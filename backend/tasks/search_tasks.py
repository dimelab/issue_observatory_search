"""Celery task that searches the keywords of a search session.

The web request only queues the session (SearchService.start); a search worker
does the searching, so a search survives the user closing the page and a restart
of the web server, and the page follows its progress by polling.

The task is safe to run more than once for a session. A worker that is killed
(a container stopped hard, an out-of-memory kill) does NOT get its task delivered
again soon: Redis holds an unacknowledged task for the visibility timeout (hours).
Instead, recover_stalled_searches (Celery beat, every minute) queues a session
again once its heartbeat has lapsed, with a new task id; it carries on with the
keywords that were not stored, and the old task, if it is ever delivered, finds
itself superseded. A session's keywords are stored one at a time, so nothing is
stored twice.
"""

import asyncio
import contextlib
import logging
from datetime import datetime
from typing import Any, Coroutine, Optional, TypeVar

from sqlalchemy import select, update

from backend.celery_app import celery_app
from backend.config import settings
from backend.core.concurrency import RedisLimits
from backend.database import AsyncSessionLocal
from backend.models.search import SearchSession
from backend.models.user import User
from backend.services.search_service import (
    SearchQueueError,
    SearchService,
    heartbeat_every,
    stale_after,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Seconds a task waits before asking again when its session, or the user's other
# search, is still running
REQUEUE_DELAY = 15

# How many times the recovery task restarts a session whose worker was lost before it gives up
MAX_AUTO_RESTARTS = 3

# Longest a search task may run, seconds. The broker's visibility timeout
# (celery_app) is longer, or the task would be handed to a second worker.
SEARCH_TIME_LIMIT = 4 * 3600


def _run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine to completion on a fresh event loop.

    A pool child also runs other tasks, which close their loop when done, so
    asyncio.get_event_loop() can return a closed loop. Every task gets its own.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def build_limits() -> Optional[RedisLimits]:
    """The limits shared by all search workers, kept in Redis."""
    return RedisLimits(str(settings.redis_url))


async def _heartbeat(session_id: int) -> None:
    """Keep the session's updated_at fresh while its search runs.

    Its own database session: it must not wait for, or disturb, the one the
    search is storing results with.
    """
    while True:
        await asyncio.sleep(heartbeat_every())
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(SearchSession)
                    .where(
                        SearchSession.id == session_id,
                        SearchSession.status == "processing",
                    )
                    .values(updated_at=datetime.utcnow())
                )
                await db.commit()
        except Exception as e:  # a missed beat is harmless; stale needs several
            logger.warning(f"Heartbeat for search session {session_id} failed: {e}")


async def _run_session(session_id: int, task_id: str) -> str:
    """Search one session. Returns what became of it: "completed", "failed",
    or why nothing was done ("wait", "done", "superseded", "missing")."""
    limits = build_limits()
    try:
        async with AsyncSessionLocal() as db:
            session = await db.get(SearchSession, session_id)
            if session is None:
                logger.warning(f"Search session {session_id} no longer exists")
                return "missing"
            user = await db.get(User, session.user_id)
            service = SearchService(db, user, limits=limits)

            verdict = await service.admit_session(session, task_id)
            if verdict != "run":
                logger.info(f"Search session {session_id}: {verdict}")
                return verdict

            logger.info(f"Searching session {session_id} (task {task_id})")
            heartbeat = asyncio.create_task(_heartbeat(session_id))
            try:
                await service.run_pending_queries(session)
                await service.finish_session(session)
                return "completed"
            except Exception as e:
                logger.exception(f"Search session {session_id} failed")
                await service.finish_session(session, error=str(e) or type(e).__name__)
                return "failed"
            finally:
                heartbeat.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat
    finally:
        if limits is not None:
            await limits.close()


async def _recover_stalled() -> list[int]:
    """Restart the sessions whose worker was lost: "processing" without a heartbeat for stale_after().

    Redis keeps a task that was running when its worker was killed as "unacknowledged"
    until the visibility timeout (hours), so it is not redelivered in time to matter.
    Queued again with a new task id, the session carries on with the keywords that were
    not stored; the old task, if it is ever delivered, finds itself superseded.

    Returns:
        list[int]: Ids of the sessions queued again
    """
    restarted: list[int] = []
    async with AsyncSessionLocal() as db:
        cutoff = datetime.utcnow() - stale_after()
        found = await db.execute(
            select(SearchSession.id)
            .where(
                SearchSession.status == "processing", SearchSession.updated_at < cutoff
            )
            .order_by(SearchSession.id)
            .limit(50)
        )
        for session_id in found.scalars().all():
            # populate_existing: look again, the session may have reported in since
            session = await db.get(SearchSession, session_id, populate_existing=True)
            if (
                session is None
                or session.status != "processing"
                or session.updated_at >= cutoff
            ):
                continue
            user = await db.get(User, session.user_id)
            service = SearchService(db, user)

            config = dict(session.config or {})
            restarts = int(config.get("auto_restarts", 0))
            if restarts >= MAX_AUTO_RESTARTS:
                logger.error(
                    f"Search session {session_id} lost its worker {restarts} times; giving up"
                )
                await service.finish_session(
                    session,
                    error="The search stopped repeatedly because its worker was lost, "
                    "and was not restarted again. Search again to retry.",
                )
                continue

            config["auto_restarts"] = restarts + 1
            session.config = config
            try:
                await service.start(session)
            except SearchQueueError:
                logger.error(
                    "Could not restart search sessions: the queue is not available"
                )
                break
            logger.warning(
                f"Search session {session_id} lost its worker; queued again "
                f"(restart {restarts + 1}/{MAX_AUTO_RESTARTS})"
            )
            restarted.append(session_id)
    return restarted


@celery_app.task(
    bind=True,
    name="backend.tasks.search_tasks.run_search_session",
    max_retries=None,  # waiting for the user's other search is not an error
    time_limit=SEARCH_TIME_LIMIT,
    ignore_result=True,  # progress lives in the database; nobody reads a task result
)
def run_search_session(self, session_id: int) -> dict:
    """
    Search the pending keywords of a session and store the results.

    Args:
        session_id: SearchSession ID

    Returns:
        dict: session_id and outcome ("completed", "failed", "done",
            "superseded" or "missing")
    """
    outcome = _run_async(_run_session(session_id, self.request.id))
    if outcome == "wait":
        raise self.retry(countdown=REQUEUE_DELAY)
    return {"session_id": session_id, "outcome": outcome}


@celery_app.task(
    name="backend.tasks.search_tasks.recover_stalled_searches",
    ignore_result=True,
    time_limit=300,
)
def recover_stalled_searches() -> dict:
    """
    Queue again the searches whose worker was lost (run every minute by Celery beat,
    on the default queue so that a worker busy with long searches cannot delay it).

    Returns:
        dict: restarted (the session ids)
    """
    return {"restarted": _run_async(_recover_stalled())}
