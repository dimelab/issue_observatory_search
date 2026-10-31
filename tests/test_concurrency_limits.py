"""Tests for the Redis-backed slots and rate limit (run on fakeredis with Lua)."""

import asyncio
import os
import time
import uuid

import pytest
from fakeredis import FakeAsyncRedis
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from backend.core.concurrency import RedisLimits


@pytest.fixture(params=["fakeredis", "redis"])
async def limits(request):
    """The limits on fakeredis, and on a real Redis when TEST_REDIS_URL is set."""
    if request.param == "fakeredis":
        client = FakeAsyncRedis()
        prefix = "test"
    else:
        url = os.environ.get("TEST_REDIS_URL")
        if not url:
            pytest.skip(
                "set TEST_REDIS_URL (for example redis://localhost:6379/11) to test on a real Redis"
            )
        client = Redis.from_url(url)
        prefix = f"test-{uuid.uuid4().hex}"  # nothing else in that database is touched
    yield RedisLimits(client=client, prefix=prefix)
    async for key in client.scan_iter(match=f"{prefix}:*"):
        await client.delete(key)
    await client.close()


@pytest.mark.asyncio
class TestSlots:
    async def test_no_more_than_the_limit_hold_a_slot(self, limits):
        inside = peak = 0

        async def work():
            nonlocal inside, peak
            async with limits.slot("a", limit=3):
                inside += 1
                peak = max(peak, inside)
                await asyncio.sleep(0.03)
                inside -= 1

        await asyncio.gather(*(work() for _ in range(12)))

        assert peak == 3

    async def test_a_released_slot_can_be_taken_again(self, limits):
        async with limits.slot("a", limit=1):
            assert not await limits._try_acquire_slot("a", 1, 60, "other")
        assert await limits._try_acquire_slot("a", 1, 60, "other")

    async def test_slot_is_released_when_the_block_fails(self, limits):
        with pytest.raises(RuntimeError):
            async with limits.slot("a", limit=1):
                raise RuntimeError("boom")

        assert await limits._try_acquire_slot("a", 1, 60, "other")

    async def test_names_are_independent(self, limits):
        async with limits.slot("a", limit=1):
            assert await limits._try_acquire_slot("b", 1, 60, "other")

    async def test_a_lease_expires_when_its_holder_dies(self, limits):
        # a process that was killed never releases: its place must free itself
        assert await limits._try_acquire_slot("a", 2, 0.1, "dead-1")
        assert await limits._try_acquire_slot("a", 2, 0.1, "dead-2")
        assert not await limits._try_acquire_slot("a", 2, 0.1, "live")

        await asyncio.sleep(0.15)

        assert await limits._try_acquire_slot("a", 2, 60, "live")

    async def test_waiting_caller_gets_in_when_a_lease_expires(self, limits):
        assert await limits._try_acquire_slot("a", 1, 0.2, "dead")

        started = time.monotonic()
        async with limits.slot("a", limit=1):
            waited = time.monotonic() - started

        assert 0.1 < waited < 1.0


@pytest.mark.asyncio
class TestThrottle:
    async def test_requests_are_spaced_evenly_after_a_small_burst(self, limits):
        stamps = []

        async def call():
            await limits.throttle("r", per_second=10, burst=2)
            stamps.append(time.monotonic())

        await asyncio.gather(*(call() for _ in range(20)))

        stamps.sort()
        gaps = [
            b - a for a, b in zip(stamps[1:], stamps[2:])
        ]  # after the first two (the burst)
        assert min(gaps) >= 0.07  # one every 0.1 s, not ten at once
        assert (
            stamps[-1] - stamps[0] >= 1.6
        )  # 18 requests after the burst at 10 a second

    async def test_never_more_than_the_rate_plus_the_burst_in_any_second(self, limits):
        stamps = []

        async def call():
            await limits.throttle("r", per_second=10, burst=3)
            stamps.append(time.monotonic())

        await asyncio.gather(*(call() for _ in range(25)))

        stamps.sort()
        for i, start in enumerate(stamps):
            in_window = [s for s in stamps[i:] if s < start + 1.0]
            assert (
                len(in_window) <= 10 + 3
            ), "more than the rate plus the burst inside one second"

    async def test_a_quiet_spell_earns_the_burst_back(self, limits):
        for _ in range(3):
            await limits.throttle("r", per_second=20, burst=3)  # spends the burst
        await asyncio.sleep(0.2)
        started = time.monotonic()

        for _ in range(3):
            await limits.throttle("r", per_second=20, burst=3)

        assert time.monotonic() - started < 0.1

    async def test_requests_under_the_limit_do_not_wait(self, limits):
        started = time.monotonic()

        for _ in range(4):
            await limits.throttle("r", per_second=10)

        assert time.monotonic() - started < 0.2

    async def test_names_are_independent(self, limits):
        for _ in range(3):
            await limits.throttle("a", per_second=3)
        started = time.monotonic()

        await limits.throttle("b", per_second=3)

        assert time.monotonic() - started < 0.2


class BrokenRedis(FakeAsyncRedis):
    """Every script call fails, as when Redis is down in the middle of a search."""

    def register_script(self, script):
        async def broken(*args, **kwargs):
            raise RedisConnectionError("redis is down")

        return broken

    async def zrem(self, *args, **kwargs):
        raise RedisConnectionError("redis is down")


@pytest.mark.asyncio
class TestRedisDown:
    async def test_slot_carries_on_without_the_limit(self, caplog):
        limits = RedisLimits(client=BrokenRedis(), prefix="test")
        ran = []

        async with limits.slot("a", limit=1):
            ran.append(1)
        async with limits.slot("a", limit=1):  # a second one is not blocked either
            ran.append(2)

        assert ran == [1, 2]
        assert "Redis limits unavailable" in caplog.text

    async def test_throttle_returns_at_once(self):
        limits = RedisLimits(client=BrokenRedis(), prefix="test")
        started = time.monotonic()

        for _ in range(20):
            await limits.throttle("r", per_second=1)

        assert time.monotonic() - started < 0.5

    async def test_the_problem_is_logged_once_not_per_request(self, caplog):
        limits = RedisLimits(client=BrokenRedis(), prefix="test")

        for _ in range(10):
            await limits.throttle("r", per_second=1)

        assert caplog.text.count("Redis limits unavailable") == 1

    def test_needs_a_url_or_a_client(self):
        with pytest.raises(ValueError):
            RedisLimits()
