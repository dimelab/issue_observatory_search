"""Service for content analysis operations."""
import logging
import time
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.nlp.batch import BatchAnalyzer, BatchAnalysisResult
from backend.core.nlp.cache import get_analysis_cache
from backend.repositories.analysis_repository import AnalysisRepository
from backend.models.website import WebsiteContent
from backend.models.scraping import ScrapingJob
from backend.schemas.analysis import (
    AnalysisResultResponse,
    ExtractedNounResponse,
    ExtractedEntityResponse,
    NounsSummaryResponse,
    EntitiesSummaryResponse,
    AnalysisStatusResponse,
    AggregateNounResponse,
    AggregateEntityResponse,
    JobAggregateResponse,
)
from sqlalchemy import select

logger = logging.getLogger(__name__)


class AnalysisService:
    """
    Service for content analysis operations.

    Handles business logic for analyzing scraped content,
    including caching, batch processing, and result aggregation.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the analysis service.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.repository = AnalysisRepository(session)
        self.batch_analyzer = BatchAnalyzer()

    async def analyze_content(
        self,
        content_id: int,
        extract_nouns: bool = True,
        extract_entities: bool = True,
        max_nouns: int = 100,
        min_frequency: int = 2,
        force_refresh: bool = False,
    ) -> AnalysisResultResponse:
        """
        Analyze a single website content.

        This method:
        1. Checks cache for existing results (unless force_refresh)
        2. Fetches content from database
        3. Runs NLP analysis
        4. Stores results in database
        5. Caches results
        6. Returns structured response

        Args:
            content_id: Website content ID
            extract_nouns: Whether to extract nouns
            extract_entities: Whether to extract entities
            max_nouns: Maximum nouns to extract
            min_frequency: Minimum noun frequency
            force_refresh: Skip cache and re-analyze

        Returns:
            AnalysisResultResponse with extracted data

        Raises:
            ValueError: If content not found or has no text
        """
        logger.info(f"Analyzing content {content_id}")

        # Check cache first
        if not force_refresh:
            cache = await get_analysis_cache()
            cached_result = await cache.get_cached_analysis(content_id)
            if cached_result:
                logger.info(f"Returning cached analysis for content {content_id}")
                return AnalysisResultResponse(**cached_result)

        # Fetch content
        stmt = select(WebsiteContent).where(WebsiteContent.id == content_id)
        result = await self.session.execute(stmt)
        content = result.scalar_one_or_none()

        if not content:
            raise ValueError(f"Content with ID {content_id} not found")

        if not content.extracted_text:
            raise ValueError(f"Content {content_id} has no extracted text")

        # Create or get analysis record
        analysis = await self.repository.get_analysis_by_content_id(content_id)
        if not analysis:
            analysis = await self.repository.create_analysis(
                content_id=content_id,
                extract_nouns=extract_nouns,
                extract_entities=extract_entities,
                max_nouns=max_nouns,
                min_frequency=min_frequency,
            )
            await self.session.commit()
        else:
            # Update analysis record to processing
            await self.repository.update_analysis_status(
                analysis.id, "processing"
            )
            await self.session.commit()

        # Perform analysis
        start_time = time.time()

        try:
            batch_result = await self.batch_analyzer.process_single(
                text=content.extracted_text,
                language=content.language or "en",
                extract_nouns=extract_nouns,
                extract_entities=extract_entities,
                max_nouns=max_nouns,
                min_frequency=min_frequency,
                content_id=content_id,
            )

            if not batch_result.success:
                raise Exception(batch_result.error or "Analysis failed")

            # Store results in database
            await self._store_analysis_results(
                content_id=content_id,
                language=content.language or "en",
                nouns=batch_result.nouns,
                entities=batch_result.entities,
            )

            # Update analysis status
            processing_duration = time.time() - start_time
            await self.repository.update_analysis_status(
                analysis_id=analysis.id,
                status="completed",
                nouns_count=len(batch_result.nouns),
                entities_count=len(batch_result.entities),
                processing_duration=processing_duration,
            )

            await self.session.commit()

            # Build response
            response = AnalysisResultResponse(
                content_id=content_id,
                url=content.url,
                language=content.language,
                word_count=content.word_count,
                status="completed",
                nouns=[
                    ExtractedNounResponse(
                        word=n.word,
                        lemma=n.lemma,
                        frequency=n.frequency,
                        tfidf_score=n.tfidf_score,
                        positions=n.positions,
                    )
                    for n in batch_result.nouns
                ],
                entities=[
                    ExtractedEntityResponse(
                        text=e.text,
                        label=e.label,
                        start_pos=e.start,
                        end_pos=e.end,
                        confidence=e.confidence,
                    )
                    for e in batch_result.entities
                ],
                analyzed_at=datetime.utcnow(),
                processing_duration=processing_duration,
            )

            # Cache result
            cache = await get_analysis_cache()
            await cache.cache_analysis(content_id, response.dict())

            logger.info(
                f"Successfully analyzed content {content_id} in "
                f"{processing_duration:.2f}s"
            )

            return response

        except Exception as e:
            logger.error(f"Error analyzing content {content_id}: {e}")

            # Update analysis status to failed
            await self.repository.update_analysis_status(
                analysis_id=analysis.id,
                status="failed",
                error_message=str(e),
            )
            await self.session.commit()

            raise

    async def analyze_batch(
        self,
        content_ids: List[int],
        extract_nouns: bool = True,
        extract_entities: bool = True,
        max_nouns: int = 100,
        min_frequency: int = 2,
    ) -> Dict[str, Any]:
        """
        Analyze multiple contents in batch.

        Args:
            content_ids: List of content IDs to analyze
            extract_nouns: Whether to extract nouns
            extract_entities: Whether to extract entities
            max_nouns: Maximum nouns per document
            min_frequency: Minimum noun frequency

        Returns:
            Dictionary with batch statistics
        """
        logger.info(f"Starting batch analysis of {len(content_ids)} contents")

        # Fetch all contents
        stmt = select(WebsiteContent).where(WebsiteContent.id.in_(content_ids))
        result = await self.session.execute(stmt)
        contents = list(result.scalars().all())

        if not contents:
            raise ValueError("No contents found with provided IDs")

        # Filter contents with text
        valid_contents = [c for c in contents if c.extracted_text]
        logger.info(
            f"Found {len(valid_contents)} contents with extracted text"
        )

        if not valid_contents:
            raise ValueError("No contents have extracted text")

        # Create analysis records
        for content in valid_contents:
            existing = await self.repository.get_analysis_by_content_id(
                content.id
            )
            if not existing:
                await self.repository.create_analysis(
                    content_id=content.id,
                    extract_nouns=extract_nouns,
                    extract_entities=extract_entities,
                    max_nouns=max_nouns,
                    min_frequency=min_frequency,
                )

        await self.session.commit()

        # Perform batch analysis
        texts = [c.extracted_text for c in valid_contents]
        languages = [c.language or "en" for c in valid_contents]
        ids = [c.id for c in valid_contents]

        # Assume all same language for batch (could be improved)
        primary_language = max(set(languages), key=languages.count)

        start_time = time.time()

        batch_results = await self.batch_analyzer.process_batch(
            texts=texts,
            language=primary_language,
            extract_nouns=extract_nouns,
            extract_entities=extract_entities,
            max_nouns=max_nouns,
            min_frequency=min_frequency,
            content_ids=ids,
            use_corpus=True,
        )

        # Store results for each content
        successful = 0
        failed = 0

        for content, batch_result in zip(valid_contents, batch_results):
            analysis = await self.repository.get_analysis_by_content_id(
                content.id
            )

            if batch_result.success:
                try:
                    await self._store_analysis_results(
                        content_id=content.id,
                        language=content.language or "en",
                        nouns=batch_result.nouns,
                        entities=batch_result.entities,
                    )

                    await self.repository.update_analysis_status(
                        analysis_id=analysis.id,
                        status="completed",
                        nouns_count=len(batch_result.nouns),
                        entities_count=len(batch_result.entities),
                        processing_duration=batch_result.processing_time,
                    )

                    successful += 1

                except Exception as e:
                    logger.error(
                        f"Error storing results for content {content.id}: {e}"
                    )
                    await self.repository.update_analysis_status(
                        analysis_id=analysis.id,
                        status="failed",
                        error_message=str(e),
                    )
                    failed += 1

            else:
                await self.repository.update_analysis_status(
                    analysis_id=analysis.id,
                    status="failed",
                    error_message=batch_result.error,
                )
                failed += 1

        await self.session.commit()

        total_time = time.time() - start_time

        result = {
            "total_contents": len(content_ids),
            "processed": len(valid_contents),
            "successful": successful,
            "failed": failed,
            "processing_time": total_time,
        }

        logger.info(
            f"Batch analysis completed: {successful} successful, "
            f"{failed} failed in {total_time:.2f}s"
        )

        return result

    async def get_analysis_status(
        self, content_id: int
    ) -> Optional[AnalysisStatusResponse]:
        """
        Get analysis status for a content.

        Args:
            content_id: Website content ID

        Returns:
            AnalysisStatusResponse or None if not analyzed
        """
        analysis = await self.repository.get_analysis_by_content_id(content_id)
        if not analysis:
            return None

        return AnalysisStatusResponse(
            content_id=content_id,
            status=analysis.status,
            extract_nouns=analysis.extract_nouns,
            extract_entities=analysis.extract_entities,
            max_nouns=analysis.max_nouns,
            min_frequency=analysis.min_frequency,
            nouns_count=analysis.nouns_count,
            entities_count=analysis.entities_count,
            processing_duration=analysis.processing_duration,
            error_message=analysis.error_message,
            started_at=analysis.started_at,
            completed_at=analysis.completed_at,
            created_at=analysis.created_at,
            updated_at=analysis.updated_at,
        )

    async def get_nouns(
        self, content_id: int, limit: Optional[int] = None
    ) -> NounsSummaryResponse:
        """
        Get extracted nouns for a content.

        Args:
            content_id: Website content ID
            limit: Optional limit on results

        Returns:
            NounsSummaryResponse with nouns
        """
        # Check cache
        cache = await get_analysis_cache()
        cached_nouns = await cache.get_cached_nouns(content_id)

        if cached_nouns:
            nouns_data = cached_nouns[:limit] if limit else cached_nouns
        else:
            nouns = await self.repository.get_nouns_by_content_id(
                content_id, limit
            )
            nouns_data = [
                {
                    "word": n.word,
                    "lemma": n.lemma,
                    "frequency": n.frequency,
                    "tfidf_score": n.tfidf_score,
                    "positions": n.positions,
                }
                for n in nouns
            ]

            # Cache result
            await cache.cache_nouns(content_id, nouns_data)

        # Get content language
        stmt = select(WebsiteContent).where(WebsiteContent.id == content_id)
        result = await self.session.execute(stmt)
        content = result.scalar_one_or_none()

        return NounsSummaryResponse(
            content_id=content_id,
            language=content.language if content else None,
            nouns=[ExtractedNounResponse(**n) for n in nouns_data],
            total_count=len(nouns_data),
        )

    async def get_entities(
        self,
        content_id: int,
        label: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> EntitiesSummaryResponse:
        """
        Get extracted entities for a content.

        Args:
            content_id: Website content ID
            label: Optional entity type filter
            limit: Optional limit on results

        Returns:
            EntitiesSummaryResponse with entities
        """
        # Check cache
        cache = await get_analysis_cache()
        cached_entities = await cache.get_cached_entities(content_id)

        if cached_entities and not label:  # Cache doesn't support filtering
            entities_data = cached_entities[:limit] if limit else cached_entities
        else:
            entities = await self.repository.get_entities_by_content_id(
                content_id, label, limit
            )
            entities_data = [
                {
                    "text": e.text,
                    "label": e.label,
                    "start_pos": e.start_pos,
                    "end_pos": e.end_pos,
                    "confidence": e.confidence,
                }
                for e in entities
            ]

            # Cache result (only if no filter)
            if not label:
                await cache.cache_entities(content_id, entities_data)

        # Get content language
        stmt = select(WebsiteContent).where(WebsiteContent.id == content_id)
        result = await self.session.execute(stmt)
        content = result.scalar_one_or_none()

        # Count entities by type
        entities_by_type = {}
        for e in entities_data:
            label_key = e["label"]
            entities_by_type[label_key] = entities_by_type.get(label_key, 0) + 1

        return EntitiesSummaryResponse(
            content_id=content_id,
            language=content.language if content else None,
            entities=[ExtractedEntityResponse(**e) for e in entities_data],
            total_count=len(entities_data),
            entities_by_type=entities_by_type,
        )

    async def get_job_aggregate(
        self, job_id: int, top_n: int = 50
    ) -> JobAggregateResponse:
        """
        Get aggregated analysis results for a scraping job.

        Args:
            job_id: Scraping job ID
            top_n: Number of top items to return

        Returns:
            JobAggregateResponse with aggregated data
        """
        # Get statistics
        stats = await self.repository.get_analysis_stats_for_job(job_id)

        # Get top nouns
        nouns_data = await self.repository.get_aggregated_nouns_for_job(
            job_id, top_n
        )

        # Get top entities
        entities_data = await self.repository.get_aggregated_entities_for_job(
            job_id, top_n
        )

        # Get entity counts by type
        entities_by_type = (
            await self.repository.get_entity_counts_by_type_for_job(job_id)
        )

        return JobAggregateResponse(
            job_id=job_id,
            total_contents=stats["total_contents"],
            analyzed_contents=stats["analyzed_contents"],
            failed_contents=stats["failed_contents"],
            top_nouns=[AggregateNounResponse(**n) for n in nouns_data],
            top_entities=[AggregateEntityResponse(**e) for e in entities_data],
            entities_by_type=entities_by_type,
        )

    async def delete_analysis(self, content_id: int) -> bool:
        """
        Delete analysis results for a content.

        Args:
            content_id: Website content ID

        Returns:
            True if deleted, False if not found
        """
        # Invalidate cache
        cache = await get_analysis_cache()
        await cache.invalidate_analysis(content_id)

        # Delete from database
        deleted = await self.repository.delete_analysis(content_id)
        await self.session.commit()

        if deleted:
            logger.info(f"Deleted analysis for content {content_id}")

        return deleted

    async def _store_analysis_results(
        self,
        content_id: int,
        language: str,
        nouns: List,
        entities: List,
    ):
        """
        Store analysis results in database.

        Args:
            content_id: Website content ID
            language: Language code
            nouns: List of ExtractedNoun objects
            entities: List of ExtractedEntity objects
        """
        # Delete existing results
        await self.repository.delete_nouns_by_content_id(content_id)
        await self.repository.delete_entities_by_content_id(content_id)

        # Store nouns
        if nouns:
            nouns_data = [
                {
                    "website_content_id": content_id,
                    "word": n.word,
                    "lemma": n.lemma,
                    "frequency": n.frequency,
                    "tfidf_score": n.tfidf_score,
                    "positions": n.positions,
                    "language": language,
                }
                for n in nouns
            ]
            await self.repository.bulk_create_nouns(nouns_data)

        # Store entities
        if entities:
            entities_data = [
                {
                    "website_content_id": content_id,
                    "text": e.text,
                    "label": e.label,
                    "start_pos": e.start,
                    "end_pos": e.end,
                    "confidence": e.confidence,
                    "language": language,
                }
                for e in entities
            ]
            await self.repository.bulk_create_entities(entities_data)

        logger.debug(
            f"Stored {len(nouns)} nouns and {len(entities)} entities "
            f"for content {content_id}"
        )
