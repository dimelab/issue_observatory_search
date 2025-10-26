"""Temporal search service for time-based queries."""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from collections import defaultdict

from backend.models.search import SearchSession, SearchQuery, SearchResult
from backend.models.user import User
from backend.services.search_service import SearchService

logger = logging.getLogger(__name__)


class TemporalSearchService:
    """
    Service for temporal search operations.

    Provides functionality for:
    - Date-filtered searches
    - Time period comparisons
    - Trend detection
    - Temporal snapshots
    """

    def __init__(self, db: AsyncSession, user: User):
        """
        Initialize temporal search service.

        Args:
            db: Database session
            user: Current user
        """
        self.db = db
        self.user = user
        self.search_service = SearchService(db, user)

    async def search_with_date_range(
        self,
        session: SearchSession,
        queries: List[str],
        search_engine: str,
        max_results: int,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        temporal_snapshot: bool = False,
        **kwargs,
    ) -> SearchSession:
        """
        Execute search with date range filtering.

        Args:
            session: Search session
            queries: List of query strings
            search_engine: Search engine name
            max_results: Max results per query
            date_from: Start date for filtering
            date_to: End date for filtering
            temporal_snapshot: If true, mark as snapshot for later comparison
            **kwargs: Additional search parameters

        Returns:
            Updated search session
        """
        logger.info(
            f"Executing temporal search from {date_from} to {date_to} "
            f"(snapshot={temporal_snapshot})"
        )

        # Update session config with temporal info
        session.config = session.config or {}
        session.config["temporal"] = {
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "snapshot": temporal_snapshot,
        }

        session.status = "processing"
        session.started_at = datetime.utcnow()
        await self.db.commit()

        # Get search engine instance
        engine = self.search_service._get_search_engine(search_engine)

        # Check if engine supports date filtering
        if not hasattr(engine, "search"):
            raise ValueError(f"Engine {search_engine} does not support temporal search")

        # Track seen URLs
        seen_urls: set[str] = set()

        try:
            for query_text in queries:
                # Create query record with temporal fields
                query = SearchQuery(
                    session_id=session.id,
                    query_text=query_text,
                    search_engine=engine.name,
                    max_results=max_results,
                    date_from=date_from,
                    date_to=date_to,
                    temporal_snapshot=temporal_snapshot,
                    status="processing",
                )
                self.db.add(query)
                await self.db.flush()

                try:
                    # Execute search with date range
                    results = await engine.search(
                        query=query_text,
                        max_results=max_results,
                        date_from=date_from,
                        date_to=date_to,
                    )

                    # Apply additional filters if specified
                    if kwargs.get("allowed_domains"):
                        results = self.search_service._filter_by_domains(
                            results, kwargs["allowed_domains"]
                        )

                    # Store results
                    stored_count = await self.search_service._store_results(
                        query=query,
                        results=results,
                        seen_urls=seen_urls,
                    )

                    query.status = "completed"
                    query.result_count = stored_count
                    query.executed_at = datetime.utcnow()

                    logger.info(
                        f"Temporal query '{query_text}' completed with {stored_count} results"
                    )

                except Exception as e:
                    logger.error(f"Error executing temporal query '{query_text}': {e}")
                    query.status = "failed"
                    query.error_message = str(e)
                    query.executed_at = datetime.utcnow()

                await self.db.commit()

            # Mark session as completed
            session.status = "completed"
            session.completed_at = datetime.utcnow()

        except Exception as e:
            logger.error(f"Error executing temporal searches: {e}")
            session.status = "failed"
            session.completed_at = datetime.utcnow()
            raise

        finally:
            await self.db.commit()
            await self.db.refresh(session)

        return session

    async def compare_time_periods(
        self,
        query_text: str,
        periods: List[Dict[str, datetime]],
        search_engine: str = "google_custom",
        max_results: int = 50,
    ) -> Dict[str, Any]:
        """
        Compare search results across different time periods.

        Args:
            query_text: Query to search
            periods: List of dicts with 'start' and 'end' datetime
            search_engine: Search engine to use
            max_results: Max results per period

        Returns:
            Dict with comparison data
        """
        logger.info(f"Comparing {len(periods)} time periods for '{query_text}'")

        period_results = []

        for i, period in enumerate(periods):
            # Create session for this period
            session = await self.search_service.create_session(
                name=f"Temporal comparison: {query_text} ({i+1})",
                description=f"Period {period['start']} to {period['end']}",
                config={"comparison_index": i},
            )

            # Execute search for this period
            await self.search_with_date_range(
                session=session,
                queries=[query_text],
                search_engine=search_engine,
                max_results=max_results,
                date_from=period.get("start"),
                date_to=period.get("end"),
                temporal_snapshot=True,
            )

            # Get results
            query = await self.db.execute(
                select(SearchQuery).where(SearchQuery.session_id == session.id)
            )
            query_obj = query.scalar_one()

            results = await self.db.execute(
                select(SearchResult).where(SearchResult.query_id == query_obj.id)
            )
            result_list = list(results.scalars().all())

            period_results.append({
                "period": period,
                "session_id": session.id,
                "result_count": len(result_list),
                "results": result_list,
            })

        # Analyze differences
        analysis = self._analyze_temporal_changes(period_results)

        return {
            "query": query_text,
            "periods": periods,
            "period_results": period_results,
            "analysis": analysis,
        }

    async def detect_trends(
        self,
        session_id: int,
    ) -> Dict[str, Any]:
        """
        Detect trends in temporal search results.

        Analyzes how search results change over time to identify:
        - Emerging domains
        - Declining domains
        - New topics/terms
        - Changing rankings

        Args:
            session_id: Session ID to analyze

        Returns:
            Dict with trend analysis
        """
        # Get session
        session = await self.search_service.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Get all queries with temporal data
        queries = await self.db.execute(
            select(SearchQuery)
            .where(
                and_(
                    SearchQuery.session_id == session_id,
                    SearchQuery.temporal_snapshot == True,
                )
            )
            .order_by(SearchQuery.date_from)
        )
        query_list = list(queries.scalars().all())

        if not query_list:
            return {"error": "No temporal snapshots found in session"}

        # Group queries by time period
        time_periods = defaultdict(list)
        for query in query_list:
            period_key = (query.date_from, query.date_to)
            time_periods[period_key].append(query)

        # Analyze each period
        period_analysis = []
        for period, period_queries in sorted(time_periods.items()):
            # Get all results for this period
            query_ids = [q.id for q in period_queries]
            results = await self.db.execute(
                select(SearchResult).where(SearchResult.query_id.in_(query_ids))
            )
            result_list = list(results.scalars().all())

            # Extract domains and count
            domain_counts = defaultdict(int)
            for result in result_list:
                domain_counts[result.domain] += 1

            period_analysis.append({
                "period": {"start": period[0], "end": period[1]},
                "result_count": len(result_list),
                "unique_domains": len(domain_counts),
                "top_domains": sorted(
                    domain_counts.items(), key=lambda x: x[1], reverse=True
                )[:10],
            })

        # Detect trends
        trends = self._detect_domain_trends(period_analysis)

        return {
            "session_id": session_id,
            "periods_analyzed": len(period_analysis),
            "period_analysis": period_analysis,
            "trends": trends,
        }

    async def get_temporal_snapshots(
        self,
        query_text: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[SearchSession]:
        """
        Get temporal snapshots for a query.

        Args:
            query_text: Optional query text filter
            date_from: Optional start date
            date_to: Optional end date

        Returns:
            List of search sessions marked as temporal snapshots
        """
        # Build query
        conditions = [
            SearchSession.user_id == self.user.id,
        ]

        # Get sessions with temporal config
        result = await self.db.execute(
            select(SearchSession).where(and_(*conditions))
        )
        sessions = list(result.scalars().all())

        # Filter for temporal snapshots
        temporal_sessions = []
        for session in sessions:
            if session.config and session.config.get("temporal", {}).get("snapshot"):
                # Additional filtering if specified
                if query_text:
                    # Check if any query matches
                    queries = await self.db.execute(
                        select(SearchQuery).where(
                            and_(
                                SearchQuery.session_id == session.id,
                                SearchQuery.query_text.ilike(f"%{query_text}%"),
                            )
                        )
                    )
                    if not queries.scalar_one_or_none():
                        continue

                temporal_sessions.append(session)

        logger.info(f"Found {len(temporal_sessions)} temporal snapshots")
        return temporal_sessions

    def _analyze_temporal_changes(
        self,
        period_results: List[Dict],
    ) -> Dict[str, Any]:
        """
        Analyze changes across time periods.

        Args:
            period_results: List of period result dicts

        Returns:
            Dict with analysis
        """
        # Extract URLs and domains across periods
        period_urls = []
        period_domains = []

        for period_data in period_results:
            urls = {r.url for r in period_data["results"]}
            domains = {r.domain for r in period_data["results"]}
            period_urls.append(urls)
            period_domains.append(domains)

        # Calculate overlap between consecutive periods
        url_overlaps = []
        domain_overlaps = []

        for i in range(len(period_urls) - 1):
            url_overlap = len(period_urls[i] & period_urls[i + 1])
            url_overlap_pct = (
                url_overlap / len(period_urls[i]) * 100 if period_urls[i] else 0
            )

            domain_overlap = len(period_domains[i] & period_domains[i + 1])
            domain_overlap_pct = (
                domain_overlap / len(period_domains[i]) * 100
                if period_domains[i]
                else 0
            )

            url_overlaps.append({
                "periods": f"{i} -> {i+1}",
                "overlap_count": url_overlap,
                "overlap_percentage": round(url_overlap_pct, 2),
            })

            domain_overlaps.append({
                "periods": f"{i} -> {i+1}",
                "overlap_count": domain_overlap,
                "overlap_percentage": round(domain_overlap_pct, 2),
            })

        # Find new and disappeared URLs/domains
        if len(period_results) >= 2:
            first_urls = period_urls[0]
            last_urls = period_urls[-1]

            new_urls = last_urls - first_urls
            disappeared_urls = first_urls - last_urls

            first_domains = period_domains[0]
            last_domains = period_domains[-1]

            new_domains = last_domains - first_domains
            disappeared_domains = first_domains - last_domains
        else:
            new_urls = set()
            disappeared_urls = set()
            new_domains = set()
            disappeared_domains = set()

        return {
            "url_overlaps": url_overlaps,
            "domain_overlaps": domain_overlaps,
            "new_urls_count": len(new_urls),
            "disappeared_urls_count": len(disappeared_urls),
            "new_domains": list(new_domains),
            "disappeared_domains": list(disappeared_domains),
        }

    def _detect_domain_trends(
        self,
        period_analysis: List[Dict],
    ) -> Dict[str, Any]:
        """
        Detect domain trends across periods.

        Args:
            period_analysis: List of period analysis dicts

        Returns:
            Dict with trend detection
        """
        if len(period_analysis) < 2:
            return {"error": "Need at least 2 periods to detect trends"}

        # Track domain appearances across periods
        domain_timeline = defaultdict(list)

        for i, period in enumerate(period_analysis):
            for domain, count in period["top_domains"]:
                domain_timeline[domain].append((i, count))

        # Classify trends
        emerging = []  # Domains appearing later
        declining = []  # Domains disappearing
        stable = []  # Domains consistent across periods

        for domain, timeline in domain_timeline.items():
            period_indices = [t[0] for t in timeline]
            counts = [t[1] for t in timeline]

            # Emerging: appears in later periods but not early ones
            if min(period_indices) > 0:
                emerging.append({
                    "domain": domain,
                    "first_appearance": min(period_indices),
                    "max_count": max(counts),
                })

            # Declining: appears in early periods but not later ones
            elif max(period_indices) < len(period_analysis) - 1:
                declining.append({
                    "domain": domain,
                    "last_appearance": max(period_indices),
                    "max_count": max(counts),
                })

            # Stable: appears in most periods
            elif len(period_indices) >= len(period_analysis) * 0.7:
                stable.append({
                    "domain": domain,
                    "appearances": len(period_indices),
                    "avg_count": sum(counts) / len(counts),
                })

        return {
            "emerging_domains": sorted(
                emerging, key=lambda x: x["max_count"], reverse=True
            )[:10],
            "declining_domains": sorted(
                declining, key=lambda x: x["max_count"], reverse=True
            )[:10],
            "stable_domains": sorted(
                stable, key=lambda x: x["avg_count"], reverse=True
            )[:10],
        }
