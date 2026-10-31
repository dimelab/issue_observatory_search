"""Tests for adding keywords to an existing search session.

Covers queuing keywords (SearchService.add_queries), searching the queued ones
(run_pending_queries), the two session endpoints, and the scraping rule that a
job skips URLs earlier jobs on the same session already collected.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.api.search import router as search_router
from backend.core.search_engines.base import SearchResult as EngineResult
from backend.database import get_db
from backend.models.scraping import ScrapingJob
from backend.models.search import SearchQuery, SearchResult, SearchSession
from backend.models.website import Website, WebsiteContent
from backend.services.search_service import SearchService
from backend.tasks import search_tasks
from backend.tasks.scraping_tasks import get_previously_collected_urls
from backend.utils.dependencies import get_current_active_user


class StubEngine:
    """Search engine double: fixed URLs per keyword, optional failures."""

    name = "serper"

    def __init__(self, urls_by_query, fail_on=()):
        self.urls_by_query = urls_by_query
        self.fail_on = set(fail_on)
        self.calls = []

    async def search(self, query, max_results, hl, gl):
        self.calls.append((query, max_results, hl, gl))
        if query in self.fail_on:
            raise RuntimeError("quota exceeded")
        return [
            EngineResult(
                url=url,
                title=f"Title {rank}",
                description="d",
                rank=rank,
                domain=url.split("/")[2],
            )
            for rank, url in enumerate(self.urls_by_query.get(query, []), start=1)
        ]


@pytest.fixture
async def session_with_results(db_session, test_user):
    """Completed session with one searched keyword and two stored URLs."""
    session = SearchSession(
        user_id=test_user.id,
        name="Gender equality",
        status="completed",
        config={
            "search_engine": "serper",
            "max_results": 7,
            "language": "da",
            "country": "dk",
            "allowed_domains": None,
        },
    )
    db_session.add(session)
    await db_session.flush()

    query = SearchQuery(
        session_id=session.id,
        query_text="ligestilling",
        search_engine="serper",
        max_results=7,
        status="completed",
        result_count=2,
    )
    db_session.add(query)
    await db_session.flush()
    for rank, url in enumerate(["https://a.dk/one", "https://b.dk/two"], start=1):
        db_session.add(
            SearchResult(
                query_id=query.id,
                url=url,
                title=f"t{rank}",
                rank=rank,
                domain=url.split("/")[2],
            )
        )
    await db_session.commit()
    return session


@pytest.fixture
def stub_engine(monkeypatch):
    """Install a StubEngine as the only search engine; returns a setter."""
    holder = {}

    def install(engine):
        holder["engine"] = engine
        monkeypatch.setattr(
            SearchService, "_get_search_engine", lambda self, name: engine
        )
        return engine

    return install


async def queries_of(db_session, session):
    result = await db_session.execute(
        select(SearchQuery)
        .where(SearchQuery.session_id == session.id)
        .order_by(SearchQuery.id)
    )
    return list(result.scalars().all())


class TestQueueThenRun:
    """A new multi-keyword search is queued as pending keywords, then run like added ones."""

    async def test_dedupes_across_keywords_and_records_failures(
        self, db_session, test_user, stub_engine
    ):
        engine = stub_engine(
            StubEngine(
                {
                    "one": ["https://a.dk/1", "https://b.dk/2"],
                    "two": ["https://b.dk/2", "https://c.dk/3"],
                },
                fail_on={"bad"},
            )
        )
        service = SearchService(db_session, test_user)
        session, count = await service.queue_session(
            "S",
            ["one", "bad", "two"],
            {
                "search_engine": "serper",
                "max_results": 5,
                "language": "da",
                "country": "dk",
                "allowed_domains": None,
            },
        )
        assert count == 3
        assert [q.status for q in await queries_of(db_session, session)] == ["pending"] * 3

        summary = await service.run_pending_queries(session)

        assert (summary["queries_run"], summary["queries_failed"]) == (3, 1)
        assert engine.calls[0] == ("one", 5, "da", "dk")
        by_text = {q.query_text: q for q in await queries_of(db_session, session)}
        assert (by_text["one"].result_count, by_text["two"].result_count) == (2, 1)
        assert by_text["one"].search_engine == "serper"
        assert by_text["one"].max_results == 5
        assert by_text["bad"].status == "failed"
        assert "quota exceeded" in by_text["bad"].error_message


class TestAddQueries:
    """SearchService.add_queries and count_pending_queries."""

    async def test_queues_pending_queries_with_session_settings(
        self, db_session, test_user, session_with_results
    ):
        service = SearchService(db_session, test_user)

        added, skipped = await service.add_queries(
            session_with_results, ["kønsbalance", "løngab"]
        )

        assert [q.query_text for q in added] == ["kønsbalance", "løngab"]
        assert skipped == []
        for q in added:
            assert q.status == "pending"
            assert q.search_engine == "serper"
            assert q.max_results == 7
            assert q.language == "da"
            assert q.result_count == 0
        assert await service.count_pending_queries(session_with_results.id) == 2

    async def test_skips_keywords_already_in_session(
        self, db_session, test_user, session_with_results
    ):
        service = SearchService(db_session, test_user)

        added, skipped = await service.add_queries(
            session_with_results, ["LIGESTILLING", "ny  søgning", "Ny Søgning"]
        )

        assert [q.query_text for q in added] == ["ny  søgning"]
        assert skipped == ["LIGESTILLING", "Ny Søgning"]

    async def test_failed_keyword_can_be_added_again(
        self, db_session, test_user, session_with_results
    ):
        service = SearchService(db_session, test_user)
        existing = (await queries_of(db_session, session_with_results))[0]
        existing.status = "failed"
        await db_session.commit()

        added, skipped = await service.add_queries(
            session_with_results, ["ligestilling"]
        )

        assert len(added) == 1 and skipped == []
        assert added[0].status == "pending"

    async def test_session_without_config_uses_defaults(self, db_session, test_user):
        session = SearchSession(
            user_id=test_user.id, name="Old", status="completed", config=None
        )
        db_session.add(session)
        await db_session.commit()

        added, _ = await SearchService(db_session, test_user).add_queries(
            session, ["x"]
        )

        assert added[0].search_engine == "google_custom"
        assert added[0].max_results == 10


class TestRunPendingQueries:
    """SearchService.run_pending_queries."""

    async def test_searches_only_pending_and_dedupes_against_session(
        self, db_session, test_user, session_with_results, stub_engine
    ):
        engine = stub_engine(
            StubEngine(
                {
                    # a.dk/one is already stored by "ligestilling"; the
                    # trailing slash and fragment must not defeat the check
                    "kønsbalance": [
                        "https://a.dk/one/#top",
                        "https://c.dk/three",
                    ],
                    "løngab": ["https://c.dk/three", "https://d.dk/four"],
                    "ligestilling": ["https://z.dk/should-not-run"],
                }
            )
        )
        service = SearchService(db_session, test_user)
        await service.add_queries(session_with_results, ["kønsbalance", "løngab"])

        summary = await service.run_pending_queries(session_with_results)

        assert [call[0] for call in engine.calls] == ["kønsbalance", "løngab"]
        assert engine.calls[0][1:] == (7, "da", "dk")
        assert summary == {
            "queries_run": 2,
            "queries_failed": 0,
            "new_results": 2,  # c.dk/three once, d.dk/four
            "pending_count": 0,
        }
        by_text = {
            q.query_text: q for q in await queries_of(db_session, session_with_results)
        }
        assert by_text["kønsbalance"].status == "completed"
        assert by_text["kønsbalance"].result_count == 1
        assert by_text["løngab"].result_count == 1
        assert by_text["kønsbalance"].executed_at is not None
        assert by_text["ligestilling"].result_count == 2  # untouched
        assert session_with_results.status == "completed"

        urls = (
            (
                await db_session.execute(
                    select(SearchResult.url)
                    .join(SearchQuery)
                    .where(SearchQuery.session_id == session_with_results.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(urls) == len(set(urls)) == 4

    async def test_second_run_does_nothing(
        self, db_session, test_user, session_with_results, stub_engine
    ):
        engine = stub_engine(StubEngine({"ny": ["https://c.dk/x"]}))
        service = SearchService(db_session, test_user)
        await service.add_queries(session_with_results, ["ny"])
        await service.run_pending_queries(session_with_results)

        summary = await service.run_pending_queries(session_with_results)

        assert summary["queries_run"] == 0
        assert len(engine.calls) == 1

    async def test_one_failing_keyword_does_not_stop_the_rest(
        self, db_session, test_user, session_with_results, stub_engine
    ):
        stub_engine(StubEngine({"ok": ["https://c.dk/x"]}, fail_on={"bad"}))
        service = SearchService(db_session, test_user)
        await service.add_queries(session_with_results, ["bad", "ok"])

        summary = await service.run_pending_queries(session_with_results)

        assert summary["queries_run"] == 2
        assert summary["queries_failed"] == 1
        assert summary["new_results"] == 1
        by_text = {
            q.query_text: q for q in await queries_of(db_session, session_with_results)
        }
        assert by_text["bad"].status == "failed"
        assert "quota exceeded" in by_text["bad"].error_message
        assert by_text["ok"].status == "completed"

    async def test_unconfigured_engine_leaves_queries_pending(
        self, db_session, test_user, session_with_results, monkeypatch
    ):
        def not_configured(self, name):
            raise ValueError("Serper API key not configured")

        monkeypatch.setattr(SearchService, "_get_search_engine", not_configured)
        service = SearchService(db_session, test_user)
        await service.add_queries(session_with_results, ["ny"])

        with pytest.raises(ValueError, match="not configured"):
            await service.run_pending_queries(session_with_results)

        assert await service.count_pending_queries(session_with_results.id) == 1


class TestSessionEndpoints:
    """POST /search/session/{id}/queries and /queries/run."""

    @pytest.fixture
    async def api(self, db_session, test_user):
        app = FastAPI()
        app.include_router(search_router, prefix="/api")

        async def override_db():
            yield db_session

        async def override_user():
            return test_user

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_active_user] = override_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client

    async def test_add_then_queue_the_search(
        self, api, db_session, session_with_results, monkeypatch, stub_engine
    ):
        stub_engine(StubEngine({}))
        sent = []
        monkeypatch.setattr(
            search_tasks.run_search_session,
            "apply_async",
            lambda args, task_id, queue, **kw: sent.append((args, task_id, queue)),
        )
        base = f"/api/search/session/{session_with_results.id}"

        response = await api.post(
            f"{base}/queries", json={"queries": ["ny", " NY ", "ligestilling", ""]}
        )
        assert response.status_code == 201
        body = response.json()
        assert body["added"] == ["ny"]
        assert body["skipped"] == ["ligestilling"]
        assert body["pending_count"] == 1

        response = await api.post(f"{base}/queries/run")
        assert response.status_code == 202  # queued for a worker, nothing searched here
        body = response.json()
        assert (body["queued"], body["status"]) == (1, "pending")
        assert sent == [([session_with_results.id], body["task_id"], "search")]

        # queued: a second click must not queue it again
        response = await api.post(f"{base}/queries/run")
        assert response.status_code == 409
        assert len(sent) == 1

    async def test_rejects_blank_keywords(self, api, session_with_results):
        response = await api.post(
            f"/api/search/session/{session_with_results.id}/queries",
            json={"queries": ["  ", ""]},
        )
        assert response.status_code == 422

    async def test_other_users_session_is_404(self, api, db_session, test_admin):
        foreign = SearchSession(
            user_id=test_admin.id, name="Theirs", status="completed", config={}
        )
        db_session.add(foreign)
        await db_session.commit()

        for path, body in (("queries", {"queries": ["x"]}), ("queries/run", None)):
            response = await api.post(
                f"/api/search/session/{foreign.id}/{path}", json=body
            )
            assert response.status_code == 404

    async def test_run_is_refused_while_session_processes(
        self, api, db_session, session_with_results
    ):
        session_with_results.status = "processing"
        await db_session.commit()

        response = await api.post(
            f"/api/search/session/{session_with_results.id}/queries/run"
        )

        assert response.status_code == 409

    async def test_unconfigured_engine_is_400(
        self, api, db_session, session_with_results, monkeypatch
    ):
        def not_configured(self, name):
            raise ValueError("Serper API key not configured")

        monkeypatch.setattr(SearchService, "_get_search_engine", not_configured)
        base = f"/api/search/session/{session_with_results.id}"
        await api.post(f"{base}/queries", json={"queries": ["ny"]})

        response = await api.post(f"{base}/queries/run")

        assert response.status_code == 400
        assert "not configured" in response.json()["detail"]


class TestPreviouslyCollectedUrls:
    """Scraping jobs skip what earlier jobs on the session collected."""

    async def _job(self, db_session, user, session, name):
        job = ScrapingJob(
            user_id=user.id,
            session_id=session.id,
            name=name,
            status="completed",
            depth=1,
            domain_filter="same_domain",
        )
        db_session.add(job)
        await db_session.flush()
        return job

    async def _content(self, db_session, user, job, url, status):
        website = (
            await db_session.execute(select(Website).where(Website.url == url))
        ).scalar_one_or_none()
        if website is None:
            website = Website(url=url, domain=url.split("/")[2])
            db_session.add(website)
            await db_session.flush()
        db_session.add(
            WebsiteContent(
                website_id=website.id,
                user_id=user.id,
                scraping_job_id=job.id,
                url=url,
                status=status,
                scrape_depth=1,
            )
        )

    async def test_only_successful_content_of_other_jobs_on_same_session(
        self, db_session, test_user, session_with_results
    ):
        other = SearchSession(
            user_id=test_user.id, name="Other", status="completed", config={}
        )
        db_session.add(other)
        await db_session.flush()

        first = await self._job(db_session, test_user, session_with_results, "first")
        second = await self._job(db_session, test_user, session_with_results, "second")
        elsewhere = await self._job(db_session, test_user, other, "elsewhere")
        await self._content(db_session, test_user, first, "https://a.dk/one", "success")
        await self._content(db_session, test_user, first, "https://b.dk/two", "failed")
        await self._content(
            db_session, test_user, second, "https://own.dk/x", "success"
        )
        await self._content(
            db_session, test_user, elsewhere, "https://o.dk/y", "success"
        )
        await db_session.commit()

        collected = await get_previously_collected_urls(db_session, second)

        # a.dk/one: collected by "first". b.dk/two: failed, so tried again.
        # own.dk/x: the job's own content. o.dk/y: a different session.
        assert collected == {"https://a.dk/one"}
