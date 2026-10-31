"""Tests for resolving Google redirect links (google.com/goto) in Serper results."""

import asyncio
from unittest.mock import patch

import pytest

from backend.core.search_engines.base import (
    SearchEngineAPIError,
    SearchEngineRateLimitError,
    is_google_redirect,
)
from backend.core.search_engines.serper import SerperSearch

REAL_SLEEP = (
    asyncio.sleep
)  # tests that patch asyncio.sleep must not slow or count the fake's own wait

SEARCH_URL = SerperSearch.API_URL
RESOLVE_URL = SerperSearch.RESOLVE_URL


def goto(n: int) -> str:
    """A Google redirect link as Serper returns them for results beyond the top three."""
    return f"https://www.google.com/goto?url=CAES{n}"


def real(n: int) -> str:
    return f"https://site{n}.dk/page"


def page(first: int, count: int, redirects_from: int = 3) -> dict:
    """A search response of `count` results; those from `redirects_from` on are redirects."""
    organic = []
    for i in range(count):
        n = first + i
        organic.append(
            {
                "title": f"Result {n}",
                "link": real(n) if i < redirects_from else goto(n),
                "snippet": f"About {n}",
            }
        )
    return {"organic": organic, "searchParameters": {"q": "test"}}


def resolved(data: dict) -> dict:
    """What /resolve answers: every redirect replaced by the real URL."""
    out = {**data, "organic": []}
    for result, n in zip(data["organic"], range(1000)):
        number = int(result["title"].split()[-1])
        out["organic"].append({**result, "link": real(number)})
    return out


class Response:
    """Just enough of an httpx response."""

    def __init__(self, data=None, status_code=200, text="", headers=None):
        self._data = data
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._data


class FakeSerper:
    """Stands in for httpx.AsyncClient.post: /search pages, then /resolve answers."""

    def __init__(self, pages, resolve=None):
        self.pages = pages  # one response per search page
        self.resolve = resolve or (lambda body, call: Response(resolved(body)))
        self.calls = []  # (url, body, headers)
        self.resolve_calls = 0
        self.in_flight = 0
        self.max_in_flight = 0

    async def post(self, url, json=None, headers=None, **kwargs):
        self.calls.append((url, json, headers))
        if url == SEARCH_URL:
            return Response(self.pages[json["page"] - 1])
        assert url == RESOLVE_URL
        self.resolve_calls += 1
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await REAL_SLEEP(0.05)  # Google makes /resolve wait
            return self.resolve(json, self.resolve_calls)
        finally:
            self.in_flight -= 1

    def resolve_bodies(self):
        return [body for url, body, _ in self.calls if url == RESOLVE_URL]


def make_engine(**kwargs):
    engine = SerperSearch(api_key="test_key", **kwargs)
    engine.RATE_LIMIT_BASE_WAIT = 0.0  # tests of a 429 should not really wait
    return engine


async def search(fake, max_results=10, **engine_kwargs):
    engine = make_engine(**engine_kwargs)
    with patch("httpx.AsyncClient.post", side_effect=fake.post):
        return await engine.search("test", max_results=max_results)


class TestIsGoogleRedirect:
    @pytest.mark.parametrize(
        "url",
        [
            "https://www.google.com/goto?url=CAESabc",
            "https://google.com/goto?url=x",
            "http://www.google.dk/goto?url=x",
            "https://www.google.co.uk/goto/anything",
            "https://WWW.GOOGLE.COM:443/goto?url=x",
        ],
    )
    def test_redirects(self, url):
        assert is_google_redirect(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/goto?url=x",  # /goto on another site
            "https://www.google.com/maps/place/Aarhus",
            "https://docs.google.com/document/d/1/goto",
            "https://notgoogle.com/goto?url=x",
            "https://www.google.com.evil.dk/goto?url=x",
            "https://example.dk/google.com/goto",
            "",
            "not a url",
        ],
    )
    def test_everything_else(self, url):
        assert is_google_redirect(url) is False


@pytest.mark.asyncio
class TestResolveLinks:
    async def test_redirects_are_replaced_by_the_real_urls(self):
        fake = FakeSerper([page(1, 8)])

        results = await search(fake)

        assert [r.url for r in results] == [real(n) for n in range(1, 9)]
        assert [r.rank for r in results] == list(range(1, 9))
        assert [r.domain for r in results] == [f"site{n}.dk" for n in range(1, 9)]
        assert [r.title for r in results][:2] == ["Result 1", "Result 2"]

    async def test_whole_search_response_is_sent_with_the_api_key(self):
        first_page = page(1, 6)
        fake = FakeSerper([first_page])

        await search(fake)

        assert fake.resolve_calls == 1
        url, body, headers = [c for c in fake.calls if c[0] == RESOLVE_URL][0]
        assert body == first_page
        assert headers["X-API-KEY"] == "test_key"

    async def test_no_resolve_call_when_every_link_is_real(self):
        fake = FakeSerper([page(1, 3)])

        results = await search(fake)

        assert len(results) == 3
        assert fake.resolve_calls == 0

    async def test_other_google_links_are_kept_as_results(self):
        data = {
            "organic": [
                {"title": "Map", "link": "https://www.google.com/maps/place/Aarhus"},
                {"title": "Doc", "link": "https://docs.google.com/document/d/1/edit"},
            ]
        }
        fake = FakeSerper([data])

        results = await search(fake)

        assert [r.url for r in results] == [o["link"] for o in data["organic"]]
        assert fake.resolve_calls == 0

    async def test_pages_are_resolved_at_the_same_time(self):
        fake = FakeSerper([page(1, 10), page(11, 10, redirects_from=0)])

        results = await search(fake, max_results=20)

        assert [r.url for r in results] == [real(n) for n in range(1, 21)]
        assert fake.resolve_calls == 2
        assert fake.max_in_flight == 2  # not one after the other

    async def test_only_pages_with_redirects_are_sent(self):
        fake = FakeSerper(
            [page(1, 10, redirects_from=10), page(11, 10, redirects_from=5)]
        )

        await search(fake, max_results=20)

        assert fake.resolve_calls == 1
        assert fake.resolve_bodies()[0]["organic"][0]["title"] == "Result 11"

    async def test_max_results_still_caps_the_list(self):
        fake = FakeSerper([page(1, 10), page(11, 10, redirects_from=0)])

        results = await search(fake, max_results=14)

        assert len(results) == 14
        assert results[-1].url == real(14)


@pytest.mark.asyncio
class TestRetryAndUnresolved:
    async def test_retry_after_sends_the_answer_again_after_the_wait(self):
        def resolve(body, call):
            if call == 1:  # some links are not ready yet
                partly = resolved(body)
                partly["organic"][-1]["link"] = goto(99)
                partly["retryAfter"] = 7
                return Response(partly)
            return Response(resolved(body))

        fake = FakeSerper([page(1, 6)], resolve=resolve)
        sleeps = []

        async def no_sleep(seconds):
            sleeps.append(seconds)

        with patch("backend.core.search_engines.serper.asyncio.sleep", no_sleep):
            results = await search(fake)

        assert fake.resolve_calls == 2
        assert sleeps == [7.0]
        assert "retryAfter" not in fake.resolve_bodies()[1]
        assert fake.resolve_bodies()[1]["organic"][-1]["link"] == goto(
            99
        )  # what came back
        assert len(results) == 6 and all("google.com" not in r.url for r in results)

    async def test_links_still_unresolved_are_dropped_not_returned(self):
        def resolve(body, call):
            partly = resolved(body)
            partly["organic"][4]["link"] = goto(5)  # never gets ready
            partly["retryAfter"] = 1
            return Response(partly)

        fake = FakeSerper([page(1, 6)], resolve=resolve)

        async def no_sleep(seconds):
            pass

        with patch("backend.core.search_engines.serper.asyncio.sleep", no_sleep):
            results = await search(fake)

        assert fake.resolve_calls == SerperSearch.RESOLVE_MAX_ATTEMPTS
        assert [r.url for r in results] == [real(n) for n in (1, 2, 3, 4, 6)]
        assert [r.rank for r in results] == [1, 2, 3, 4, 5]

    async def test_wait_is_capped(self):
        def resolve(body, call):
            partly = resolved(body)
            partly["organic"][-1]["link"] = goto(9)
            partly["retryAfter"] = 100000
            return Response(partly)

        fake = FakeSerper([page(1, 5)], resolve=resolve)
        sleeps = []

        async def no_sleep(seconds):
            sleeps.append(seconds)

        with patch("backend.core.search_engines.serper.asyncio.sleep", no_sleep):
            await search(fake)

        assert sleeps and max(sleeps) == SerperSearch.RESOLVE_MAX_WAIT


@pytest.mark.asyncio
class TestResolveErrors:
    async def test_server_error_fails_the_search_with_a_clear_message(self):
        fake = FakeSerper(
            [page(1, 6)],
            resolve=lambda body, call: Response(status_code=500, text="boom"),
        )

        with pytest.raises(
            SearchEngineAPIError, match="resolve failed with status 500"
        ):
            await search(fake)

    async def test_rate_limit_is_reported_as_such(self):
        fake = FakeSerper(
            [page(1, 6)], resolve=lambda body, call: Response(status_code=429)
        )

        with pytest.raises(SearchEngineRateLimitError, match="resolve rate limit"):
            await search(fake)

    async def test_bad_key_is_reported(self):
        fake = FakeSerper(
            [page(1, 6)], resolve=lambda body, call: Response(status_code=401)
        )

        with pytest.raises(SearchEngineAPIError, match="Invalid Serper API key"):
            await search(fake)

    async def test_timeout_fails_the_search_with_a_clear_message(self):
        import httpx

        def resolve(body, call):
            raise httpx.ReadTimeout("slow")

        fake = FakeSerper([page(1, 6)], resolve=resolve)

        with pytest.raises(SearchEngineAPIError, match="resolve timed out"):
            await search(fake)

    async def test_one_failing_page_fails_the_search_after_the_others_finish(self):
        def resolve(body, call):
            if body["organic"][0]["title"] == "Result 11":
                return Response(status_code=500, text="boom")
            return Response(resolved(body))

        fake = FakeSerper(
            [page(1, 10, redirects_from=2), page(11, 10, redirects_from=0)],
            resolve=resolve,
        )

        with pytest.raises(SearchEngineAPIError):
            await search(fake, max_results=20)

        assert fake.resolve_calls == 2 and fake.in_flight == 0


@pytest.mark.asyncio
class TestParallelSearches:
    async def test_resolve_requests_in_flight_are_capped_across_searches(self):
        fake = FakeSerper([page(1, 6)])
        engine = make_engine(resolve_concurrency=3)

        with patch("httpx.AsyncClient.post", side_effect=fake.post):
            results = await asyncio.gather(*(engine.search("test") for _ in range(10)))

        assert all(len(r) == 6 for r in results)
        assert fake.resolve_calls == 10
        assert fake.max_in_flight == 3

    async def test_all_run_at_once_when_the_cap_allows(self):
        fake = FakeSerper([page(1, 6)])
        engine = make_engine(resolve_concurrency=30)

        with patch("httpx.AsyncClient.post", side_effect=fake.post):
            await asyncio.gather(*(engine.search("test") for _ in range(10)))

        assert fake.max_in_flight == 10

    def test_connection_pool_is_large_enough_for_the_cap(self):
        engine = SerperSearch(api_key="test_key", resolve_concurrency=200)

        assert engine.limits.max_connections >= 200 + 50
        assert (
            engine.timeout_config.pool >= 60
        )  # waiting for a connection must outlast a /resolve

    def test_cap_is_at_least_one(self):
        assert (
            SerperSearch(api_key="test_key", resolve_concurrency=0).resolve_concurrency
            == 1
        )


@pytest.mark.asyncio
class TestRateLimitBackoff:
    async def test_resolve_429_is_waited_out_and_asked_again(self):
        def resolve(body, call):
            if call <= 2:
                return Response(status_code=429)
            return Response(resolved(body))

        fake = FakeSerper([page(1, 6)], resolve=resolve)

        results = await search(fake)

        assert fake.resolve_calls == 3
        assert len(results) == 6

    async def test_retry_after_header_sets_the_wait(self):
        def resolve(body, call):
            if call == 1:
                return Response(status_code=429, headers={"Retry-After": "5"})
            return Response(resolved(body))

        fake = FakeSerper([page(1, 6)], resolve=resolve)
        sleeps = []

        async def record(seconds):
            sleeps.append(seconds)

        with patch("backend.core.search_engines.serper.asyncio.sleep", record):
            await search(fake)

        assert sleeps == [5.0]

    async def test_wait_without_header_doubles_and_is_capped(self):
        engine = SerperSearch(api_key="test_key")
        sleeps = []

        async def record(seconds):
            sleeps.append(seconds)

        with patch("backend.core.search_engines.serper.asyncio.sleep", record):
            for attempt in (1, 2, 3):
                await engine._wait_after_rate_limit(
                    Response(status_code=429), attempt, "x"
                )
            engine.RATE_LIMIT_BASE_WAIT = 1000.0
            await engine._wait_after_rate_limit(Response(status_code=429), 1, "x")

        assert (
            2.0 <= sleeps[0] <= 3.0
            and 4.0 <= sleeps[1] <= 6.0
            and 8.0 <= sleeps[2] <= 12.0
        )
        assert sleeps[3] == SerperSearch.RESOLVE_MAX_WAIT

    async def test_gives_up_after_the_retries(self):
        fake = FakeSerper(
            [page(1, 6)], resolve=lambda body, call: Response(status_code=429)
        )

        with pytest.raises(SearchEngineRateLimitError, match="resolve rate limit"):
            await search(fake)

        assert fake.resolve_calls == SerperSearch.RATE_LIMIT_RETRIES + 1

    async def test_search_429_is_waited_out_and_asked_again(self):
        data = page(1, 3)
        calls = {"search": 0}

        class Flaky(FakeSerper):
            async def post(self, url, json=None, headers=None, **kwargs):
                if url == SEARCH_URL:
                    calls["search"] += 1
                    if calls["search"] == 1:
                        return Response(status_code=429)
                return await super().post(url, json=json, headers=headers, **kwargs)

        results = await search(Flaky([data]))

        assert calls["search"] == 2
        assert len(results) == 3


@pytest.mark.asyncio
class TestSharedLimits:
    """Limits kept in Redis hold across engine instances, as across worker processes."""

    @pytest.fixture(params=["fakeredis", "redis"])
    async def limits(self, request):
        import os
        import uuid

        from fakeredis import FakeAsyncRedis
        from redis.asyncio import Redis

        from backend.core.concurrency import RedisLimits

        if request.param == "fakeredis":
            client = FakeAsyncRedis()
            prefix = "test"
        else:
            url = os.environ.get("TEST_REDIS_URL")
            if not url:
                pytest.skip("set TEST_REDIS_URL to test on a real Redis")
            client = Redis.from_url(url)
            prefix = f"test-{uuid.uuid4().hex}"
        yield RedisLimits(client=client, prefix=prefix)
        async for key in client.scan_iter(match=f"{prefix}:*"):
            await client.delete(key)
        await client.close()

    def test_base_url_points_the_engine_elsewhere(self):
        engine = SerperSearch(api_key="k", base_url="http://fake.local:9000/")

        assert engine.API_URL == "http://fake.local:9000/search"
        assert engine.RESOLVE_URL == "http://fake.local:9000/resolve"
        assert (
            SerperSearch.API_URL == "https://google.serper.dev/search"
        )  # the class is untouched

    async def test_every_request_goes_through_the_rate_limit(self, limits):
        calls = []
        original = limits.throttle

        async def spy(name, per_second):
            calls.append((name, per_second))
            await original(name, per_second)

        limits.throttle = spy
        fake = FakeSerper([page(1, 10), page(11, 10, redirects_from=0)])
        engine = make_engine(limits=limits, rate_per_second=25)

        with patch("httpx.AsyncClient.post", side_effect=fake.post):
            await engine.search("test", max_results=20)

        # two search pages and two /resolve calls
        assert len(fake.calls) == 4
        assert calls == [("serper", 25)] * 4

    async def test_requests_per_second_hold_across_engines(self, limits):
        fake = FakeSerper([page(1, 3)])  # no redirects: only /search calls
        engines = [make_engine(limits=limits, rate_per_second=4) for _ in range(2)]

        started = asyncio.get_running_loop().time()
        with patch("httpx.AsyncClient.post", side_effect=fake.post):
            await asyncio.gather(*(engines[i % 2].search("test") for i in range(10)))
        elapsed = asyncio.get_running_loop().time() - started

        assert len(fake.calls) == 10
        assert elapsed >= 1.4  # 4 + 4 + 2 take three windows

    async def test_resolve_slots_are_shared_between_engines(self, limits):
        fake = FakeSerper([page(1, 6)])
        engines = [make_engine(limits=limits, resolve_concurrency=3) for _ in range(3)]

        with patch("httpx.AsyncClient.post", side_effect=fake.post):
            await asyncio.gather(*(engines[i % 3].search("test") for i in range(12)))

        # each engine alone would allow 3, so 9 across the three; the shared limit holds it to 3
        assert fake.resolve_calls == 12
        assert fake.max_in_flight == 3

    async def test_without_shared_limits_nothing_needs_redis(self):
        fake = FakeSerper([page(1, 6)])

        results = await search(fake)  # no limits passed

        assert len(results) == 6
