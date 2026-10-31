"""API tests for queueing searches for workers: execute, run, progress, delete."""

from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.api.search import router as search_router
from backend.config import settings
from backend.database import get_db
from backend.models.search import SearchQuery, SearchSession
from backend.services.search_service import SearchService, stale_after
from backend.tasks import search_tasks
from backend.utils.dependencies import get_current_active_user

EXECUTE = {
    "session_name": "Gender",
    "queries": ["ligestilling", "sexisme", "Ligestilling"],
    "search_engine": "serper",
    "max_results": 20,
    "language": "da",
    "country": "dk",
}


@pytest.fixture
async def api(db_session, test_user):
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


@pytest.fixture
def broker(monkeypatch):
    """Stand in for the Celery broker: records what would be sent to the search queue."""
    sent = []
    monkeypatch.setattr(settings, "serper_api_key", "test-key")
    monkeypatch.setattr(
        search_tasks.run_search_session,
        "apply_async",
        lambda args, task_id, queue, **kw: sent.append(
            {"args": args, "task_id": task_id, "queue": queue}
        ),
    )
    return sent


async def make_session(db_session, user, status="completed", keywords=("a",), **fields):
    service = SearchService(db_session, user)
    session, _ = await service.queue_session(
        "S",
        list(keywords),
        {
            "search_engine": "serper",
            "max_results": 10,
            "language": "da",
            "country": "dk",
        },
    )
    session.status = status
    for key, value in fields.items():
        setattr(session, key, value)
    await db_session.commit()
    return session


@pytest.mark.asyncio
class TestExecute:
    async def test_queues_the_search_and_answers_at_once(self, api, db_session, broker):
        response = await api.post("/api/search/execute", json=EXECUTE)

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "pending"
        assert "2 keywords" in body["message"]  # "Ligestilling" is "ligestilling" again
        assert body["status_url"] == f"/api/search/session/{body['session_id']}"
        assert broker == [
            {
                "args": [body["session_id"]],
                "task_id": body["task_id"],
                "queue": "search",
            }
        ]

        session = await db_session.get(SearchSession, body["session_id"])
        assert (session.status, session.celery_task_id) == ("pending", body["task_id"])
        assert (
            session.config["max_results"] == 20
            and session.config["search_engine"] == "serper"
        )
        queries = (
            (
                await db_session.execute(
                    select(SearchQuery).where(SearchQuery.session_id == session.id)
                )
            )
            .scalars()
            .all()
        )
        assert sorted((q.query_text, q.status, q.max_results) for q in queries) == [
            ("ligestilling", "pending", 20),
            ("sexisme", "pending", 20),
        ]

    async def test_a_missing_api_key_is_a_400_and_creates_nothing(
        self, api, db_session, broker, monkeypatch
    ):
        monkeypatch.setattr(settings, "serper_api_key", None)

        response = await api.post("/api/search/execute", json=EXECUTE)

        assert response.status_code == 400
        assert "Serper API key" in response.json()["detail"]
        assert broker == []
        assert (await db_session.execute(select(SearchSession))).first() is None

    async def test_broker_down_is_a_503_and_the_session_is_marked_failed(
        self, api, db_session, monkeypatch
    ):
        monkeypatch.setattr(settings, "serper_api_key", "test-key")

        def broken(*args, **kwargs):
            raise ConnectionError("redis is down")

        monkeypatch.setattr(search_tasks.run_search_session, "apply_async", broken)

        response = await api.post("/api/search/execute", json=EXECUTE)

        assert response.status_code == 503
        assert "queue is not available" in response.json()["detail"]
        (session,) = (await db_session.execute(select(SearchSession))).scalars().all()
        assert session.status == "failed" and session.error_message

    async def test_the_old_auto_scrape_fields_are_still_accepted_and_ignored(
        self, api, broker
    ):
        body = {**EXECUTE, "auto_scrape": True, "scrape_config": {"depth": 2}}

        response = await api.post("/api/search/execute", json=body)

        assert response.status_code == 202


@pytest.mark.asyncio
class TestRun:
    async def test_starts_a_search_again_after_it_failed(
        self, api, db_session, test_user, broker
    ):
        session = await make_session(
            db_session, test_user, status="failed", error_message="database gone"
        )

        response = await api.post(f"/api/search/session/{session.id}/queries/run")

        assert response.status_code == 202
        assert response.json()["queued"] == 1
        await db_session.refresh(session)
        assert session.status == "pending" and session.error_message is None
        assert len(broker) == 1

    async def test_takes_over_a_session_whose_worker_stopped_reporting(
        self, api, db_session, test_user, broker
    ):
        session = await make_session(
            db_session,
            test_user,
            status="processing",
            updated_at=datetime.utcnow() - stale_after() - timedelta(minutes=1),
        )
        query = (await db_session.execute(select(SearchQuery))).scalars().first()
        query.status = "processing"  # claimed by the dead worker
        await db_session.commit()

        response = await api.post(f"/api/search/session/{session.id}/queries/run")

        assert response.status_code == 202 and response.json()["queued"] == 1

    async def test_a_person_searching_again_starts_the_automatic_restart_count_afresh(
        self, api, db_session, test_user, broker
    ):
        session = await make_session(db_session, test_user, status="failed")
        session.config = {**session.config, "auto_restarts": 3}
        await db_session.commit()

        response = await api.post(f"/api/search/session/{session.id}/queries/run")

        assert response.status_code == 202
        await db_session.refresh(session)
        assert "auto_restarts" not in session.config

    async def test_refuses_while_a_worker_is_on_it(
        self, api, db_session, test_user, broker
    ):
        session = await make_session(
            db_session, test_user, status="processing", updated_at=datetime.utcnow()
        )

        response = await api.post(f"/api/search/session/{session.id}/queries/run")

        assert response.status_code == 409 and broker == []

    async def test_nothing_to_search_queues_nothing(
        self, api, db_session, test_user, broker
    ):
        session = await make_session(db_session, test_user)
        (query,) = (await db_session.execute(select(SearchQuery))).scalars().all()
        query.status = "completed"
        await db_session.commit()

        response = await api.post(f"/api/search/session/{session.id}/queries/run")

        assert response.status_code == 200
        assert response.json()["queued"] == 0 and broker == []

    async def test_broker_down_is_a_503(self, api, db_session, test_user, monkeypatch):
        monkeypatch.setattr(settings, "serper_api_key", "test-key")
        session = await make_session(db_session, test_user)

        def broken(*args, **kwargs):
            raise ConnectionError("redis is down")

        monkeypatch.setattr(search_tasks.run_search_session, "apply_async", broken)

        response = await api.post(f"/api/search/session/{session.id}/queries/run")

        assert response.status_code == 503
        await db_session.refresh(session)
        assert session.status == "failed"


@pytest.mark.asyncio
class TestProgress:
    async def test_reports_status_and_counts(self, api, db_session, test_user):
        session = await make_session(
            db_session, test_user, status="processing", keywords=("a", "b", "c")
        )
        a, b, c = (
            (await db_session.execute(select(SearchQuery).order_by(SearchQuery.id)))
            .scalars()
            .all()
        )
        a.status, a.result_count = "completed", 12
        b.status = "processing"
        c.status = "failed"
        await db_session.commit()

        response = await api.get(f"/api/search/session/{session.id}/progress")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "processing"
        assert (
            body["total"],
            body["completed"],
            body["processing"],
            body["failed"],
            body["pending"],
        ) == (3, 1, 1, 1, 0)
        assert body["results"] == 12 and body["stale"] is False

    async def test_shows_why_a_search_failed(self, api, db_session, test_user):
        session = await make_session(
            db_session, test_user, status="failed", error_message="database gone"
        )

        body = (await api.get(f"/api/search/session/{session.id}/progress")).json()

        assert body["status"] == "failed" and body["error_message"] == "database gone"

    async def test_other_users_session_is_404(self, api, db_session, test_admin):
        foreign = await make_session(db_session, test_admin)

        response = await api.get(f"/api/search/session/{foreign.id}/progress")

        assert response.status_code == 404


@pytest.mark.asyncio
class TestDelete:
    async def test_a_session_being_searched_cannot_be_deleted(
        self, api, db_session, test_user
    ):
        session = await make_session(
            db_session, test_user, status="processing", updated_at=datetime.utcnow()
        )

        response = await api.delete(f"/api/search/session/{session.id}")

        assert response.status_code == 409
        assert await db_session.get(SearchSession, session.id) is not None

    async def test_a_queued_session_cannot_be_deleted(self, api, db_session, test_user):
        session = await make_session(
            db_session, test_user, status="pending", celery_task_id="t"
        )

        assert (
            await api.delete(f"/api/search/session/{session.id}")
        ).status_code == 409

    async def test_a_stale_or_finished_session_can_be(self, api, db_session, test_user):
        stale = await make_session(
            db_session,
            test_user,
            status="processing",
            updated_at=datetime.utcnow() - stale_after() - timedelta(minutes=1),
        )
        done = await make_session(db_session, test_user, status="completed")

        assert (await api.delete(f"/api/search/session/{stale.id}")).status_code == 204
        assert (await api.delete(f"/api/search/session/{done.id}")).status_code == 204
