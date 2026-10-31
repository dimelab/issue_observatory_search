"""Limits shared by every worker process, kept in Redis.

A search worker runs several processes, and several users search at once, but
the Serper account behind them is one: it has one request rate and one pool of
slow /resolve calls. These limits count across all processes and hosts.

- ``slot``: a counting semaphore. Each holder leases its place with an expiry,
  so a process that is killed cannot keep a place forever.
- ``throttle``: a rate limit that paces requests evenly (N per second, with a small
  burst allowed) instead of letting N through in the same instant: a burst arrives
  bunched up at the other end, and would go over the limit of the API.

If Redis cannot be reached while a search is running, both carry on without
limiting and log it: a search should not fail because of its own rate limiter,
and the 429 handling of the engine remains as a second line of defence.
"""

import asyncio
import logging
import random
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

# KEYS[1] = sorted set of leases (score = expiry time); ARGV = now, limit, lease, token
_ACQUIRE_SLOT = """
local now = tonumber(ARGV[1])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
if redis.call('ZCARD', KEYS[1]) < tonumber(ARGV[2]) then
    redis.call('ZADD', KEYS[1], now + tonumber(ARGV[3]), ARGV[4])
    redis.call('EXPIRE', KEYS[1], math.ceil(tonumber(ARGV[3])) + 60)
    return 1
end
return 0
"""

# Pacing (GCRA). KEYS[1] holds the time, in ms, at which the next request is "due".
# ARGV = now_ms, interval_ms (1000 / limit), tolerance_ms ((burst - 1) * interval).
# A request may go ahead when it is no more than `tolerance` early. Returns 0 when it
# may, else the milliseconds to wait before asking again.
_ACQUIRE_RATE = """
local now = tonumber(ARGV[1])
local interval = tonumber(ARGV[2])
local tolerance = tonumber(ARGV[3])
local due = tonumber(redis.call('GET', KEYS[1]) or now)
if due < now then due = now end
local wait = due - now - tolerance
if wait > 0 then
    return math.ceil(wait)
end
redis.call('SET', KEYS[1], tostring(due + interval), 'PX', math.ceil(tolerance + interval) + 1000)
return 0
"""

# How often a Redis problem is logged, seconds: a long search would otherwise log it per request
_WARN_EVERY = 60.0


class RedisLimits:
    """Cross-process slots and rate limits for calls to an external API."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        client: Optional[Redis] = None,
        prefix: str = "limits",
    ) -> None:
        """
        Args:
            redis_url: Redis to keep the counters in (ignored if client is given)
            client: An existing client, for tests
            prefix: Prefix for the Redis keys
        """
        if client is None:
            if not redis_url:
                raise ValueError("RedisLimits needs a redis_url or a client")
            client = Redis.from_url(
                redis_url, socket_connect_timeout=2, socket_timeout=5
            )
        self._redis = client
        self._prefix = prefix
        self._slot_script = client.register_script(_ACQUIRE_SLOT)
        self._rate_script = client.register_script(_ACQUIRE_RATE)
        self._last_warning = 0.0

    async def close(self) -> None:
        """Close the Redis connection."""
        try:
            await self._redis.close()
        except Exception:  # closing must never hide the real outcome of a search
            pass

    def _warn(self, error: Exception) -> None:
        now = time.monotonic()
        if now - self._last_warning > _WARN_EVERY:
            self._last_warning = now
            logger.warning(
                f"Redis limits unavailable ({error!r}); carrying on without them"
            )

    async def _try_acquire_slot(
        self, name: str, limit: int, lease: float, token: str
    ) -> bool:
        """One attempt to take a place; True if it was free."""
        got = await self._slot_script(
            keys=[f"{self._prefix}:slot:{name}"],
            args=[time.time(), limit, lease, token],
        )
        return bool(got)

    @asynccontextmanager
    async def slot(
        self, name: str, limit: int, lease: float = 300.0
    ) -> AsyncIterator[None]:
        """
        Hold one of ``limit`` places for as long as the block runs.

        Waits while all places are taken. The place is leased for ``lease``
        seconds, so make that longer than the block can take; if the process
        dies the place frees itself when the lease runs out.

        Args:
            name: Which limit (shared by every caller using the same name)
            limit: How many may hold a place at the same time
            lease: Seconds after which an unreleased place is given up
        """
        token = uuid.uuid4().hex
        held = False
        while True:
            try:
                if await self._try_acquire_slot(name, limit, lease, token):
                    held = True
                    break
            except (RedisError, OSError, asyncio.TimeoutError) as e:
                self._warn(e)
                break  # carry on without the limit
            await asyncio.sleep(random.uniform(0.05, 0.25))

        try:
            yield
        finally:
            if held:
                try:
                    await self._redis.zrem(f"{self._prefix}:slot:{name}", token)
                except (RedisError, OSError, asyncio.TimeoutError):
                    pass  # the lease expires on its own

    async def throttle(self, name: str, per_second: int, burst: int = 3) -> None:
        """
        Wait until a request is allowed: ``per_second`` requests a second on
        average, counted across all processes, spaced out evenly, with at most
        ``burst`` allowed back to back. Call it once per request.

        Args:
            name: Which limit (shared by every caller using the same name)
            per_second: Requests allowed per second
            burst: How many may go at the same moment after a quiet spell
        """
        interval_ms = 1000.0 / per_second
        tolerance_ms = (min(burst, per_second) - 1) * interval_ms
        while True:
            try:
                wait_ms = await self._rate_script(
                    keys=[f"{self._prefix}:rate:{name}"],
                    args=[time.time() * 1000, interval_ms, tolerance_ms],
                )
            except (RedisError, OSError, asyncio.TimeoutError) as e:
                self._warn(e)
                return
            if not wait_ms:
                return
            await asyncio.sleep(int(wait_ms) / 1000 + random.uniform(0, 0.005))
