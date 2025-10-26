"""Celery tasks for Phase 7 advanced search features."""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from celery import Task

from backend.celery_app import celery_app
from backend.database import AsyncSessionLocal
from backend.models.user import User
from backend.models.search import SearchSession
from backend.models.bulk_search import BulkSearchUpload, BulkSearchRow
from backend.models.query_expansion import QueryExpansionCandidate
from backend.services.temporal_search_service import TemporalSearchService
from backend.services.session_comparison_service import SessionComparisonService
from backend.services.search_service import SearchService
from backend.core.search.query_expansion import QueryExpander
from sqlalchemy import select

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task with database session management."""

    _db = None

    @property
    def db(self):
        """Get database session."""
        if self._db is None:
            self._db = AsyncSessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        """Close database session after task."""
        if self._db is not None:
            import asyncio
            asyncio.create_task(self._db.close())
            self._db = None


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="advanced_search.query_expansion",
    max_retries=3,
    default_retry_delay=60,
)
async def query_expansion_task(
    self,
    session_id: int,
    user_id: int,
    expansion_sources: List[str],
    max_candidates: int = 100,
    min_score: float = 0.1,
) -> Dict[str, Any]:
    """
    Generate query expansion candidates asynchronously.

    Args:
        session_id: Session ID to expand from
        user_id: User ID
        expansion_sources: Sources to use for expansion
        max_candidates: Maximum candidates to generate
        min_score: Minimum score threshold

    Returns:
        Dict with expansion results
    """
    try:
        async with AsyncSessionLocal() as db:
            # Get user
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one()

            # Get session
            session_result = await db.execute(
                select(SearchSession).where(SearchSession.id == session_id)
            )
            session = session_result.scalar_one()

            # Initialize expander
            expander = QueryExpander(
                max_candidates=max_candidates,
                min_frequency=2,
                similarity_threshold=min_score,
            )

            # Get search results if requested
            candidates = []

            if "search_results" in expansion_sources:
                # Get results from session
                from backend.models.search import SearchQuery, SearchResult

                queries = await db.execute(
                    select(SearchQuery).where(SearchQuery.session_id == session_id)
                )
                query_list = list(queries.scalars().all())

                if query_list:
                    query_ids = [q.id for q in query_list]
                    results = await db.execute(
                        select(SearchResult).where(SearchResult.query_id.in_(query_ids))
                    )
                    result_list = list(results.scalars().all())

                    # Convert to dict format
                    result_dicts = [
                        {
                            "url": r.url,
                            "title": r.title,
                            "description": r.description,
                        }
                        for r in result_list
                    ]

                    # Get seed query (first query)
                    seed_query = query_list[0].query_text

                    # Expand from results
                    result_candidates = expander.expand_from_search_results(
                        results=result_dicts,
                        seed_query=seed_query,
                    )

                    candidates.extend(result_candidates)

            if "content" in expansion_sources:
                # Get analyzed content
                from backend.models.website import WebsiteContent
                from backend.models.analysis import ExtractedNoun, ExtractedEntity

                # Get content IDs from session results
                queries = await db.execute(
                    select(SearchQuery).where(SearchQuery.session_id == session_id)
                )
                query_list = list(queries.scalars().all())

                if query_list:
                    query_ids = [q.id for q in query_list]
                    from backend.models.search import SearchResult

                    results = await db.execute(
                        select(SearchResult).where(SearchResult.query_id.in_(query_ids))
                    )
                    result_list = list(results.scalars().all())
                    urls = [r.url for r in result_list]

                    # Get content
                    contents = await db.execute(
                        select(WebsiteContent).where(WebsiteContent.url.in_(urls))
                    )
                    content_list = list(contents.scalars().all())
                    content_ids = [c.id for c in content_list]

                    if content_ids:
                        # Get nouns
                        nouns = await db.execute(
                            select(ExtractedNoun).where(
                                ExtractedNoun.website_content_id.in_(content_ids)
                            )
                        )
                        noun_list = list(nouns.scalars().all())

                        # Get entities
                        entities = await db.execute(
                            select(ExtractedEntity).where(
                                ExtractedEntity.website_content_id.in_(content_ids)
                            )
                        )
                        entity_list = list(entities.scalars().all())

                        # Convert to dict format
                        noun_dicts = [
                            {
                                "word": n.word,
                                "lemma": n.lemma,
                                "frequency": n.frequency,
                                "tfidf_score": n.tfidf_score,
                            }
                            for n in noun_list
                        ]

                        entity_dicts = [
                            {
                                "text": e.text,
                                "label": e.label,
                                "confidence": e.confidence,
                            }
                            for e in entity_list
                        ]

                        # Expand from content
                        seed_query = query_list[0].query_text
                        content_candidates = expander.expand_from_content(
                            nouns=noun_dicts,
                            entities=entity_dicts,
                            seed_query=seed_query,
                            top_n=50,
                        )

                        candidates.extend(content_candidates)

            # Filter candidates
            if candidates:
                seed_query = ""
                queries = await db.execute(
                    select(SearchQuery).where(SearchQuery.session_id == session_id)
                )
                query_list = list(queries.scalars().all())
                if query_list:
                    seed_query = query_list[0].query_text

                candidates = expander.filter_candidates(
                    candidates=candidates,
                    seed_query=seed_query,
                    min_score=min_score,
                )

            # Store candidates in database
            stored_count = 0
            for candidate in candidates[:max_candidates]:
                db_candidate = QueryExpansionCandidate(
                    session_id=session_id,
                    candidate_term=candidate.term,
                    score=candidate.score,
                    source=",".join(candidate.sources),
                    metadata=candidate.metadata,
                    generation=1,
                )
                db.add(db_candidate)
                stored_count += 1

            await db.commit()

            logger.info(
                f"Generated {stored_count} expansion candidates for session {session_id}"
            )

            return {
                "session_id": session_id,
                "candidates_generated": stored_count,
                "sources_used": expansion_sources,
                "status": "completed",
            }

    except Exception as e:
        logger.error(f"Error in query expansion task: {e}")
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="advanced_search.bulk_search",
    max_retries=1,
    soft_time_limit=3600,  # 1 hour
)
async def bulk_search_task(
    self,
    upload_id: int,
    user_id: int,
    session_name: str,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute bulk search from CSV upload.

    Args:
        upload_id: Bulk upload ID
        user_id: User ID
        session_name: Name for the search session
        description: Optional session description

    Returns:
        Dict with execution results
    """
    try:
        async with AsyncSessionLocal() as db:
            # Get user
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one()

            # Get upload
            upload_result = await db.execute(
                select(BulkSearchUpload).where(BulkSearchUpload.id == upload_id)
            )
            upload = upload_result.scalar_one()

            # Create session
            search_service = SearchService(db, user)
            session = await search_service.create_session(
                name=session_name,
                description=description or f"Bulk search from {upload.filename}",
                config={"bulk_upload_id": upload_id},
            )

            # Update upload
            upload.session_id = session.id
            upload.task_id = self.request.id
            upload.executed_at = datetime.utcnow()
            await db.commit()

            # Get all rows
            rows_result = await db.execute(
                select(BulkSearchRow).where(BulkSearchRow.upload_id == upload_id)
            )
            rows = list(rows_result.scalars().all())

            # Execute each row
            successful = 0
            failed = 0

            for row in rows:
                try:
                    # Parse row data
                    query_data = row.query_data
                    query_text = query_data.get("query")
                    search_engine = query_data.get("search_engine", "google_custom")
                    max_results = query_data.get("max_results", 10)

                    # Execute search
                    await search_service._execute_single_query(
                        session=session,
                        query_text=query_text,
                        engine=search_service._get_search_engine(search_engine),
                        max_results=max_results,
                        allowed_domains=query_data.get("allowed_domains"),
                        seen_urls=set(),  # Each row gets fresh deduplication
                    )

                    row.status = "completed"
                    successful += 1

                except Exception as e:
                    logger.error(f"Error executing row {row.row_number}: {e}")
                    row.status = "failed"
                    row.error_message = str(e)
                    failed += 1

                await db.commit()

                # Update progress
                progress = ((successful + failed) / len(rows)) * 100
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "current": successful + failed,
                        "total": len(rows),
                        "percentage": progress,
                    },
                )

            # Mark session and upload as completed
            session.status = "completed"
            session.completed_at = datetime.utcnow()
            upload.completed_at = datetime.utcnow()
            await db.commit()

            logger.info(
                f"Bulk search completed: {successful} successful, {failed} failed"
            )

            return {
                "upload_id": upload_id,
                "session_id": session.id,
                "total_rows": len(rows),
                "successful": successful,
                "failed": failed,
                "status": "completed",
            }

    except Exception as e:
        logger.error(f"Error in bulk search task: {e}")
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="advanced_search.temporal_snapshot",
    max_retries=3,
)
async def temporal_snapshot_task(
    self,
    session_id: int,
    user_id: int,
) -> Dict[str, Any]:
    """
    Create temporal snapshot archive for later comparison.

    Args:
        session_id: Session ID to snapshot
        user_id: User ID

    Returns:
        Dict with snapshot info
    """
    try:
        async with AsyncSessionLocal() as db:
            # Get session
            session_result = await db.execute(
                select(SearchSession).where(SearchSession.id == session_id)
            )
            session = session_result.scalar_one()

            # Mark as temporal snapshot
            session.config = session.config or {}
            session.config["temporal_snapshot"] = {
                "created_at": datetime.utcnow().isoformat(),
                "archived": True,
            }

            await db.commit()

            logger.info(f"Created temporal snapshot for session {session_id}")

            return {
                "session_id": session_id,
                "snapshot_created": True,
                "timestamp": datetime.utcnow().isoformat(),
            }

    except Exception as e:
        logger.error(f"Error creating temporal snapshot: {e}")
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="advanced_search.session_comparison",
    max_retries=3,
)
async def session_comparison_task(
    self,
    session_ids: List[int],
    user_id: int,
    comparison_type: str = "full",
) -> Dict[str, Any]:
    """
    Perform complex session comparison asynchronously.

    Args:
        session_ids: List of session IDs to compare
        user_id: User ID
        comparison_type: Type of comparison

    Returns:
        Dict with comparison results
    """
    try:
        async with AsyncSessionLocal() as db:
            # Get user
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one()

            # Perform comparison
            comparison_service = SessionComparisonService(db, user)
            results = await comparison_service.compare_sessions(
                session_ids=session_ids,
                comparison_type=comparison_type,
            )

            logger.info(f"Completed comparison of {len(session_ids)} sessions")

            return results

    except Exception as e:
        logger.error(f"Error in session comparison task: {e}")
        raise self.retry(exc=e)
