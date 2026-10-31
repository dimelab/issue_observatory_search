"""Tests for searching in workers: queueing, admission, heartbeat, recovery, the task."""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from celery.exceptions import Retry
from sqlalchemy import select

from backend.config import settings
from backend.core.search_engines.base import SearchResult as EngineResult
from backend.models.search import SearchQuery, SearchResult, SearchSession
from backend.services import search_service
from backend.services.search_service import (
    QUEUED_STALE_AFTER,
    SearchQueueError,
    SearchService,
    stale_after,
)
from backend.tasks import search_tasks

CONFIG = {
    "search_engine": "serper",
    "max_results": 10,
    "language": "da",
    "country": "dk",
    "allowed_domains": None,
}


class Engine:
    """Search engine double: one page per keyword, optional failure, optional wait."""

    name = "serper"

    def __init__(self, fail_on=(), delay=0.0):
        self.fail_on = set(fail_on)
        self.delay = delay
        self.calls = []

    async def search(self, query, max_results, hl, gl):
        self.calls.append(query)
        if self.delay:
            await asyncio.sleep(self.delay)
        if query in self.fail_on:
            raise RuntimeError("quota exceeded")
        url = f"https://{query.replace(' ', '-')}.dk/page"
        return [
            EngineResult(
                url=url, title="t", description="d", rank=1, domain=url.split("/")[2]
            )
        ]


@pytest.fixture
def use_engine(monkeypatch):
    def install(engine):
        monkeypatch.setattr(
            SearchService, "_get_search_engine", lambda self, name: engine
        )
        return engine

    return install


@pytest.fixture
def task_env(monkeypatch, db_session):
    """Let the task use the test's database session and no Redis."""

    class Context:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(search_tasks, "AsyncSessionLocal", lambda: Context())
    monkeypatch.setattr(search_tasks, "build_limits", lambda: None)
    monkeypatch.setattr(search_tasks, "heartbeat_every", lambda: 3600)


async def make_session(
    db_session, user, keywords=("one", "two"), status="pending", task_id="t1", **fields
):
    service = SearchService(db_session, user)
    session, _ = await service.queue_session("S", list(keywords), dict(CONFIG))
    session.status = status
    session.celery_task_id = task_id
    for key, value in fields.items():
        setattr(session, key, value)
    await db_session.commit()
    return session


async def queries_of(db_session, session):
    result = await db_session.execute(
        select(SearchQuery)
        .where(SearchQuery.session_id == session.id)
        .order_by(SearchQuery.id)
    )
    return list(result.scalars().all())


def minutes_ago(n):
    return datetime.utcnow() - timedelta(minutes=n)


@pytest.mark.asyncio
class TestQueueAndStart:
    async def test_queue_session_holds_the_keywords_as_pending(
        self, db_session, test_user
    ):
        session, count = await SearchService(db_session, test_user).queue_session(
            "S", ["a", "b", "A", "c"], dict(CONFIG)
        )

        assert (session.status, count) == ("pending", 3)  # "A" is "a" again
        assert [q.status for q in await queries_of(db_session, session)] == [
            "pending"
        ] * 3

    async def test_start_stores_the_task_id_before_sending_it(
        self, db_session, test_user, monkeypatch
    ):
        session = await make_session(
            db_session, test_user, status="failed", task_id=None
        )
        session.error_message = "old"
        sent = []

        def apply_async(args, task_id, queue, **kwargs):
            # what the worker would find the moment it gets the task
            sent.append((args, task_id, queue, session.status, session.celery_task_id))

        monkeypatch.setattr(search_tasks.run_search_session, "apply_async", apply_async)

        task_id = await SearchService(db_session, test_user).start(session)

        assert sent == [([session.id], task_id, "search", "pending", task_id)]
        assert session.error_message is None and session.completed_at is None

    async def test_broker_down_marks_the_session_failed(
        self, db_session, test_user, monkeypatch
    ):
        session = await make_session(db_session, test_user, task_id=None)

        def broken(*args, **kwargs):
            raise ConnectionError("redis is down")

        monkeypatch.setattr(search_tasks.run_search_session, "apply_async", broken)

        with pytest.raises(SearchQueueError):
            await SearchService(db_session, test_user).start(session)

        assert session.status == "failed"
        assert "queue is not available" in session.error_message

    async def test_missing_key_is_reported_before_queueing(
        self, db_session, test_user, monkeypatch
    ):
        session = await make_session(db_session, test_user)
        monkeypatch.setattr(settings, "serper_api_key", None)

        with pytest.raises(ValueError, match="Serper API key"):
            await SearchService(db_session, test_user).ensure_engines_configured(
                session
            )

    @pytest.mark.parametrize(
        "status, task_id, age, busy",
        [
            ("pending", "t", timedelta(minutes=5), True),  # queued
            ("pending", None, timedelta(minutes=5), False),  # never sent
            (
                "pending",
                "t",
                QUEUED_STALE_AFTER + timedelta(minutes=1),
                False,
            ),  # queue lost it
            ("processing", "t", timedelta(seconds=30), True),
            (
                "processing",
                "t",
                stale_after() + timedelta(minutes=1),
                False,
            ),  # worker gone
            ("completed", "t", timedelta(0), False),
            ("failed", "t", timedelta(0), False),
        ],
    )
    async def test_is_busy(self, db_session, test_user, status, task_id, age, busy):
        session = await make_session(
            db_session, test_user, status=status, task_id=task_id
        )
        session.updated_at = datetime.utcnow() - age

        assert SearchService.is_busy(session) is busy


@pytest.mark.asyncio
class TestAdmission:
    async def test_a_queued_session_is_admitted_and_marked_processing(
        self, db_session, test_user
    ):
        session = await make_session(db_session, test_user)

        verdict = await SearchService(db_session, test_user).admit_session(
            session, "t1"
        )

        assert verdict == "run"
        assert session.status == "processing"
        assert session.started_at is not None

    async def test_keywords_a_dead_run_left_claimed_are_pending_again(
        self, db_session, test_user
    ):
        session = await make_session(
            db_session,
            test_user,
            ["a", "b", "c"],
            status="processing",
            updated_at=minutes_ago(10),
        )
        a, b, c = await queries_of(db_session, session)
        a.status, a.result_count = "completed", 1
        b.status = "processing"
        c.status = "failed"
        await db_session.commit()

        verdict = await SearchService(db_session, test_user).admit_session(
            session, "t1"
        )

        assert verdict == "run"
        assert [q.status for q in await queries_of(db_session, session)] == [
            "completed",
            "pending",
            "failed",
        ]

    async def test_a_session_another_worker_is_on_waits(self, db_session, test_user):
        session = await make_session(
            db_session, test_user, status="processing", updated_at=minutes_ago(0)
        )

        assert (
            await SearchService(db_session, test_user).admit_session(session, "t1")
            == "wait"
        )

    async def test_a_session_whose_worker_stopped_reporting_is_taken_over(
        self, db_session, test_user
    ):
        session = await make_session(
            db_session, test_user, status="processing", updated_at=minutes_ago(5)
        )

        assert (
            await SearchService(db_session, test_user).admit_session(session, "t1")
            == "run"
        )

    @pytest.mark.parametrize("status", ["completed", "failed"])
    async def test_a_finished_session_is_left_alone(
        self, db_session, test_user, status
    ):
        session = await make_session(db_session, test_user, status=status)

        assert (
            await SearchService(db_session, test_user).admit_session(session, "t1")
            == "done"
        )
        assert session.status == status

    async def test_an_older_task_does_not_run_a_session_queued_again(
        self, db_session, test_user
    ):
        session = await make_session(db_session, test_user, task_id="newer")

        assert (
            await SearchService(db_session, test_user).admit_session(session, "older")
            == "superseded"
        )
        assert session.status == "pending"

    async def test_a_user_searches_one_session_at_a_time(self, db_session, test_user):
        running = await make_session(
            db_session,
            test_user,
            status="processing",
            updated_at=minutes_ago(0),
            task_id="r",
        )
        waiting = await make_session(db_session, test_user, task_id="w")
        service = SearchService(db_session, test_user)

        assert await service.admit_session(waiting, "w") == "wait"
        assert waiting.status == "pending"

        running.status = "completed"
        await db_session.commit()

        assert await service.admit_session(waiting, "w") == "run"

    async def test_the_cap_can_be_raised(self, db_session, test_user, monkeypatch):
        monkeypatch.setattr(settings, "search_max_active_per_user", 2)
        await make_session(
            db_session,
            test_user,
            status="processing",
            updated_at=minutes_ago(0),
            task_id="r",
        )
        second = await make_session(db_session, test_user, task_id="w")
        third = await make_session(db_session, test_user, task_id="x")
        service = SearchService(db_session, test_user)

        assert await service.admit_session(second, "w") == "run"
        assert await service.admit_session(third, "x") == "wait"

    async def test_another_users_search_does_not_count(
        self, db_session, test_user, test_admin
    ):
        await make_session(
            db_session,
            test_admin,
            status="processing",
            updated_at=minutes_ago(0),
            task_id="r",
        )
        mine = await make_session(db_session, test_user, task_id="w")

        assert (
            await SearchService(db_session, test_user).admit_session(mine, "w") == "run"
        )

    async def test_a_crashed_session_stops_counting_once_its_heartbeat_lapses(
        self, db_session, test_user
    ):
        await make_session(
            db_session,
            test_user,
            status="processing",
            updated_at=minutes_ago(10),
            task_id="dead",
        )
        mine = await make_session(db_session, test_user, task_id="w")

        assert (
            await SearchService(db_session, test_user).admit_session(mine, "w") == "run"
        )


@pytest.mark.asyncio
class TestFinishAndProgress:
    async def test_completed_even_when_a_keyword_failed(
        self, db_session, test_user, use_engine
    ):
        use_engine(Engine(fail_on={"two"}))
        service = SearchService(db_session, test_user)
        session = await make_session(db_session, test_user, status="processing")

        await service.run_pending_queries(session)
        await service.finish_session(session)

        assert session.status == "completed" and session.completed_at is not None
        assert [q.status for q in await queries_of(db_session, session)] == [
            "completed",
            "failed",
        ]

    async def test_failure_records_why_and_releases_claimed_keywords(
        self, db_session, test_user
    ):
        session = await make_session(db_session, test_user, status="processing")
        first, second = await queries_of(db_session, session)
        first.status = "processing"
        second.status = "completed"
        await db_session.commit()

        await SearchService(db_session, test_user).finish_session(
            session, error="database gone"
        )

        assert session.status == "failed" and session.error_message == "database gone"
        assert [q.status for q in await queries_of(db_session, session)] == [
            "pending",
            "completed",
        ]

    async def test_progress_counts_the_keywords(self, db_session, test_user):
        session = await make_session(
            db_session, test_user, ["a", "b", "c", "d"], status="processing"
        )
        a, b, c, d = await queries_of(db_session, session)
        a.status, a.result_count = "completed", 7
        b.status, b.result_count = "completed", 3
        c.status = "failed"
        d.status = "processing"
        await db_session.commit()

        progress = await SearchService(db_session, test_user).progress(session)

        assert (progress["total"], progress["completed"], progress["failed"]) == (
            4,
            2,
            1,
        )
        assert (progress["pending"], progress["processing"], progress["results"]) == (
            0,
            1,
            10,
        )
        assert progress["status"] == "processing" and progress["stale"] is False

    async def test_progress_says_when_the_worker_stopped_reporting(
        self, db_session, test_user
    ):
        session = await make_session(
            db_session, test_user, status="processing", updated_at=minutes_ago(10)
        )

        assert (await SearchService(db_session, test_user).progress(session))[
            "stale"
        ] is True

    async def test_progress_of_a_session_without_keywords(self, db_session, test_user):
        session = SearchSession(
            user_id=test_user.id, name="Empty", status="completed", config={}
        )
        db_session.add(session)
        await db_session.commit()

        progress = await SearchService(db_session, test_user).progress(session)

        assert (progress["total"], progress["results"]) == (0, 0)


@pytest.mark.asyncio
class TestTask:
    async def test_searches_the_session_and_completes_it(
        self, db_session, test_user, use_engine, task_env
    ):
        engine = use_engine(Engine())
        session = await make_session(db_session, test_user, ["one", "two", "three"])

        outcome = await search_tasks._run_session(session.id, "t1")

        assert outcome == "completed"
        assert session.status == "completed"
        assert sorted(engine.calls) == ["one", "three", "two"]
        assert [q.status for q in await queries_of(db_session, session)] == [
            "completed"
        ] * 3

    async def test_an_unexpected_error_fails_the_session_with_the_reason(
        self, db_session, test_user, use_engine, task_env, monkeypatch
    ):
        use_engine(Engine())

        async def broken(self, session):
            raise RuntimeError("database gone")

        monkeypatch.setattr(SearchService, "run_pending_queries", broken)
        session = await make_session(db_session, test_user)

        outcome = await search_tasks._run_session(session.id, "t1")

        assert outcome == "failed"
        assert session.status == "failed" and session.error_message == "database gone"

    async def test_a_missing_key_fails_the_session_with_a_readable_message(
        self, db_session, test_user, task_env, monkeypatch
    ):
        monkeypatch.setattr(settings, "serper_api_key", None)
        session = await make_session(db_session, test_user)

        outcome = await search_tasks._run_session(session.id, "t1")

        assert outcome == "failed"
        assert session.error_message == "Serper API key not configured"

    async def test_waits_when_the_user_already_searches(
        self, db_session, test_user, use_engine, task_env
    ):
        engine = use_engine(Engine())
        await make_session(
            db_session,
            test_user,
            status="processing",
            updated_at=minutes_ago(0),
            task_id="r",
        )
        waiting = await make_session(db_session, test_user, task_id="w")

        assert await search_tasks._run_session(waiting.id, "w") == "wait"
        assert engine.calls == [] and waiting.status == "pending"

    async def test_a_deleted_session_is_not_an_error(self, db_session, task_env):
        assert await search_tasks._run_session(987654, "t") == "missing"

    async def test_redelivery_after_a_crash_finishes_only_the_keywords_left(
        self, db_session, test_user, use_engine, task_env
    ):
        engine = use_engine(Engine())
        session = await make_session(
            db_session,
            test_user,
            ["done", "left1", "left2"],
            status="processing",
            updated_at=minutes_ago(10),
        )
        done, left1, _ = await queries_of(db_session, session)
        done.status, done.result_count = "completed", 1
        db_session.add(
            SearchResult(
                query_id=done.id,
                url="https://done.dk/page",
                title="t",
                rank=1,
                domain="done.dk",
            )
        )
        left1.status = "processing"  # claimed by the worker that died
        await db_session.commit()

        outcome = await search_tasks._run_session(session.id, "t1")

        assert outcome == "completed"
        assert sorted(engine.calls) == [
            "left1",
            "left2",
        ]  # "done" is not searched again
        urls = (await db_session.execute(select(SearchResult.url))).scalars().all()
        assert sorted(urls) == [
            "https://done.dk/page",
            "https://left1.dk/page",
            "https://left2.dk/page",
        ]

    @staticmethod
    def one_beat(monkeypatch, db_session):
        """Let _heartbeat beat exactly once: the second sleep ends it, outside any statement."""

        class Context:
            async def __aenter__(self):
                return db_session

            async def __aexit__(self, *exc):
                return False

        sleeps = []

        async def sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) > 1:
                raise asyncio.CancelledError

        monkeypatch.setattr(search_tasks, "AsyncSessionLocal", lambda: Context())
        monkeypatch.setattr(search_tasks.asyncio, "sleep", sleep)
        return sleeps

    async def test_the_heartbeat_keeps_updated_at_fresh(
        self, db_session, test_user, monkeypatch
    ):
        session = await make_session(
            db_session, test_user, status="processing", updated_at=minutes_ago(10)
        )
        old = session.updated_at
        sleeps = self.one_beat(monkeypatch, db_session)

        with pytest.raises(asyncio.CancelledError):
            await search_tasks._heartbeat(session.id)
        await db_session.refresh(session)

        assert sleeps[0] == search_tasks.heartbeat_every()
        assert session.updated_at > old + timedelta(minutes=9)

    async def test_the_heartbeat_leaves_a_finished_session_alone(
        self, db_session, test_user, monkeypatch
    ):
        session = await make_session(
            db_session, test_user, status="completed", updated_at=minutes_ago(10)
        )
        old = session.updated_at
        self.one_beat(monkeypatch, db_session)

        with pytest.raises(asyncio.CancelledError):
            await search_tasks._heartbeat(session.id)
        await db_session.refresh(session)

        assert session.updated_at == old

    async def test_a_failed_beat_is_logged_and_the_next_one_still_comes(
        self, db_session, test_user, monkeypatch, caplog
    ):
        session = await make_session(db_session, test_user, status="processing")
        sleeps = []

        class Broken:
            async def __aenter__(self):
                raise ConnectionError("database restarting")

            async def __aexit__(self, *exc):
                return False

        async def sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) > 2:
                raise asyncio.CancelledError

        monkeypatch.setattr(search_tasks, "AsyncSessionLocal", lambda: Broken())
        monkeypatch.setattr(search_tasks.asyncio, "sleep", sleep)

        with pytest.raises(asyncio.CancelledError):
            await search_tasks._heartbeat(session.id)

        assert len(sleeps) == 3  # it beat twice, both failed, and it kept going
        assert caplog.text.count("Heartbeat for search session") == 2


@pytest.mark.asyncio
class TestRecoverStalled:
    """A killed worker's task is not redelivered for hours: the recovery task restarts the session."""

    @pytest.fixture
    def sent(self, monkeypatch):
        sent = []
        monkeypatch.setattr(
            search_tasks.run_search_session,
            "apply_async",
            lambda args, task_id, queue, **kw: sent.append((args, task_id, queue)),
        )
        return sent

    async def test_a_session_that_stopped_reporting_is_queued_again(
        self, db_session, test_user, task_env, sent
    ):
        session = await make_session(
            db_session,
            test_user,
            status="processing",
            task_id="dead-task",
            updated_at=minutes_ago(10),
        )

        restarted = await search_tasks._recover_stalled()

        assert restarted == [session.id]
        assert sent == [([session.id], session.celery_task_id, "search")]
        assert (
            session.celery_task_id != "dead-task"
        )  # a new task: the old one will find itself superseded
        assert session.status == "pending" and session.config["auto_restarts"] == 1

    async def test_sessions_that_are_fine_are_left_alone(
        self, db_session, test_user, test_admin, task_env, sent
    ):
        fresh = await make_session(
            db_session, test_user, status="processing", updated_at=minutes_ago(0)
        )
        queued = await make_session(
            db_session, test_user, status="pending", updated_at=minutes_ago(30)
        )
        done = await make_session(
            db_session, test_user, status="completed", updated_at=minutes_ago(30)
        )
        failed = await make_session(
            db_session, test_admin, status="failed", updated_at=minutes_ago(30)
        )

        assert await search_tasks._recover_stalled() == []

        assert sent == []
        assert [x.status for x in (fresh, queued, done, failed)] == [
            "processing",
            "pending",
            "completed",
            "failed",
        ]

    async def test_the_window_is_a_setting(
        self, db_session, test_user, task_env, sent, monkeypatch
    ):
        session = await make_session(
            db_session, test_user, status="processing", updated_at=minutes_ago(10)
        )
        monkeypatch.setattr(
            settings, "search_stale_seconds", 3600
        )  # an hour: ten minutes is fine

        assert await search_tasks._recover_stalled() == []

    async def test_it_gives_up_after_a_few_restarts(
        self, db_session, test_user, task_env, sent
    ):
        session = await make_session(
            db_session, test_user, status="processing", updated_at=minutes_ago(10)
        )
        session.config = {
            **session.config,
            "auto_restarts": search_tasks.MAX_AUTO_RESTARTS,
        }
        session.updated_at = minutes_ago(10)  # a change to the row would otherwise count as a report
        await db_session.commit()

        assert await search_tasks._recover_stalled() == []

        assert sent == []
        assert (
            session.status == "failed" and "stopped repeatedly" in session.error_message
        )

    async def test_the_queue_being_down_is_not_a_crash(
        self, db_session, test_user, task_env, monkeypatch
    ):
        def broken(*args, **kwargs):
            raise ConnectionError("redis is down")

        monkeypatch.setattr(search_tasks.run_search_session, "apply_async", broken)
        await make_session(
            db_session, test_user, status="processing", updated_at=minutes_ago(10)
        )

        assert (
            await search_tasks._recover_stalled() == []
        )  # logged, and the next minute tries again

    async def test_a_restarted_session_is_then_searched_by_the_next_task(
        self, db_session, test_user, task_env, sent, use_engine
    ):
        engine = use_engine(Engine())
        session = await make_session(
            db_session,
            test_user,
            ["one", "two"],
            status="processing",
            updated_at=minutes_ago(10),
        )
        first, second = await queries_of(db_session, session)
        first.status = "processing"  # claimed by the worker that died
        await db_session.commit()
        await search_tasks._recover_stalled()

        outcome = await search_tasks._run_session(session.id, session.celery_task_id)

        assert outcome == "completed" and sorted(engine.calls) == ["one", "two"]

    async def test_the_old_task_is_superseded_if_it_turns_up_later(
        self, db_session, test_user, task_env, sent
    ):
        session = await make_session(
            db_session,
            test_user,
            status="processing",
            task_id="dead-task",
            updated_at=minutes_ago(10),
        )
        await search_tasks._recover_stalled()

        assert await search_tasks._run_session(session.id, "dead-task") == "superseded"


class TestRecoveryWiring:
    def test_beat_runs_it_every_minute_on_the_default_queue(self):
        from backend.celery_app import celery_app

        entry = celery_app.conf.beat_schedule["recover-stalled-searches"]

        assert entry["task"] == search_tasks.recover_stalled_searches.name
        assert entry["schedule"] == 60.0
        assert (
            entry["options"]["queue"] == "celery"
        )  # not behind long searches on the search queue

    def test_the_task_reports_what_it_restarted(self, monkeypatch):
        monkeypatch.setattr(
            search_tasks, "_run_async", lambda coro: (coro.close(), [4, 7])[1]
        )

        assert search_tasks.recover_stalled_searches.apply().get() == {
            "restarted": [4, 7]
        }

    def test_the_heartbeat_comes_well_inside_the_window(self, monkeypatch):
        for seconds in (12, 180, 600):
            monkeypatch.setattr(settings, "search_stale_seconds", seconds)
            assert search_service.heartbeat_every() * 5 <= seconds


class TestTaskWrapper:
    """The Celery task itself, with the async part replaced."""

    def test_returns_the_outcome(self, monkeypatch):
        monkeypatch.setattr(
            search_tasks, "_run_async", lambda coro: (coro.close(), "completed")[1]
        )

        result = search_tasks.run_search_session.apply(args=[5], task_id="t").get()

        assert result == {"session_id": 5, "outcome": "completed"}

    def test_asks_again_later_while_the_user_is_busy(self, monkeypatch):
        monkeypatch.setattr(
            search_tasks, "_run_async", lambda coro: (coro.close(), "wait")[1]
        )
        retried = []

        def retry(countdown):
            retried.append(countdown)
            return Retry()

        monkeypatch.setattr(search_tasks.run_search_session, "retry", retry)

        with pytest.raises(Retry):
            search_tasks.run_search_session.run(5)

        assert retried == [search_tasks.REQUEUE_DELAY]

    def test_is_routed_to_the_search_queue_and_not_limited_to_ten_minutes(self):
        from backend.celery_app import celery_app

        route = celery_app.amqp.router.route({}, search_tasks.run_search_session.name)

        assert route["queue"].name == "search"
        assert (
            search_tasks.run_search_session.time_limit
            == search_tasks.SEARCH_TIME_LIMIT
            >= 3600
        )
        assert search_tasks.run_search_session.max_retries is None
        assert (
            celery_app.conf.broker_transport_options["visibility_timeout"]
            > search_tasks.SEARCH_TIME_LIMIT
        )
        assert "backend.tasks.search_tasks" in celery_app.conf.include


@pytest.mark.asyncio
class TestAdmissionRace:
    """Two admissions at the same instant need a real database: SQLite ignores row locks."""

    async def test_two_sessions_of_one_user_are_not_both_admitted(self, engine):
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from backend.models.user import User
        from backend.utils.auth import get_password_hash

        if engine.dialect.name == "sqlite":
            pytest.skip("needs row locks (PostgreSQL)")

        maker = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with maker() as setup:
            user = User(
                username="racer",
                email="racer@example.com",
                password_hash=get_password_hash("x" * 8),
                is_admin=False,
                is_active=True,
            )
            setup.add(user)
            await setup.commit()
            ids = []
            for n in range(4):  # four queued sessions of one user
                session, _ = await SearchService(setup, user).queue_session(
                    "S", ["k"], dict(CONFIG)
                )
                session.celery_task_id = f"t{n}"
                await setup.commit()
                ids.append(session.id)
            user_id = user.id

        async def admit(session_id, task_id):
            async with maker() as db:
                session = await db.get(SearchSession, session_id)
                user = await db.get(User, session.user_id)
                verdict = await SearchService(db, user).admit_session(session, task_id)
                await asyncio.sleep(
                    0.05
                )  # holding on to the outcome a moment: the others must not overtake
                return verdict

        try:
            verdicts = await asyncio.gather(
                *(admit(sid, f"t{n}") for n, sid in enumerate(ids))
            )
            assert sorted(verdicts) == ["run", "wait", "wait", "wait"]  # the cap is 1
        finally:
            async with maker() as cleanup:
                await cleanup.execute(
                    SearchSession.__table__.delete().where(
                        SearchSession.user_id == user_id
                    )
                )
                await cleanup.execute(User.__table__.delete().where(User.id == user_id))
                await cleanup.commit()
