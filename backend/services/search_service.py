"""Search service for executing and managing searches."""
import asyncio
import contextlib
import hashlib
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Union
from urllib.parse import urlparse

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.core.concurrency import RedisLimits
from backend.core.search_engines.base import (
    SearchEngineBase,
    SearchResult as EngineSearchResult,
    is_google_redirect,
)
from backend.core.search_engines.google_custom import GoogleCustomSearch
from backend.core.search_engines.serper import SerperSearch
from backend.models.search import SearchSession, SearchQuery, SearchResult
from backend.models.user import User

logger = logging.getLogger(__name__)

# Fallbacks for sessions whose config lacks a value; same as SearchExecuteRequest.
DEFAULT_SEARCH_ENGINE = "google_custom"
DEFAULT_MAX_RESULTS = 10
DEFAULT_LANGUAGE = "da"
DEFAULT_COUNTRY = "dk"

# A search runs in a worker, which bumps its session's updated_at every heartbeat_every()
# seconds. A session that says "processing" but was not bumped for stale_after() lost its
# worker (crash, kill, restart) and may be taken over: the recovery task (search_tasks)
# restarts it, or the user can search again. A queued session whose task vanished from
# the queue (Redis wiped) is given up after QUEUED_STALE_AFTER so it can be started again.
QUEUED_STALE_AFTER = timedelta(hours=24)


def stale_after() -> timedelta:
    """How long a "processing" session may go without reporting before it counts as lost."""
    return timedelta(seconds=settings.search_stale_seconds)


def heartbeat_every() -> float:
    """Seconds between a running search's reports (a sixth of stale_after())."""
    return settings.search_stale_seconds / 6

# How long a keyword may hold one of the shared keyword slots before the lease runs out
KEYWORD_SLOT_LEASE = 900.0


class SearchQueueError(Exception):
    """The search could not be queued (the broker is not reachable)."""

class SearchService:
    """Service for managing search operations."""

    def __init__(
        self,
        db: AsyncSession,
        user: User,
        limits: Optional[RedisLimits] = None
    ) -> None:
        """
        Initialize search service.

        Args:
            db: Database session
            user: Current user
            limits: Limits shared by all workers (Redis); a search run by a
                worker passes them so several users stay within what the
                search account allows
        """
        self.db = db
        self.user = user
        self.limits = limits

    async def create_session(
        self,
        name: str,
        description: Optional[str] = None,
        config: Optional[dict] = None
    ) -> SearchSession:
        """
        Create a new search session.

        Args:
            name: Session name
            description: Optional description
            config: Optional configuration

        Returns:
            SearchSession: Created session
        """
        session = SearchSession(
            user_id=self.user.id,
            name=name,
            description=description,
            config=config,
            status="pending"
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        logger.info(f"Created search session {session.id} for user {self.user.id}")
        return session

    @staticmethod
    def is_stale(session: SearchSession, now: Optional[datetime] = None) -> bool:
        """Whether a session says "processing" but its worker stopped reporting."""
        now = now or datetime.utcnow()
        return session.status == "processing" and now - session.updated_at > stale_after()

    @staticmethod
    def is_busy(session: SearchSession, now: Optional[datetime] = None) -> bool:
        """
        Whether a search is running or waiting its turn for this session, so
        another must not be queued on top of it.
        """
        now = now or datetime.utcnow()
        if session.status == "processing":
            return now - session.updated_at <= stale_after()
        if session.status == "pending":
            return (
                session.celery_task_id is not None
                and now - session.updated_at <= QUEUED_STALE_AFTER
            )
        return False

    async def queue_session(
        self,
        name: str,
        queries: list[str],
        config: dict
    ) -> tuple[SearchSession, int]:
        """
        Create a session with its keywords waiting as "pending" queries.

        Nothing is searched here: start() queues the search for a worker.

        Args:
            name: Session name
            queries: Keywords (a keyword given twice is kept once)
            config: Session configuration (engine, max results, language,
                country, domain filter)

        Returns:
            tuple: (the session, how many keywords it holds)
        """
        session = await self.create_session(name=name, config=config)
        added, _ = await self.add_queries(session, queries)
        return session, len(added)

    def ensure_engine_configured(self, name: str) -> None:
        """
        Check that a search engine has its key, before a session is created.

        Raises:
            ValueError: If the engine is unknown or not configured
        """
        self._get_search_engine(name)

    async def count_unfinished_queries(self, session_id: int) -> int:
        """
        Count the keywords a search of the session would still do: pending
        ones, and ones a dead worker left claimed ("processing") when the
        session is not being searched.

        Args:
            session_id: Session ID

        Returns:
            int: Keywords in status "pending" or "processing"
        """
        result = await self.db.execute(
            select(func.count(SearchQuery.id)).where(
                SearchQuery.session_id == session_id,
                SearchQuery.status.in_(("pending", "processing"))
            )
        )
        return result.scalar() or 0

    async def ensure_engines_configured(self, session: SearchSession) -> None:
        """
        Check that every engine the session's pending keywords need has its
        key, so a missing key is reported to the user at once and not in a
        worker.

        Raises:
            ValueError: If an engine is not configured
        """
        names = await self.db.execute(
            select(SearchQuery.search_engine).where(
                SearchQuery.session_id == session.id,
                SearchQuery.status.in_(("pending", "processing"))
            ).distinct()
        )
        for name in names.scalars():
            self._get_search_engine(name)

    async def start(self, session: SearchSession) -> str:
        """
        Queue the session's pending keywords for a search worker.

        The session becomes "pending" ("queued") with the id of the task, which
        is stored before the task is sent so the worker finds it. If the broker
        cannot be reached the session is marked failed and SearchQueueError is
        raised.

        Args:
            session: Session to search

        Returns:
            str: The Celery task id

        Raises:
            SearchQueueError: If the task could not be queued
        """
        task_id = str(uuid.uuid4())
        session.status = "pending"
        session.celery_task_id = task_id
        session.error_message = None
        session.completed_at = None
        session.updated_at = datetime.utcnow()
        await self.db.commit()

        # Imported here: the task module imports this service
        from backend.tasks.search_tasks import run_search_session

        try:
            # apply_async talks to Redis synchronously: keep it off the event loop
            await asyncio.to_thread(
                run_search_session.apply_async,
                args=[session.id],
                task_id=task_id,
                queue="search",
                retry_policy={"max_retries": 1, "interval_start": 0, "interval_max": 0.5},
            )
        except Exception as e:
            logger.error(f"Could not queue search session {session.id}: {e}")
            session.status = "failed"
            session.error_message = (
                "The search queue is not available. Try again in a moment."
            )
            session.completed_at = datetime.utcnow()
            await self.db.commit()
            raise SearchQueueError(session.error_message) from e

        logger.info(f"Queued search session {session.id} as task {task_id}")
        return task_id

    async def admit_session(self, session: SearchSession, task_id: str) -> str:
        """
        Decide whether the task may start searching this session now.

        Called by the worker task each time it picks the session up. A user's
        sessions are admitted one at a time (settings.search_max_active_per_user)
        under a lock on the user's row, so two sessions cannot both slip in.

        Args:
            session: The session the task was queued for
            task_id: Id of the task asking

        Returns:
            str: "run" (the session is now "processing" and any keyword a dead
                run left claimed is pending again), "wait" (another search of
                this session, or of this user, is running: ask again later),
                "done" (nothing left to do) or "superseded" (a newer task was
                queued for the session)
        """
        # Serialise this user's admissions
        await self.db.execute(
            select(User.id).where(User.id == session.user_id).with_for_update()
        )
        await self.db.refresh(session)

        if session.celery_task_id and session.celery_task_id != task_id:
            await self.db.commit()  # releases the lock
            return "superseded"
        if session.status in ("completed", "failed"):
            await self.db.commit()  # releases the lock
            return "done"

        now = datetime.utcnow()
        if session.status == "processing" and not self.is_stale(session, now):
            await self.db.commit()  # releases the lock
            return "wait"  # another worker is on it (or has just lost it: wait for the heartbeat to lapse)

        running = await self.db.execute(
            select(func.count(SearchSession.id)).where(
                SearchSession.user_id == session.user_id,
                SearchSession.id != session.id,
                SearchSession.status == "processing",
                SearchSession.updated_at > now - stale_after()
            )
        )
        if (running.scalar() or 0) >= settings.search_max_active_per_user:
            await self.db.commit()  # releases the lock
            return "wait"

        session.status = "processing"
        session.error_message = None
        session.started_at = session.started_at or now
        session.updated_at = now
        await self.db.execute(
            update(SearchQuery)
            .where(SearchQuery.session_id == session.id, SearchQuery.status == "processing")
            .values(status="pending")
        )
        await self.db.commit()
        return "run"

    async def finish_session(
        self, session: SearchSession, error: Optional[str] = None
    ) -> None:
        """
        Close a session after its search: "completed" (keywords that failed
        are marked on the keywords themselves), or "failed" with the reason.
        On failure, keywords still claimed go back to "pending" so searching
        again picks them up.

        Args:
            session: The session that was searched
            error: Why the search stopped, if it did
        """
        now = datetime.utcnow()
        if error:
            await self.db.rollback()
            await self.db.refresh(session)
            await self.db.execute(
                update(SearchQuery)
                .where(SearchQuery.session_id == session.id, SearchQuery.status == "processing")
                .values(status="pending")
            )
            session.status = "failed"
            session.error_message = error[:1000]
        else:
            session.status = "completed"
            session.error_message = None
        session.completed_at = now
        session.updated_at = now
        await self.db.commit()

    async def progress(self, session: SearchSession) -> dict:
        """
        How far a session's search has come, counted from its keywords.

        Args:
            session: Session to report on

        Returns:
            dict: status, error_message, total, pending, processing, completed,
                failed, results (stored so far), started_at, updated_at and
                stale (it says "processing" but its worker stopped reporting)
        """
        rows = await self.db.execute(
            select(
                SearchQuery.status,
                func.count(SearchQuery.id),
                func.coalesce(func.sum(SearchQuery.result_count), 0)
            )
            .where(SearchQuery.session_id == session.id)
            .group_by(SearchQuery.status)
        )
        counts = {"pending": 0, "processing": 0, "completed": 0, "failed": 0}
        results = 0
        for status, count, stored in rows.all():
            counts[status] = counts.get(status, 0) + count
            results += int(stored or 0)

        return {
            "status": session.status,
            "error_message": session.error_message,
            "total": sum(counts.values()),
            **counts,
            "results": results,
            "started_at": session.started_at,
            "updated_at": session.updated_at,
            "stale": self.is_stale(session),
        }

    async def _execute_single_query(
        self,
        session: SearchSession,
        query_text: str,
        engine: SearchEngineBase,
        max_results: int,
        language: str,
        country: str,
        allowed_domains: Optional[list[str]],
        seen_urls: set[str]
    ) -> SearchQuery:
        """
        Execute a single search query.

        Args:
            session: Parent session
            query_text: Query string
            engine: Search engine instance
            max_results: Max results
            language: Language code (hl parameter)
            country: Country code (gl parameter)
            allowed_domains: Optional domain filter
            seen_urls: Set of already seen URLs for deduplication

        Returns:
            SearchQuery: Created query with results
        """
        # Create query record
        query = SearchQuery(
            session_id=session.id,
            query_text=query_text,
            search_engine=engine.name,
            max_results=max_results,
            allowed_domains=allowed_domains,
            status="processing"
        )
        self.db.add(query)
        await self.db.flush()

        await self._run_query(
            query=query,
            engine=engine,
            language=language,
            country=country,
            allowed_domains=allowed_domains,
            seen_urls=seen_urls
        )
        return query

    async def _run_query(
        self,
        query: SearchQuery,
        engine: SearchEngineBase,
        language: str,
        country: str,
        allowed_domains: Optional[list[str]],
        seen_urls: set[str],
        fetched: Optional[Union[list[EngineSearchResult], Exception]] = None
    ) -> None:
        """
        Search for an existing query row and store its results.

        A failing search is recorded on the query (status "failed" and
        error_message) rather than raised, so one bad keyword does not stop
        the others. Commits when done.

        Args:
            query: Query row, already in status "processing"
            engine: Search engine instance
            language: Language code (hl parameter)
            country: Country code (gl parameter)
            allowed_domains: Optional domain filter
            seen_urls: URL hashes already stored for the session; updated
            fetched: Outcome of a search already made for this query by
                _search_batch: its results, or the exception it raised. None
                searches here.
        """
        query_text = query.query_text

        try:
            if fetched is None:
                # Execute search with language and country parameters
                results = await engine.search(
                    query=query_text,
                    max_results=query.max_results,
                    hl=language,
                    gl=country
                )
            elif isinstance(fetched, Exception):
                raise fetched
            else:
                results = fetched

            # Filter by allowed domains if specified
            if allowed_domains:
                results = self._filter_by_domains(results, allowed_domains)

            # Deduplicate and store results
            stored_count = await self._store_results(
                query=query,
                results=results,
                seen_urls=seen_urls
            )

            # Update query status
            query.status = "completed"
            query.result_count = stored_count
            query.executed_at = datetime.utcnow()

            logger.info(
                f"Query '{query_text}' completed with {stored_count} unique results"
            )

        except Exception as e:
            logger.error(f"Error executing query '{query_text}': {e}")
            query.status = "failed"
            query.error_message = str(e)
            query.executed_at = datetime.utcnow()

        await self.db.commit()

    def _keyword_slot(self):
        """
        A place among the keywords being searched by all workers at once (a
        no-op without shared limits).
        """
        if self.limits is None:
            return contextlib.nullcontext()
        return self.limits.slot(
            "keywords", settings.search_global_concurrency, lease=KEYWORD_SLOT_LEASE
        )

    async def _search_and_store(
        self,
        jobs: list[tuple[SearchQuery, SearchEngineBase]],
        language: str,
        country: str,
        seen_urls: set[str]
    ) -> None:
        """
        Search many queries in parallel and store their results in query order.

        Up to settings.search_concurrency searches run at the same time, in a
        sliding window: when one finishes the next starts, so a slow keyword
        does not hold back the ones behind it. Results are stored one query at
        a time in the order of jobs, as soon as that query's search is done,
        and committed each time, so deduplication and progress behave as if
        the queries ran one after another. A search that fails is recorded on
        its query like any other failure.

        Args:
            jobs: (query row, engine) pairs, in the order to store them
            language: Language code (hl parameter)
            country: Country code (gl parameter)
            seen_urls: URL hashes already stored for the session; updated
        """
        # Read the rows here, before the searches are awaited
        calls = [
            (engine, query.query_text, query.max_results) for query, engine in jobs
        ]
        window = asyncio.Semaphore(settings.search_concurrency)

        async def search(
            engine: SearchEngineBase, text: str, max_results: int
        ) -> Union[list[EngineSearchResult], Exception]:
            async with window, self._keyword_slot():
                try:
                    return await engine.search(
                        query=text, max_results=max_results, hl=language, gl=country
                    )
                except Exception as e:  # recorded on the query by _run_query
                    return e

        tasks = [asyncio.create_task(search(*call)) for call in calls]
        try:
            for (query, engine), task in zip(jobs, tasks):
                await self._run_query(
                    query=query,
                    engine=engine,
                    language=language,
                    country=country,
                    allowed_domains=query.allowed_domains,
                    seen_urls=seen_urls,
                    fetched=await task
                )
        finally:
            # If storing stops early (an error, a cancelled request), stop the
            # searches still running instead of leaving them behind
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def add_queries(
        self,
        session: SearchSession,
        queries: list[str]
    ) -> tuple[list[SearchQuery], list[str]]:
        """
        Queue new keywords on an existing session without searching yet.

        The queries take the session's search settings (engine, max results,
        language, domain filter) and wait in status "pending" until
        run_pending_queries is called. A keyword already in the session
        (compared case-insensitively, ignoring extra whitespace) is skipped,
        unless its earlier search failed, which makes adding it again a retry.

        Args:
            session: Session to extend, owned by the current user
            queries: Cleaned keyword strings

        Returns:
            tuple: (queries created, keywords skipped as already present)
        """
        config = session.config or {}

        result = await self.db.execute(
            select(SearchQuery.query_text).where(
                SearchQuery.session_id == session.id,
                SearchQuery.status != "failed"
            )
        )
        known = {self._query_key(text) for text in result.scalars()}

        added: list[SearchQuery] = []
        skipped: list[str] = []
        for text in queries:
            key = self._query_key(text)
            if key in known:
                skipped.append(text)
                continue
            known.add(key)

            query = SearchQuery(
                session_id=session.id,
                query_text=text,
                search_engine=config.get("search_engine", DEFAULT_SEARCH_ENGINE),
                max_results=config.get("max_results", DEFAULT_MAX_RESULTS),
                allowed_domains=config.get("allowed_domains"),
                language=config.get("language"),
                status="pending"
            )
            self.db.add(query)
            added.append(query)

        if added:
            session.updated_at = datetime.utcnow()
        await self.db.commit()

        logger.info(
            f"Queued {len(added)} keywords on session {session.id} "
            f"({len(skipped)} already present)"
        )
        return added, skipped

    async def count_pending_queries(self, session_id: int) -> int:
        """
        Count the keywords in a session that have not been searched yet.

        Args:
            session_id: Session ID

        Returns:
            int: Number of queries in status "pending"
        """
        result = await self.db.execute(
            select(func.count(SearchQuery.id)).where(
                SearchQuery.session_id == session_id,
                SearchQuery.status == "pending"
            )
        )
        return result.scalar() or 0

    async def run_pending_queries(self, session: SearchSession) -> dict[str, int]:
        """
        Search for the keywords queued on a session.

        Results are deduplicated against everything the session already
        holds, so a page found by an earlier keyword is not stored twice. The
        queued queries are claimed (status "processing") before any search
        runs, so a second click or request cannot search them again.

        Args:
            session: Session whose pending queries should run

        Returns:
            dict: queries_run, queries_failed, new_results, pending_count

        Raises:
            ValueError: If a pending query's search engine is not configured;
                nothing is claimed in that case
        """
        config = session.config or {}
        language = config.get("language", DEFAULT_LANGUAGE)
        country = config.get("country", DEFAULT_COUNTRY)

        # Build the engines first: a missing API key should leave the queries
        # pending instead of marking them all failed.
        engine_names = await self.db.execute(
            select(SearchQuery.search_engine).where(
                SearchQuery.session_id == session.id,
                SearchQuery.status == "pending"
            ).distinct()
        )
        engines = {
            name: self._get_search_engine(name) for name in engine_names.scalars()
        }

        # Claim the pending queries.
        claimed = await self.db.execute(
            select(SearchQuery)
            .where(
                SearchQuery.session_id == session.id,
                SearchQuery.status == "pending"
            )
            .order_by(SearchQuery.id)
            .with_for_update()
        )
        pending = list(claimed.scalars().all())
        for query in pending:
            query.status = "processing"
        await self.db.commit()

        if pending:
            seen_urls = await self._load_seen_urls(session.id)
            jobs = []
            for query in pending:
                try:
                    engine = engines.get(query.search_engine) or (
                        self._get_search_engine(query.search_engine)
                    )
                except ValueError as e:
                    query.status = "failed"
                    query.error_message = str(e)
                    query.executed_at = datetime.utcnow()
                    await self.db.commit()
                    continue
                jobs.append((query, engine))

            await self._search_and_store(
                jobs,
                language=language,
                country=country,
                seen_urls=seen_urls
            )

            session.updated_at = datetime.utcnow()
            await self.db.commit()

        logger.info(
            f"Ran {len(pending)} pending queries for session {session.id}"
        )
        return {
            "queries_run": len(pending),
            "queries_failed": sum(1 for q in pending if q.status == "failed"),
            "new_results": sum(q.result_count for q in pending),
            "pending_count": await self.count_pending_queries(session.id),
        }

    async def _load_seen_urls(self, session_id: int) -> set[str]:
        """
        Hash every URL already stored for a session.

        Args:
            session_id: Session ID

        Returns:
            set[str]: URL hashes in the form _store_results compares against
        """
        result = await self.db.execute(
            select(SearchResult.url)
            .join(SearchQuery, SearchResult.query_id == SearchQuery.id)
            .where(SearchQuery.session_id == session_id)
        )
        return {
            self._hash_url(self._normalize_url(url)) for url in result.scalars()
        }

    @staticmethod
    def _query_key(text: str) -> str:
        """Normalize a keyword for duplicate checks (case, inner whitespace)."""
        return " ".join(text.split()).casefold()

    async def _store_results(
        self,
        query: SearchQuery,
        results: list[EngineSearchResult],
        seen_urls: set[str]
    ) -> int:
        """
        Store search results with deduplication.

        Args:
            query: Parent query
            results: List of search results
            seen_urls: Set of URLs already seen in this session

        Returns:
            int: Number of unique results stored
        """
        stored_count = 0
        redirects = 0

        for result in results:
            # A Google redirect (google.com/goto) is not the page: engines
            # resolve these, and one that gets here unresolved must not be
            # stored, deduplicated or scraped as if it were a website
            if is_google_redirect(result.url):
                redirects += 1
                continue

            # Normalize URL for comparison
            normalized_url = self._normalize_url(result.url)
            url_hash = self._hash_url(normalized_url)

            # Skip if we've seen this URL in this session
            if url_hash in seen_urls:
                logger.debug(f"Skipping duplicate URL: {result.url}")
                continue

            # Store result
            search_result = SearchResult(
                query_id=query.id,
                url=result.url,
                title=result.title,
                description=result.description,
                rank=result.rank,
                domain=result.domain,
                scraped=False
            )
            self.db.add(search_result)

            # Mark URL as seen
            seen_urls.add(url_hash)
            stored_count += 1

        if redirects:
            logger.warning(
                f"Query {query.id}: skipped {redirects} unresolved Google redirect link(s)"
            )

        await self.db.flush()
        return stored_count

    def _get_search_engine(self, engine_name: str):
        """
        Get search engine instance.

        Args:
            engine_name: Name of search engine

        Returns:
            Search engine instance

        Raises:
            ValueError: If engine not supported or not configured
        """
        if engine_name == "google_custom":
            if not settings.google_custom_search_api_key:
                raise ValueError("Google Custom Search API key not configured")
            if not settings.google_custom_search_engine_id:
                raise ValueError("Google Custom Search Engine ID not configured")

            return GoogleCustomSearch(
                api_key=settings.google_custom_search_api_key,
                search_engine_id=settings.google_custom_search_engine_id
            )

        elif engine_name == "serper":
            if not settings.serper_api_key:
                raise ValueError("Serper API key not configured")

            return SerperSearch(
                api_key=settings.serper_api_key,
                resolve_concurrency=settings.serper_resolve_concurrency,
                base_url=settings.serper_base_url,
                limits=self.limits,
                rate_per_second=settings.serper_rate_limit_per_second
            )

        else:
            raise ValueError(f"Unsupported search engine: {engine_name}")

    def _filter_by_domains(
        self,
        results: list[EngineSearchResult],
        allowed_domains: list[str]
    ) -> list[EngineSearchResult]:
        """
        Filter results by allowed domains.

        Args:
            results: List of search results
            allowed_domains: List of allowed TLDs (e.g., ['.dk', '.com'])

        Returns:
            list[EngineSearchResult]: Filtered results
        """
        filtered = []
        for result in results:
            domain = result.domain.lower()
            if any(domain.endswith(tld.lower()) for tld in allowed_domains):
                filtered.append(result)
        return filtered

    def _normalize_url(self, url: str) -> str:
        """
        Normalize URL for comparison.

        Args:
            url: URL to normalize

        Returns:
            str: Normalized URL
        """
        try:
            parsed = urlparse(url)
            # Remove trailing slashes, fragments, and normalize case
            normalized = (
                f"{parsed.scheme}://{parsed.netloc.lower()}"
                f"{parsed.path.rstrip('/')}"
            )
            if parsed.query:
                normalized += f"?{parsed.query}"
            return normalized
        except Exception:
            return url.lower()

    def _hash_url(self, url: str) -> str:
        """
        Create hash of URL for deduplication.

        Args:
            url: URL to hash

        Returns:
            str: URL hash
        """
        return hashlib.md5(url.encode()).hexdigest()

    async def get_session(self, session_id: int) -> Optional[SearchSession]:
        """
        Get search session by ID.

        Args:
            session_id: Session ID

        Returns:
            Optional[SearchSession]: Session if found and owned by user
        """
        result = await self.db.execute(
            select(SearchSession)
            .where(
                SearchSession.id == session_id,
                SearchSession.user_id == self.user.id
            )
        )
        return result.scalar_one_or_none()

    async def list_sessions(
        self,
        skip: int = 0,
        limit: int = 20,
        sort: str = "created_at",
        order: str = "desc"
    ) -> tuple[list[SearchSession], int]:
        """
        List user's search sessions.

        Args:
            skip: Number to skip
            limit: Max number to return
            sort: Sort field
            order: Sort order (asc/desc)

        Returns:
            tuple: (sessions, total_count)
        """
        # Base query
        query = select(SearchSession).where(SearchSession.user_id == self.user.id)

        # Add sorting
        sort_column = getattr(SearchSession, sort, SearchSession.created_at)
        if order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Get total count
        count_query = select(func.count()).select_from(SearchSession).where(
            SearchSession.user_id == self.user.id
        )
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated results
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        sessions = list(result.scalars().all())

        return sessions, total

    async def delete_session(self, session_id: int) -> bool:
        """
        Delete a search session.

        Args:
            session_id: Session ID

        Returns:
            bool: True if deleted, False if not found
        """
        session = await self.get_session(session_id)
        if session is None:
            return False

        await self.db.delete(session)
        await self.db.commit()
        logger.info(f"Deleted search session {session_id}")
        return True
