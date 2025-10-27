"""Search service for executing and managing searches."""
import hashlib
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.core.search_engines.base import SearchResult as EngineSearchResult
from backend.core.search_engines.google_custom import GoogleCustomSearch
from backend.core.search_engines.serper import SerperSearch
from backend.models.search import SearchSession, SearchQuery, SearchResult
from backend.models.user import User

logger = logging.getLogger(__name__)


class SearchService:
    """Service for managing search operations."""

    def __init__(self, db: AsyncSession, user: User) -> None:
        """
        Initialize search service.

        Args:
            db: Database session
            user: Current user
        """
        self.db = db
        self.user = user

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

    async def execute_search(
        self,
        session: SearchSession,
        queries: list[str],
        search_engine: str,
        max_results: int,
        language: str = "da",
        country: str = "dk",
        allowed_domains: Optional[list[str]] = None
    ) -> SearchSession:
        """
        Execute searches for multiple queries.

        Args:
            session: Search session
            queries: List of query strings
            search_engine: Search engine name
            max_results: Max results per query
            language: Language code (hl parameter)
            country: Country code (gl parameter)
            allowed_domains: Optional domain filter

        Returns:
            SearchSession: Updated session
        """
        # Update session status
        session.status = "processing"
        session.started_at = datetime.utcnow()
        await self.db.commit()

        # Get search engine instance
        engine = self._get_search_engine(search_engine)

        # Track seen URLs for deduplication across queries
        seen_urls: set[str] = set()

        try:
            for query_text in queries:
                await self._execute_single_query(
                    session=session,
                    query_text=query_text,
                    engine=engine,
                    max_results=max_results,
                    language=language,
                    country=country,
                    allowed_domains=allowed_domains,
                    seen_urls=seen_urls
                )

            # Mark session as completed
            session.status = "completed"
            session.completed_at = datetime.utcnow()

        except Exception as e:
            logger.error(f"Error executing searches for session {session.id}: {e}")
            session.status = "failed"
            session.completed_at = datetime.utcnow()
            raise

        finally:
            await self.db.commit()
            await self.db.refresh(session)

        logger.info(
            f"Completed search session {session.id} with {len(queries)} queries"
        )
        return session

    async def _execute_single_query(
        self,
        session: SearchSession,
        query_text: str,
        engine,
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

        try:
            # Execute search with language and country parameters
            results = await engine.search(
                query=query_text,
                max_results=max_results,
                hl=language,
                gl=country
            )

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
        return query

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

        for result in results:
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
                api_key=settings.serper_api_key
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
