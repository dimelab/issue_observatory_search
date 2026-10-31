"""A search queued through the service and run by a real Celery worker.

Redis is not needed: the broker is in memory and the worker is Celery's test worker, but
everything else is the real thing: the queue name and routing, the task and its time
limits, task ids, the admission rules, the heartbeat and the limits shared through
Redis (fakeredis here). It needs a database the worker can reach with its own
connections, so it runs on PostgreSQL and is skipped on SQLite.
"""

import asyncio
import time

import pytest
from celery.contrib.testing.worker import start_worker
from fakeredis import FakeAsyncRedis, FakeServer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.celery_app import celery_app
from backend.config import settings
from backend.core.concurrency import RedisLimits
from backend.core.search_engines.base import SearchResult as EngineResult
from backend.models.search import SearchQuery, SearchResult, SearchSession
from backend.models.user import User
from backend.services.search_service import SearchService
from backend.tasks import search_tasks
from backend.utils.auth import get_password_hash

CONFIG = {
    "search_engine": "serper",
    "max_results": 10,
    "language": "da",
    "country": "dk",
    "allowed_domains": None,
}


class Engine:
    """Search engine double: one result per keyword, optionally slow."""

    name = "serper"

    def __init__(self, delay=0.05):
        self.delay = delay
        self.in_flight = 0
        self.peak = 0
        self.calls = []

    async def search(self, query, max_results, hl, gl):
        self.calls.append(query)
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        try:
            await asyncio.sleep(self.delay)
        finally:
            self.in_flight -= 1
        url = f"https://{query}.dk/page"
        return [
            EngineResult(
                url=url, title="t", description="d", rank=1, domain=f"{query}.dk"
            )
        ]


@pytest.fixture
async def maker(engine):
    if engine.dialect.name == "sqlite":
        pytest.skip(
            "the worker needs its own connections to a shared database (PostgreSQL)"
        )
    return async_sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
async def users(maker):
    created = []
    async with maker() as db:
        for name in ("alice", "bob"):
            user = User(
                username=name,
                email=f"{name}@example.com",
                password_hash=get_password_hash("x" * 8),
                is_admin=False,
                is_active=True,
            )
            db.add(user)
            created.append(user)
        await db.commit()
        ids = [u.id for u in created]
    yield ids
    async with maker() as db:  # the sessions go with their users
        await db.execute(User.__table__.delete().where(User.id.in_(ids)))
        await db.commit()


@pytest.fixture
def worker(maker, monkeypatch):
    """A real Celery worker on the search queue, in this process, with the shared limits on fakeredis."""
    monkeypatch.setattr(settings, "serper_api_key", "test-key")
    monkeypatch.setattr(search_tasks, "AsyncSessionLocal", maker)
    server = FakeServer()
    monkeypatch.setattr(
        search_tasks,
        "build_limits",
        lambda: RedisLimits(client=FakeAsyncRedis(server=server), prefix="it"),
    )
    monkeypatch.setattr(search_tasks, "REQUEUE_DELAY", 0.3)
    monkeypatch.setattr(search_tasks, "heartbeat_every", lambda: 0.2)
    monkeypatch.setattr(celery_app.conf, "broker_url", "memory://", raising=False)
    celery_app.conf.update(
        broker_url="memory://",
        result_backend="cache+memory://",
        task_always_eager=False,
    )
    with start_worker(
        celery_app,
        pool="threads",
        concurrency=3,
        queues=["search"],
        perform_ping_check=False,
        loglevel="WARNING",
    ):
        yield


async def new_session(maker, user_id, keywords):
    async with maker() as db:
        user = await db.get(User, user_id)
        service = SearchService(db, user)
        session, _ = await service.queue_session("S", keywords, dict(CONFIG))
        await service.start(session)
        return session.id


async def wait_for(maker, session_id, statuses=("completed", "failed"), timeout=30.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        async with maker() as db:
            session = await db.get(SearchSession, session_id)
            if session.status in statuses:
                return session
        await asyncio.sleep(0.1)
    raise AssertionError(f"session {session_id} did not reach {statuses} in {timeout}s")


async def snapshot(maker, session_id):
    async with maker() as db:
        session = await db.get(SearchSession, session_id)
        queries = (
            (
                await db.execute(
                    select(SearchQuery).where(SearchQuery.session_id == session_id)
                )
            )
            .scalars()
            .all()
        )
        urls = (
            (
                await db.execute(
                    select(SearchResult.url)
                    .join(SearchQuery)
                    .where(SearchQuery.session_id == session_id)
                )
            )
            .scalars()
            .all()
        )
        return session, queries, sorted(urls)


@pytest.mark.asyncio
class TestSearchWorker:
    async def test_a_queued_search_is_run_by_the_worker(
        self, maker, users, worker, monkeypatch
    ):
        engine = Engine()
        monkeypatch.setattr(
            SearchService, "_get_search_engine", lambda self, name: engine
        )

        session_id = await new_session(maker, users[0], [f"kw{i}" for i in range(12)])
        done = await wait_for(maker, session_id)

        session, queries, urls = await snapshot(maker, session_id)
        assert done.status == "completed" and session.error_message is None
        assert session.started_at is not None and session.completed_at is not None
        assert [q.status for q in queries] == ["completed"] * 12
        assert urls == sorted(f"https://kw{i}.dk/page" for i in range(12))
        assert engine.peak > 1  # keywords ran at the same time, not one after another

    async def test_progress_is_visible_while_it_runs(
        self, maker, users, worker, monkeypatch
    ):
        monkeypatch.setattr(settings, "search_concurrency", 2)
        engine = Engine(delay=0.4)
        monkeypatch.setattr(
            SearchService, "_get_search_engine", lambda self, name: engine
        )

        session_id = await new_session(maker, users[0], [f"kw{i}" for i in range(6)])
        seen = set()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            async with maker() as db:
                session = await db.get(SearchSession, session_id)
                progress = await SearchService(
                    db, await db.get(User, users[0])
                ).progress(session)
            seen.add((progress["status"], progress["completed"]))
            if progress["status"] == "completed":
                break
            await asyncio.sleep(0.05)

        assert ("pending", 0) in seen or ("processing", 0) in seen
        assert any(
            status == "processing" and 0 < done < 6 for status, done in seen
        )  # partway through
        assert ("completed", 6) in seen

    async def test_a_user_searches_one_session_at_a_time_and_another_user_is_not_held_up(
        self, maker, users, worker, monkeypatch
    ):
        engine = Engine(delay=0.8)
        monkeypatch.setattr(
            SearchService, "_get_search_engine", lambda self, name: engine
        )

        first = await new_session(maker, users[0], ["a1"])
        second = await new_session(maker, users[0], ["a2"])  # the same user
        other = await new_session(maker, users[1], ["b1"])  # another user

        done = [
            await wait_for(maker, session_id) for session_id in (first, second, other)
        ]
        alice_1, alice_2, bob = done

        # Which of one user's two sessions a worker thread picks first is a race, so
        # compare the times they ran: the same user's never overlap ...
        earlier, later = sorted((alice_1, alice_2), key=lambda s: s.started_at)
        assert later.started_at >= earlier.completed_at
        # ... and the other user was not held up: it ran alongside the user's first one
        assert bob.started_at < earlier.completed_at
        assert (
            engine.calls.count("a1")
            == engine.calls.count("a2")
            == engine.calls.count("b1")
            == 1
        )

    async def test_the_same_task_delivered_twice_searches_once(
        self, maker, users, worker, monkeypatch
    ):
        engine = Engine(delay=0.3)
        monkeypatch.setattr(
            SearchService, "_get_search_engine", lambda self, name: engine
        )
        session_id = await new_session(maker, users[0], ["x1", "x2", "x3"])
        async with maker() as db:
            task_id = (await db.get(SearchSession, session_id)).celery_task_id

        # what Redis does after a visibility timeout, or a restarted worker: the same task again
        search_tasks.run_search_session.apply_async(
            args=[session_id], task_id=task_id, queue="search"
        )

        await wait_for(maker, session_id)
        await asyncio.sleep(
            1.0
        )  # give the duplicate time to wrongly start a second run
        _, queries, urls = await snapshot(maker, session_id)
        assert sorted(engine.calls) == ["x1", "x2", "x3"]
        assert len(urls) == 3 and [q.status for q in queries] == ["completed"] * 3

    async def test_a_search_that_lost_its_worker_is_finished_by_the_next_delivery(
        self, maker, users, worker, monkeypatch
    ):
        engine = Engine(delay=0.05)
        monkeypatch.setattr(
            SearchService, "_get_search_engine", lambda self, name: engine
        )
        # a dead worker's leftovers: two keywords stored, one claimed and never finished, heartbeat long gone
        async with maker() as db:
            user = await db.get(User, users[0])
            session, _ = await SearchService(db, user).queue_session(
                "S", ["d1", "d2", "d3", "d4"], dict(CONFIG)
            )
            session.status, session.celery_task_id = "processing", "dead-task"
            session.updated_at = session.updated_at.replace(year=2020)
            queries = (
                (
                    await db.execute(
                        select(SearchQuery)
                        .where(SearchQuery.session_id == session.id)
                        .order_by(SearchQuery.id)
                    )
                )
                .scalars()
                .all()
            )
            for query in queries[:2]:
                query.status, query.result_count = "completed", 1
                db.add(
                    SearchResult(
                        query_id=query.id,
                        url=f"https://{query.query_text}.dk/page",
                        title="t",
                        rank=1,
                        domain="x.dk",
                    )
                )
            queries[2].status = "processing"
            await db.commit()
            session_id = session.id

        search_tasks.run_search_session.apply_async(
            args=[session_id], task_id="dead-task", queue="search"
        )
        await wait_for(maker, session_id)

        _, queries, urls = await snapshot(maker, session_id)
        assert [q.status for q in queries] == ["completed"] * 4
        assert sorted(engine.calls) == ["d3", "d4"]  # d1 and d2 were not searched again
        assert urls == [f"https://d{i}.dk/page" for i in range(1, 5)]

    async def test_the_recovery_task_restarts_a_search_whose_worker_was_killed(
        self, maker, users, worker, monkeypatch
    ):
        engine = Engine(delay=0.05)
        monkeypatch.setattr(
            SearchService, "_get_search_engine", lambda self, name: engine
        )
        # what a kill -9 leaves: "processing", one keyword stored, one claimed, no heartbeat, and
        # a task Redis will not hand out again for hours (nothing is queued here at all)
        async with maker() as db:
            user = await db.get(User, users[0])
            session, _ = await SearchService(db, user).queue_session(
                "S", ["k1", "k2", "k3"], dict(CONFIG)
            )
            session.status, session.celery_task_id = "processing", "killed-task"
            session.updated_at = session.updated_at.replace(year=2020)
            queries = (
                (
                    await db.execute(
                        select(SearchQuery)
                        .where(SearchQuery.session_id == session.id)
                        .order_by(SearchQuery.id)
                    )
                )
                .scalars()
                .all()
            )
            queries[0].status, queries[0].result_count = "completed", 1
            db.add(
                SearchResult(
                    query_id=queries[0].id,
                    url="https://k1.dk/page",
                    title="t",
                    rank=1,
                    domain="x.dk",
                )
            )
            queries[1].status = "processing"
            await db.commit()
            session_id = session.id

        restarted = await search_tasks._recover_stalled()
        done = await wait_for(maker, session_id)

        assert restarted == [session_id]
        session, queries, urls = await snapshot(maker, session_id)
        assert done.status == "completed" and session.config["auto_restarts"] == 1
        assert [q.status for q in queries] == ["completed"] * 3
        assert sorted(engine.calls) == ["k2", "k3"]  # k1 was already stored
        assert urls == [f"https://k{i}.dk/page" for i in (1, 2, 3)]
