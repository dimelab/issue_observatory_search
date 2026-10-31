"""Tests for searching keywords at the same time and for Google redirect links.

A Serper search waits about 30 seconds for Google to release result links beyond
the top three, so SearchService searches a few keywords at once and stores the
results afterwards, one keyword at a time, in keyword order.
"""

import asyncio
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import select

from backend.config import settings
from backend.core.search_engines.base import SearchResult as EngineResult
from backend.models.search import SearchQuery, SearchResult, SearchSession
from backend.services import search_service
from backend.services.search_service import SearchService

REAL_SLEEP = asyncio.sleep


class SlowEngine:
    """Search engine double that waits, and records how many searches overlap."""

    name = "serper"

    def __init__(self, urls_by_query, delays=None, default_delay=0.02):
        self.urls_by_query = urls_by_query
        self.delays = delays or {}
        self.default_delay = default_delay
        self.calls = []
        self.started_at = {}
        self.finished_at = {}
        self.finished = []
        self.in_flight = 0
        self.max_in_flight = 0

    async def search(self, query, max_results, hl, gl):
        self.calls.append(query)
        self.started_at[query] = asyncio.get_running_loop().time()
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await REAL_SLEEP(self.delays.get(query, self.default_delay))
            if query == "bad":
                raise RuntimeError("quota exceeded")
            self.finished.append(query)
            self.finished_at[query] = asyncio.get_running_loop().time()
            urls = self.urls_by_query.get(query, [f"https://{query}.dk/page"])
            return [
                EngineResult(
                    url=url,
                    title=f"Title {rank}",
                    description="d",
                    rank=rank,
                    domain=url.split("/")[2],
                )
                for rank, url in enumerate(urls, start=1)
            ]
        finally:
            self.in_flight -= 1


@pytest.fixture
def use_engine(monkeypatch):
    def install(engine):
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


async def stored_urls(db_session, session):
    result = await db_session.execute(
        select(SearchResult.url)
        .join(SearchQuery, SearchResult.query_id == SearchQuery.id)
        .where(SearchQuery.session_id == session.id)
    )
    return sorted(result.scalars().all())


async def run_search(db_session, test_user, queries):
    service = SearchService(db_session, test_user)
    session, _ = await service.queue_session(
        "S",
        queries,
        {
            "search_engine": "serper",
            "max_results": 10,
            "language": "da",
            "country": "dk",
            "allowed_domains": None,
        },
    )
    await service.run_pending_queries(session)
    await service.finish_session(session)
    return session


@pytest.mark.asyncio
class TestKeywordsSearchedTogether:
    async def test_up_to_the_limit_run_at_the_same_time(
        self, db_session, test_user, use_engine, monkeypatch
    ):
        monkeypatch.setattr(settings, "search_concurrency", 5)
        engine = use_engine(SlowEngine({}))
        keywords = [f"kw{i}" for i in range(12)]

        session = await run_search(db_session, test_user, keywords)

        assert engine.max_in_flight == 5
        assert sorted(engine.calls) == sorted(keywords)
        assert [q.status for q in await queries_of(db_session, session)] == [
            "completed"
        ] * 12

    async def test_default_limit_is_twenty(self, db_session, test_user, use_engine):
        assert settings.search_concurrency == 20
        engine = use_engine(SlowEngine({}))

        await run_search(db_session, test_user, [f"kw{i}" for i in range(25)])

        assert engine.max_in_flight == 20

    async def test_limit_can_be_changed(
        self, db_session, test_user, use_engine, monkeypatch
    ):
        monkeypatch.setattr(settings, "search_concurrency", 2)
        engine = use_engine(SlowEngine({}))

        await run_search(db_session, test_user, [f"kw{i}" for i in range(5)])

        assert engine.max_in_flight == 2

    async def test_a_slow_keyword_does_not_hold_back_the_ones_behind_it(
        self, db_session, test_user, use_engine, monkeypatch
    ):
        # Window of 2: "slow" takes 0.4 s, the others 0.02 s. In batches of two the third
        # keyword would wait for "slow"; in a sliding window it starts as soon as "fast1" is done.
        monkeypatch.setattr(settings, "search_concurrency", 2)
        engine = use_engine(SlowEngine({}, delays={"slow": 0.4}, default_delay=0.02))

        await run_search(db_session, test_user, ["slow", "fast1", "fast2", "fast3"])

        assert engine.started_at["fast2"] < engine.finished_at["slow"]
        assert engine.started_at["fast3"] < engine.finished_at["slow"]
        assert engine.max_in_flight == 2

    async def test_results_are_stored_in_keyword_order_not_finishing_order(
        self, db_session, test_user, use_engine
    ):
        shared = "https://shared.dk/page"
        engine = use_engine(
            SlowEngine(
                {
                    "first": [shared, "https://one.dk/x"],
                    "second": [shared, "https://two.dk/y"],
                },
                delays={"first": 0.15, "second": 0.0},
            )
        )

        session = await run_search(db_session, test_user, ["first", "second"])

        assert engine.finished == [
            "second",
            "first",
        ]  # the later keyword answered first
        by_text = {q.query_text: q for q in await queries_of(db_session, session)}
        assert by_text["first"].result_count == 2  # it keeps the shared page
        assert by_text["second"].result_count == 1

    async def test_a_failing_keyword_does_not_stop_the_others(
        self, db_session, test_user, use_engine
    ):
        use_engine(SlowEngine({}))

        session = await run_search(db_session, test_user, ["one", "bad", "two"])

        by_text = {q.query_text: q for q in await queries_of(db_session, session)}
        assert by_text["bad"].status == "failed"
        assert "quota exceeded" in by_text["bad"].error_message
        assert by_text["one"].status == by_text["two"].status == "completed"
        assert session.status == "completed"

    async def test_queued_keywords_run_at_the_same_time_too(
        self, db_session, test_user, use_engine, monkeypatch
    ):
        monkeypatch.setattr(settings, "search_concurrency", 5)
        engine = use_engine(SlowEngine({}))
        service = SearchService(db_session, test_user)
        session = await service.create_session(
            "S",
            config={
                "search_engine": "serper",
                "max_results": 5,
                "language": "da",
                "country": "dk",
            },
        )
        await service.add_queries(session, [f"kw{i}" for i in range(7)])

        summary = await service.run_pending_queries(session)

        assert engine.max_in_flight == 5
        assert (
            summary["queries_run"],
            summary["queries_failed"],
            summary["new_results"],
        ) == (7, 0, 7)

    async def test_searches_are_stopped_when_storing_fails(
        self, db_session, test_user, use_engine, monkeypatch
    ):
        engine = use_engine(
            SlowEngine({}, delays={"b": 5.0, "c": 5.0}, default_delay=0.0)
        )

        async def broken(self, *args, **kwargs):
            raise RuntimeError("database gone")

        monkeypatch.setattr(SearchService, "_run_query", broken)

        with pytest.raises(RuntimeError, match="database gone"):
            await run_search(db_session, test_user, ["a", "b", "c"])

        await REAL_SLEEP(0.05)
        assert engine.in_flight == 0  # "b" and "c" were cancelled, not left running
        assert engine.finished == ["a"]


@pytest.mark.asyncio
class TestRedirectLinksAreNeverStored:
    async def test_unresolved_google_redirects_are_skipped(
        self, db_session, test_user, use_engine
    ):
        engine = use_engine(
            SlowEngine(
                {
                    "kw": [
                        "https://real.dk/page",
                        "https://www.google.com/goto?url=CAES1",
                        "https://www.google.dk/goto?url=CAES2",
                        "https://www.google.com/maps/place/Aarhus",
                    ]
                }
            )
        )

        session = await run_search(db_session, test_user, ["kw"])

        (query,) = await queries_of(db_session, session)
        assert query.result_count == 2
        assert await stored_urls(db_session, session) == [
            "https://real.dk/page",
            "https://www.google.com/maps/place/Aarhus",
        ]
        assert engine.calls == ["kw"]

    async def test_redirects_do_not_count_as_duplicates_of_each_other(
        self, db_session, test_user, use_engine
    ):
        # Two different keywords each return a redirect; neither may be stored,
        # and neither may use up the other's real result.
        use_engine(
            SlowEngine(
                {
                    "a": ["https://www.google.com/goto?url=X", "https://a.dk/1"],
                    "b": ["https://www.google.com/goto?url=Y", "https://b.dk/1"],
                }
            )
        )

        session = await run_search(db_session, test_user, ["a", "b"])

        assert await stored_urls(db_session, session) == [
            "https://a.dk/1",
            "https://b.dk/1",
        ]


def load_script():
    """scripts/ is not a package: load find_redirect_results.py by path."""
    path = Path(__file__).parent.parent / "scripts" / "find_redirect_results.py"
    spec = importlib.util.spec_from_file_location("find_redirect_results", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
class TestFindRedirectResultsScript:
    async def make_session(self, db_session, user, name, results_by_keyword):
        session = SearchSession(
            user_id=user.id, name=name, status="completed", config={}
        )
        db_session.add(session)
        await db_session.flush()
        for text, urls in results_by_keyword.items():
            query = SearchQuery(
                session_id=session.id,
                query_text=text,
                search_engine="serper",
                max_results=10,
                status="completed",
                result_count=len(urls),
            )
            db_session.add(query)
            await db_session.flush()
            for rank, url in enumerate(urls, start=1):
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

    async def test_lists_only_queries_with_redirect_links(
        self, db_session, test_user, test_admin
    ):
        script = load_script()
        affected = await self.make_session(
            db_session,
            test_user,
            "Affected",
            {
                "sexisme": [
                    "https://a.dk/1",
                    "https://www.google.com/goto?url=1",
                    "https://www.google.com/goto?url=2",
                ],
                "clean": ["https://b.dk/1", "https://www.google.com/maps/place/Aarhus"],
            },
        )
        await self.make_session(
            db_session, test_admin, "Fine", {"x": ["https://c.dk/1"]}
        )

        rows = await script.find_redirect_results(db_session)

        assert len(rows) == 1
        assert rows[0]["session_id"] == affected.id
        assert rows[0]["query_text"] == "sexisme"
        assert (rows[0]["redirects"], rows[0]["total"]) == (2, 3)

    async def test_can_be_limited_to_one_user(self, db_session, test_user, test_admin):
        script = load_script()
        redirect = {"kw": ["https://www.google.com/goto?url=1"]}
        await self.make_session(db_session, test_user, "Mine", redirect)
        await self.make_session(db_session, test_admin, "Theirs", redirect)

        rows = await script.find_redirect_results(db_session, user_id=test_admin.id)

        assert [row["session_name"] for row in rows] == ["Theirs"]

    async def test_nothing_found_prints_so(self, db_session, test_user, capsys):
        script = load_script()
        await self.make_session(
            db_session, test_user, "Fine", {"x": ["https://c.dk/1"]}
        )

        script.print_report(await script.find_redirect_results(db_session))

        assert (
            "No search results stored as Google redirect links"
            in capsys.readouterr().out
        )

    async def test_report_names_session_and_keyword(
        self, db_session, test_user, capsys
    ):
        script = load_script()
        await self.make_session(
            db_session,
            test_user,
            "Gender",
            {"sexisme": ["https://www.google.com/goto?url=1"]},
        )

        script.print_report(await script.find_redirect_results(db_session))

        out = capsys.readouterr().out
        assert (
            '"Gender"' in out
            and "'sexisme'" in out
            and "search these keywords again" in out
        )
