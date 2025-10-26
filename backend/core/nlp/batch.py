"""Batch processing for analyzing multiple documents efficiently."""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import time

from backend.core.nlp.noun_extraction import NounExtractor, ExtractedNoun
from backend.core.nlp.ner import NamedEntityExtractor, ExtractedEntity
from backend.core.nlp.models import nlp_model_manager
from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class BatchAnalysisResult:
    """
    Result of analyzing a single document in a batch.

    Attributes:
        content_id: Website content ID (if provided)
        nouns: List of extracted nouns
        entities: List of extracted entities
        processing_time: Time taken to process (seconds)
        success: Whether processing succeeded
        error: Error message if failed
    """

    content_id: Optional[int] = None
    nouns: List[ExtractedNoun] = None
    entities: List[ExtractedEntity] = None
    processing_time: float = 0.0
    success: bool = True
    error: Optional[str] = None

    def __post_init__(self):
        """Initialize empty lists if None."""
        if self.nouns is None:
            self.nouns = []
        if self.entities is None:
            self.entities = []


class BatchAnalyzer:
    """
    Efficiently process multiple documents in batches.

    Features:
    - Parallel processing with configurable concurrency
    - Shared NLP models across batch
    - Progress tracking
    - Error handling per document
    - Optimized for throughput

    Example:
        >>> analyzer = BatchAnalyzer()
        >>> texts = ["Document 1", "Document 2", "Document 3"]
        >>> results = await analyzer.process_batch(
        ...     texts=texts,
        ...     language="en",
        ...     extract_nouns=True,
        ...     extract_entities=True
        ... )
    """

    def __init__(
        self,
        batch_size: Optional[int] = None,
        max_workers: Optional[int] = None,
    ):
        """
        Initialize the batch analyzer.

        Args:
            batch_size: Number of documents to process in parallel.
                       Defaults to settings.nlp_batch_size.
            max_workers: Maximum concurrent workers.
                        Defaults to settings.nlp_max_workers.
        """
        self.batch_size = batch_size or settings.nlp_batch_size
        self.max_workers = max_workers or settings.nlp_max_workers
        self.noun_extractor = NounExtractor()
        self.entity_extractor = NamedEntityExtractor()

    async def process_single(
        self,
        text: str,
        language: str = "en",
        extract_nouns: bool = True,
        extract_entities: bool = True,
        max_nouns: int = 100,
        min_frequency: int = 2,
        content_id: Optional[int] = None,
        corpus: Optional[List[str]] = None,
    ) -> BatchAnalysisResult:
        """
        Process a single document.

        Args:
            text: Text to analyze
            language: ISO 639-1 language code
            extract_nouns: Whether to extract nouns
            extract_entities: Whether to extract entities
            max_nouns: Maximum nouns to extract
            min_frequency: Minimum frequency for nouns
            content_id: Optional content ID for tracking
            corpus: Optional corpus for TF-IDF calculation

        Returns:
            BatchAnalysisResult with extracted data
        """
        start_time = time.time()
        result = BatchAnalysisResult(content_id=content_id)

        try:
            # Extract nouns if requested
            if extract_nouns and text:
                try:
                    result.nouns = await self.noun_extractor.extract_nouns(
                        text=text,
                        language=language,
                        max_nouns=max_nouns,
                        min_frequency=min_frequency,
                        corpus=corpus,
                    )
                except Exception as e:
                    logger.error(
                        f"Error extracting nouns for content {content_id}: {e}"
                    )
                    result.nouns = []

            # Extract entities if requested
            if extract_entities and text:
                try:
                    result.entities = await self.entity_extractor.extract_entities(
                        text=text,
                        language=language,
                    )
                except Exception as e:
                    logger.error(
                        f"Error extracting entities for content {content_id}: {e}"
                    )
                    result.entities = []

            result.success = True

        except Exception as e:
            logger.error(f"Error processing content {content_id}: {e}")
            result.success = False
            result.error = str(e)

        result.processing_time = time.time() - start_time
        return result

    async def process_batch(
        self,
        texts: List[str],
        language: str = "en",
        extract_nouns: bool = True,
        extract_entities: bool = True,
        max_nouns: int = 100,
        min_frequency: int = 2,
        content_ids: Optional[List[int]] = None,
        use_corpus: bool = True,
    ) -> List[BatchAnalysisResult]:
        """
        Process multiple documents in parallel batches.

        This method optimally processes documents by:
        1. Pre-loading the NLP model
        2. Processing in chunks to limit memory usage
        3. Using the full batch as corpus for TF-IDF
        4. Running extractions in parallel with semaphore

        Args:
            texts: List of texts to analyze
            language: ISO 639-1 language code
            extract_nouns: Whether to extract nouns
            extract_entities: Whether to extract entities
            max_nouns: Maximum nouns per document
            min_frequency: Minimum noun frequency
            content_ids: Optional list of content IDs (same length as texts)
            use_corpus: Whether to use all texts as corpus for TF-IDF

        Returns:
            List of BatchAnalysisResult objects (same order as input)
        """
        if not texts:
            return []

        logger.info(
            f"Starting batch analysis of {len(texts)} documents "
            f"(language: {language}, batch_size: {self.batch_size})"
        )

        start_time = time.time()

        # Pre-load NLP model to avoid loading it multiple times
        try:
            await nlp_model_manager.get_model(language)
        except Exception as e:
            logger.error(f"Failed to load NLP model for {language}: {e}")
            # Return failed results for all documents
            return [
                BatchAnalysisResult(
                    content_id=content_ids[i] if content_ids else None,
                    success=False,
                    error=f"Failed to load NLP model: {e}",
                )
                for i in range(len(texts))
            ]

        # Prepare corpus if using TF-IDF
        corpus = texts if use_corpus and extract_nouns else None

        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self.max_workers)

        async def process_with_semaphore(index: int) -> BatchAnalysisResult:
            """Process a single document with semaphore."""
            async with semaphore:
                content_id = content_ids[index] if content_ids else None
                text = texts[index]

                # Build corpus without current document for TF-IDF
                doc_corpus = None
                if corpus and extract_nouns:
                    doc_corpus = [t for i, t in enumerate(corpus) if i != index]

                return await self.process_single(
                    text=text,
                    language=language,
                    extract_nouns=extract_nouns,
                    extract_entities=extract_entities,
                    max_nouns=max_nouns,
                    min_frequency=min_frequency,
                    content_id=content_id,
                    corpus=doc_corpus,
                )

        # Process all documents in parallel (limited by semaphore)
        tasks = [process_with_semaphore(i) for i in range(len(texts))]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions that occurred
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Exception processing document {i}: {result}")
                final_results.append(
                    BatchAnalysisResult(
                        content_id=content_ids[i] if content_ids else None,
                        success=False,
                        error=str(result),
                    )
                )
            else:
                final_results.append(result)

        total_time = time.time() - start_time
        successful = sum(1 for r in final_results if r.success)
        failed = len(final_results) - successful

        logger.info(
            f"Batch analysis completed in {total_time:.2f}s: "
            f"{successful} successful, {failed} failed "
            f"({len(texts) / total_time:.2f} docs/sec)"
        )

        return final_results

    async def process_chunks(
        self,
        texts: List[str],
        language: str = "en",
        extract_nouns: bool = True,
        extract_entities: bool = True,
        max_nouns: int = 100,
        min_frequency: int = 2,
        content_ids: Optional[List[int]] = None,
        chunk_size: Optional[int] = None,
    ) -> List[BatchAnalysisResult]:
        """
        Process documents in chunks to limit memory usage.

        This is useful for very large batches where processing all at once
        might consume too much memory.

        Args:
            texts: List of texts to analyze
            language: ISO 639-1 language code
            extract_nouns: Whether to extract nouns
            extract_entities: Whether to extract entities
            max_nouns: Maximum nouns per document
            min_frequency: Minimum noun frequency
            content_ids: Optional list of content IDs
            chunk_size: Size of each chunk (defaults to batch_size)

        Returns:
            List of BatchAnalysisResult objects (same order as input)
        """
        if not texts:
            return []

        chunk_size = chunk_size or self.batch_size
        all_results = []

        # Process in chunks
        for i in range(0, len(texts), chunk_size):
            chunk_texts = texts[i : i + chunk_size]
            chunk_ids = (
                content_ids[i : i + chunk_size] if content_ids else None
            )

            logger.info(
                f"Processing chunk {i // chunk_size + 1} "
                f"({len(chunk_texts)} documents)"
            )

            chunk_results = await self.process_batch(
                texts=chunk_texts,
                language=language,
                extract_nouns=extract_nouns,
                extract_entities=extract_entities,
                max_nouns=max_nouns,
                min_frequency=min_frequency,
                content_ids=chunk_ids,
                use_corpus=False,  # Don't use corpus across chunks
            )

            all_results.extend(chunk_results)

            # Small delay between chunks to prevent overwhelming the system
            if i + chunk_size < len(texts):
                await asyncio.sleep(0.1)

        return all_results

    def get_statistics(
        self, results: List[BatchAnalysisResult]
    ) -> Dict[str, Any]:
        """
        Calculate statistics from batch results.

        Args:
            results: List of batch analysis results

        Returns:
            Dictionary with statistics
        """
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful

        total_time = sum(r.processing_time for r in results)
        avg_time = total_time / total if total > 0 else 0

        total_nouns = sum(len(r.nouns) for r in results if r.success)
        total_entities = sum(len(r.entities) for r in results if r.success)

        avg_nouns = total_nouns / successful if successful > 0 else 0
        avg_entities = total_entities / successful if successful > 0 else 0

        return {
            "total_documents": total,
            "successful": successful,
            "failed": failed,
            "total_processing_time": total_time,
            "avg_processing_time": avg_time,
            "total_nouns": total_nouns,
            "total_entities": total_entities,
            "avg_nouns_per_doc": avg_nouns,
            "avg_entities_per_doc": avg_entities,
        }
