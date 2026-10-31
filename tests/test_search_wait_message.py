"""The search pages tell how long a Serper search takes: they need the server's concurrency."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.api.frontend import router as frontend_router
from backend.config import settings
from backend.database import get_db
from backend.models.search import SearchQuery, SearchSession
from backend.utils.dependencies import get_current_active_user


@pytest.fixture
async def pages(db_session, test_user):
    app = FastAPI()
    app.include_router(frontend_router)

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
async def serper_session(db_session, test_user):
    session = SearchSession(
        user_id=test_user.id,
        name="Gender",
        status="completed",
        config={"search_engine": "serper"},
    )
    db_session.add(session)
    await db_session.flush()
    for text in ("one", "two", "three"):
        db_session.add(
            SearchQuery(
                session_id=session.id,
                query_text=text,
                search_engine="serper",
                max_results=10,
                status="pending",
            )
        )
    await db_session.commit()
    return session


@pytest.mark.asyncio
class TestWaitMessage:
    async def test_new_search_page_gets_the_concurrency(self, pages, monkeypatch):
        monkeypatch.setattr(settings, "search_concurrency", 7)

        response = await pages.get("/search/new")

        assert response.status_code == 200
        assert "const SEARCH_CONCURRENCY = 7;" in response.text
        assert 'id="search-wait-note"' in response.text

    async def test_session_page_gets_the_concurrency_and_the_queued_count(
        self, pages, serper_session
    ):
        response = await pages.get(f"/search/session/{serper_session.id}")

        assert response.status_code == 200
        assert (
            f"const SEARCH_CONCURRENCY = {settings.search_concurrency};"
            in response.text
        )
        assert "const PENDING_KEYWORDS = 3;" in response.text
        assert 'id="run-pending-note"' in response.text

    async def test_other_engines_get_no_note(self, pages, db_session, serper_session):
        serper_session.config = {"search_engine": "google_custom"}
        await db_session.commit()

        response = await pages.get(f"/search/session/{serper_session.id}")

        assert response.status_code == 200
        assert 'id="run-pending-note"' not in response.text
