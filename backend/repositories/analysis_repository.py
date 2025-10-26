"""Repository for analysis database operations."""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, delete, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.analysis import ExtractedNoun, ExtractedEntity, ContentAnalysis
from backend.models.website import WebsiteContent

logger = logging.getLogger(__name__)


class AnalysisRepository:
    """
    Repository for analysis database operations.

    Handles all database interactions for content analysis,
    including nouns, entities, and analysis metadata.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    # ContentAnalysis operations

    async def create_analysis(
        self,
        content_id: int,
        extract_nouns: bool,
        extract_entities: bool,
        max_nouns: int,
        min_frequency: int,
    ) -> ContentAnalysis:
        """
        Create a new analysis record.

        Args:
            content_id: Website content ID
            extract_nouns: Whether nouns were extracted
            extract_entities: Whether entities were extracted
            max_nouns: Maximum nouns configured
            min_frequency: Minimum frequency configured

        Returns:
            Created ContentAnalysis object
        """
        analysis = ContentAnalysis(
            website_content_id=content_id,
            extract_nouns=extract_nouns,
            extract_entities=extract_entities,
            max_nouns=max_nouns,
            min_frequency=min_frequency,
            status="pending",
            started_at=datetime.utcnow(),
        )

        self.session.add(analysis)
        await self.session.flush()

        logger.debug(f"Created analysis record for content_id={content_id}")
        return analysis

    async def get_analysis_by_content_id(
        self, content_id: int
    ) -> Optional[ContentAnalysis]:
        """
        Get analysis record by content ID.

        Args:
            content_id: Website content ID

        Returns:
            ContentAnalysis object or None
        """
        stmt = select(ContentAnalysis).where(
            ContentAnalysis.website_content_id == content_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_analysis_status(
        self,
        analysis_id: int,
        status: str,
        error_message: Optional[str] = None,
        nouns_count: Optional[int] = None,
        entities_count: Optional[int] = None,
        processing_duration: Optional[float] = None,
    ) -> Optional[ContentAnalysis]:
        """
        Update analysis status and metadata.

        Args:
            analysis_id: Analysis record ID
            status: New status (processing, completed, failed)
            error_message: Error message if failed
            nouns_count: Number of nouns extracted
            entities_count: Number of entities extracted
            processing_duration: Processing time in seconds

        Returns:
            Updated ContentAnalysis object or None
        """
        stmt = select(ContentAnalysis).where(ContentAnalysis.id == analysis_id)
        result = await self.session.execute(stmt)
        analysis = result.scalar_one_or_none()

        if not analysis:
            return None

        analysis.status = status
        analysis.updated_at = datetime.utcnow()

        if status == "completed":
            analysis.completed_at = datetime.utcnow()

        if error_message is not None:
            analysis.error_message = error_message

        if nouns_count is not None:
            analysis.nouns_count = nouns_count

        if entities_count is not None:
            analysis.entities_count = entities_count

        if processing_duration is not None:
            analysis.processing_duration = processing_duration

        await self.session.flush()

        logger.debug(
            f"Updated analysis {analysis_id} to status: {status}"
        )
        return analysis

    async def delete_analysis(self, content_id: int) -> bool:
        """
        Delete analysis and all related data for a content.

        Args:
            content_id: Website content ID

        Returns:
            True if deleted, False if not found
        """
        # Delete analysis (cascade will delete nouns and entities)
        stmt = delete(ContentAnalysis).where(
            ContentAnalysis.website_content_id == content_id
        )
        result = await self.session.execute(stmt)
        await self.session.flush()

        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Deleted analysis for content_id={content_id}")

        return deleted

    # ExtractedNoun operations

    async def bulk_create_nouns(
        self, nouns: List[Dict[str, Any]]
    ) -> List[ExtractedNoun]:
        """
        Bulk insert nouns.

        Args:
            nouns: List of noun dictionaries

        Returns:
            List of created ExtractedNoun objects
        """
        if not nouns:
            return []

        # Create model instances
        noun_objects = [ExtractedNoun(**noun_data) for noun_data in nouns]

        # Add all at once
        self.session.add_all(noun_objects)
        await self.session.flush()

        logger.debug(f"Bulk created {len(noun_objects)} nouns")
        return noun_objects

    async def get_nouns_by_content_id(
        self, content_id: int, limit: Optional[int] = None
    ) -> List[ExtractedNoun]:
        """
        Get nouns for a content, ordered by TF-IDF score.

        Args:
            content_id: Website content ID
            limit: Optional limit on results

        Returns:
            List of ExtractedNoun objects
        """
        stmt = (
            select(ExtractedNoun)
            .where(ExtractedNoun.website_content_id == content_id)
            .order_by(desc(ExtractedNoun.tfidf_score))
        )

        if limit:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_nouns_by_content_id(self, content_id: int) -> int:
        """
        Delete all nouns for a content.

        Args:
            content_id: Website content ID

        Returns:
            Number of nouns deleted
        """
        stmt = delete(ExtractedNoun).where(
            ExtractedNoun.website_content_id == content_id
        )
        result = await self.session.execute(stmt)
        await self.session.flush()

        return result.rowcount

    # ExtractedEntity operations

    async def bulk_create_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[ExtractedEntity]:
        """
        Bulk insert entities.

        Args:
            entities: List of entity dictionaries

        Returns:
            List of created ExtractedEntity objects
        """
        if not entities:
            return []

        # Create model instances
        entity_objects = [
            ExtractedEntity(**entity_data) for entity_data in entities
        ]

        # Add all at once
        self.session.add_all(entity_objects)
        await self.session.flush()

        logger.debug(f"Bulk created {len(entity_objects)} entities")
        return entity_objects

    async def get_entities_by_content_id(
        self,
        content_id: int,
        label: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[ExtractedEntity]:
        """
        Get entities for a content.

        Args:
            content_id: Website content ID
            label: Optional entity type filter
            limit: Optional limit on results

        Returns:
            List of ExtractedEntity objects
        """
        stmt = select(ExtractedEntity).where(
            ExtractedEntity.website_content_id == content_id
        )

        if label:
            stmt = stmt.where(ExtractedEntity.label == label)

        stmt = stmt.order_by(ExtractedEntity.start_pos)

        if limit:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_entities_by_content_id(self, content_id: int) -> int:
        """
        Delete all entities for a content.

        Args:
            content_id: Website content ID

        Returns:
            Number of entities deleted
        """
        stmt = delete(ExtractedEntity).where(
            ExtractedEntity.website_content_id == content_id
        )
        result = await self.session.execute(stmt)
        await self.session.flush()

        return result.rowcount

    # Aggregate queries

    async def get_aggregated_nouns_for_job(
        self, job_id: int, top_n: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get aggregated noun statistics for a scraping job.

        Args:
            job_id: Scraping job ID
            top_n: Number of top nouns to return

        Returns:
            List of dictionaries with aggregated noun data
        """
        # Join ExtractedNoun with WebsiteContent to filter by job
        stmt = (
            select(
                ExtractedNoun.lemma,
                func.sum(ExtractedNoun.frequency).label("total_frequency"),
                func.avg(ExtractedNoun.tfidf_score).label("avg_tfidf_score"),
                func.count(ExtractedNoun.website_content_id.distinct()).label(
                    "content_count"
                ),
                func.min(ExtractedNoun.word).label("example_word"),
            )
            .join(
                WebsiteContent,
                ExtractedNoun.website_content_id == WebsiteContent.id,
            )
            .where(WebsiteContent.scraping_job_id == job_id)
            .group_by(ExtractedNoun.lemma)
            .order_by(desc("total_frequency"))
            .limit(top_n)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        return [
            {
                "lemma": row.lemma,
                "total_frequency": row.total_frequency,
                "avg_tfidf_score": float(row.avg_tfidf_score),
                "content_count": row.content_count,
                "example_word": row.example_word,
            }
            for row in rows
        ]

    async def get_aggregated_entities_for_job(
        self, job_id: int, top_n: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get aggregated entity statistics for a scraping job.

        Args:
            job_id: Scraping job ID
            top_n: Number of top entities to return

        Returns:
            List of dictionaries with aggregated entity data
        """
        # Join ExtractedEntity with WebsiteContent to filter by job
        stmt = (
            select(
                ExtractedEntity.text,
                ExtractedEntity.label,
                func.count(ExtractedEntity.id).label("frequency"),
                func.count(
                    ExtractedEntity.website_content_id.distinct()
                ).label("content_count"),
            )
            .join(
                WebsiteContent,
                ExtractedEntity.website_content_id == WebsiteContent.id,
            )
            .where(WebsiteContent.scraping_job_id == job_id)
            .group_by(ExtractedEntity.text, ExtractedEntity.label)
            .order_by(desc("frequency"))
            .limit(top_n)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        return [
            {
                "text": row.text,
                "label": row.label,
                "frequency": row.frequency,
                "content_count": row.content_count,
            }
            for row in rows
        ]

    async def get_entity_counts_by_type_for_job(
        self, job_id: int
    ) -> Dict[str, int]:
        """
        Get entity counts grouped by type for a scraping job.

        Args:
            job_id: Scraping job ID

        Returns:
            Dictionary mapping entity types to counts
        """
        stmt = (
            select(
                ExtractedEntity.label,
                func.count(ExtractedEntity.id).label("count"),
            )
            .join(
                WebsiteContent,
                ExtractedEntity.website_content_id == WebsiteContent.id,
            )
            .where(WebsiteContent.scraping_job_id == job_id)
            .group_by(ExtractedEntity.label)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        return {row.label: row.count for row in rows}

    async def get_analysis_stats_for_job(self, job_id: int) -> Dict[str, int]:
        """
        Get analysis statistics for a scraping job.

        Args:
            job_id: Scraping job ID

        Returns:
            Dictionary with analysis statistics
        """
        # Count total contents
        total_stmt = (
            select(func.count(WebsiteContent.id))
            .where(WebsiteContent.scraping_job_id == job_id)
        )
        total_result = await self.session.execute(total_stmt)
        total_contents = total_result.scalar() or 0

        # Count analyzed contents
        analyzed_stmt = (
            select(func.count(ContentAnalysis.id))
            .join(
                WebsiteContent,
                ContentAnalysis.website_content_id == WebsiteContent.id,
            )
            .where(
                and_(
                    WebsiteContent.scraping_job_id == job_id,
                    ContentAnalysis.status == "completed",
                )
            )
        )
        analyzed_result = await self.session.execute(analyzed_stmt)
        analyzed_contents = analyzed_result.scalar() or 0

        # Count failed analyses
        failed_stmt = (
            select(func.count(ContentAnalysis.id))
            .join(
                WebsiteContent,
                ContentAnalysis.website_content_id == WebsiteContent.id,
            )
            .where(
                and_(
                    WebsiteContent.scraping_job_id == job_id,
                    ContentAnalysis.status == "failed",
                )
            )
        )
        failed_result = await self.session.execute(failed_stmt)
        failed_contents = failed_result.scalar() or 0

        return {
            "total_contents": total_contents,
            "analyzed_contents": analyzed_contents,
            "failed_contents": failed_contents,
        }

    async def get_content_with_analysis(
        self, content_id: int
    ) -> Optional[WebsiteContent]:
        """
        Get content with eagerly loaded analysis data.

        Args:
            content_id: Website content ID

        Returns:
            WebsiteContent with analysis relationships loaded
        """
        stmt = (
            select(WebsiteContent)
            .options(
                selectinload(WebsiteContent.extracted_nouns),
                selectinload(WebsiteContent.extracted_entities),
                selectinload(WebsiteContent.analysis),
            )
            .where(WebsiteContent.id == content_id)
        )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
