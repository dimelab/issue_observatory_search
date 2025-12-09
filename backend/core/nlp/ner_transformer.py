"""
Transformer-based multilingual Named Entity Recognition (NER).

Based on implementation from some2net (github.com/dimelab/some2net)
Adapted for Issue Observatory Search v6.0.0

This module provides transformer-based NER using the Hugging Face transformers library.
It supports multilingual models like Davlan/xlm-roberta-base-ner-hrl for 10+ languages.

Note: This adds significant dependencies (~2GB). Consider making it optional via feature flag.
"""
import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict
from collections import Counter

logger = logging.getLogger(__name__)

# Import transformers only when needed to avoid heavy dependency load
try:
    from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
    import torch

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning(
        "Transformers library not available. Transformer-based NER will not work. "
        "Install with: pip install transformers torch"
    )


@dataclass
class ExtractedEntity:
    """
    Represents a named entity extracted from text.

    Attributes:
        text: The entity text (e.g., "Barack Obama")
        entity_type: Entity type (e.g., "PER", "ORG", "LOC", "MISC")
        confidence: Model confidence score (0.0-1.0)
        start: Start character position in text
        end: End character position in text
        frequency: Number of times this entity appears (after aggregation)
    """

    text: str
    entity_type: str
    confidence: float
    start: Optional[int] = None
    end: Optional[int] = None
    frequency: int = 1

    def __repr__(self) -> str:
        """String representation of ExtractedEntity."""
        return (
            f"ExtractedEntity(text='{self.text}', type={self.entity_type}, "
            f"confidence={self.confidence:.4f}, freq={self.frequency})"
        )


class TransformerNERExtractor:
    """
    Multilingual NER using transformer models.

    Based on some2net implementation with Davlan/xlm-roberta-base-ner-hrl model.
    This model supports 10+ languages including English and Danish.

    Entity Types (depending on model):
    - PER/PERSON: Person names
    - ORG: Organizations, companies, agencies
    - LOC/GPE: Locations, geopolitical entities
    - MISC: Miscellaneous entities

    Key Features:
    - Multilingual support (English, Danish, and 8+ other languages)
    - Confidence scoring for each entity
    - Aggregation of repeated entities
    - Configurable confidence threshold
    - GPU support for faster inference

    Example:
        >>> extractor = TransformerNERExtractor(
        ...     model_name="Davlan/xlm-roberta-base-ner-hrl",
        ...     confidence_threshold=0.85
        ... )
        >>> entities = await extractor.extract_entities(
        ...     text="Barack Obama was president of the United States.",
        ...     language="en",
        ...     entity_types=["PER", "ORG", "LOC"]
        ... )
        >>> for entity in entities:
        ...     print(f"{entity.text} ({entity.entity_type}): {entity.confidence:.2f}")

    Performance Considerations:
    - First load: ~2GB model download + initialization (~10-30s)
    - CPU inference: ~5-10s per document
    - GPU inference: ~1-2s per document
    - Memory: ~2GB RAM for model + ~500MB per batch
    """

    def __init__(
        self,
        model_name: str = "Davlan/xlm-roberta-base-ner-hrl",
        confidence_threshold: float = 0.85,
        device: int = -1,
        cache_dir: Optional[str] = None,
    ):
        """
        Initialize transformer-based NER.

        Args:
            model_name: Hugging Face model identifier.
                       Default: "Davlan/xlm-roberta-base-ner-hrl" (multilingual)
                       Other options: "dslim/bert-base-NER", "dbmdz/bert-large-cased-finetuned-conll03-english"
            confidence_threshold: Minimum confidence score (0.0-1.0) for including entities.
                                 Higher values = more precise but may miss some entities
            device: Device for inference
                   -1 = CPU (slower but no GPU required)
                   0+ = GPU device number (faster, requires CUDA)
            cache_dir: Optional directory to cache downloaded models.
                      If None, uses Hugging Face default cache (~/.cache/huggingface)

        Raises:
            ImportError: If transformers library is not installed
            RuntimeError: If model loading fails
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "Transformers library is required for transformer-based NER. "
                "Install with: pip install transformers torch"
            )

        self.model_name = model_name
        self.confidence_threshold = max(0.0, min(1.0, confidence_threshold))
        self.device = device
        self.cache_dir = cache_dir

        self.pipeline = None
        self._model_loaded = False

        logger.info(
            f"Initialized TransformerNERExtractor: model={model_name}, "
            f"threshold={self.confidence_threshold}, device={device}"
        )

    async def _load_model(self):
        """
        Lazy-load the transformer model and pipeline.

        This is done lazily to avoid loading the model until it's actually needed,
        which saves memory and startup time.
        """
        if self._model_loaded:
            return

        logger.info(f"Loading transformer NER model: {self.model_name}")

        try:
            # Load model in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()

            def _load():
                """Internal function to load model."""
                # Determine device
                device_id = self.device
                if device_id >= 0 and torch.cuda.is_available():
                    device_str = f"cuda:{device_id}"
                    logger.info(f"Using GPU device: {device_str}")
                else:
                    device_str = "cpu"
                    if device_id >= 0:
                        logger.warning(
                            f"GPU device {device_id} requested but CUDA not available. "
                            f"Falling back to CPU."
                        )

                # Create pipeline
                ner_pipeline = pipeline(
                    "ner",
                    model=self.model_name,
                    tokenizer=self.model_name,
                    aggregation_strategy="simple",  # Aggregate subword tokens
                    device=device_str,
                    cache_dir=self.cache_dir,
                )

                return ner_pipeline

            self.pipeline = await loop.run_in_executor(None, _load)
            self._model_loaded = True

            logger.info(
                f"Successfully loaded transformer NER model: {self.model_name}"
            )

        except Exception as e:
            logger.error(f"Failed to load transformer NER model: {e}")
            raise RuntimeError(
                f"Could not load transformer model '{self.model_name}'. "
                f"Ensure transformers and torch are installed and the model is available."
            ) from e

    async def extract_entities(
        self,
        text: str,
        language: str,
        entity_types: Optional[List[str]] = None,
        max_entities: int = 100,
    ) -> List[ExtractedEntity]:
        """
        Extract named entities using transformer model.

        This method:
        1. Loads the model (lazy loading on first call)
        2. Runs NER inference on the text
        3. Filters by confidence threshold
        4. Filters by entity types (if specified)
        5. Aggregates duplicate entities
        6. Returns top N entities by confidence

        Args:
            text: The text to extract entities from
            language: ISO 639-1 language code (e.g., "en", "da")
                     Note: This parameter is for consistency with other extractors.
                     The multilingual model handles language detection automatically.
            entity_types: List of entity types to include (e.g., ["PER", "ORG", "LOC"])
                         If None, all entity types are included.
                         Common types: PER, ORG, LOC, MISC
            max_entities: Maximum number of unique entities to return

        Returns:
            List of ExtractedEntity objects sorted by confidence (descending)

        Example:
            >>> text = "Apple Inc. CEO Tim Cook announced new products in California."
            >>> entities = await extractor.extract_entities(
            ...     text=text,
            ...     language="en",
            ...     entity_types=["PER", "ORG", "LOC"]
            ... )
            >>> # Returns: [ExtractedEntity("Apple Inc.", "ORG", 0.98), ...]
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for NER extraction")
            return []

        # Load model if not already loaded
        await self._load_model()

        logger.debug(
            f"Extracting entities from text (length: {len(text)}, language: {language})"
        )

        # Run NER in executor to avoid blocking
        loop = asyncio.get_event_loop()

        def _extract():
            """Internal function to run NER."""
            try:
                # Run pipeline
                results = self.pipeline(text)
                return results
            except Exception as e:
                logger.error(f"NER extraction failed: {e}")
                return []

        ner_results = await loop.run_in_executor(None, _extract)

        if not ner_results:
            logger.info("No entities extracted by transformer NER")
            return []

        # Convert to ExtractedEntity objects and filter
        entities_dict: Dict[str, ExtractedEntity] = {}

        for result in ner_results:
            # Extract fields
            entity_text = result.get("word", "").strip()
            entity_type = result.get("entity_group", "MISC")
            confidence = result.get("score", 0.0)
            start = result.get("start")
            end = result.get("end")

            # Skip if below confidence threshold
            if confidence < self.confidence_threshold:
                continue

            # Skip if not in requested entity types
            if entity_types and entity_type not in entity_types:
                continue

            # Skip empty entities
            if not entity_text:
                continue

            # Normalize entity text (lowercase for aggregation)
            entity_key = entity_text.lower()

            # Aggregate duplicate entities
            if entity_key in entities_dict:
                # Update frequency and take max confidence
                entities_dict[entity_key].frequency += 1
                entities_dict[entity_key].confidence = max(
                    entities_dict[entity_key].confidence, confidence
                )
            else:
                # Create new entity
                entities_dict[entity_key] = ExtractedEntity(
                    text=entity_text,
                    entity_type=entity_type,
                    confidence=confidence,
                    start=start,
                    end=end,
                    frequency=1,
                )

        # Convert to list and sort by confidence
        entities = list(entities_dict.values())
        entities.sort(key=lambda x: x.confidence, reverse=True)

        # Limit to max_entities
        entities = entities[:max_entities]

        logger.info(
            f"Extracted {len(entities)} unique entities "
            f"(from {len(ner_results)} raw detections)"
        )

        return entities

    async def extract_entities_batch(
        self,
        texts: List[str],
        language: str,
        entity_types: Optional[List[str]] = None,
        max_entities: int = 100,
    ) -> List[List[ExtractedEntity]]:
        """
        Extract entities from multiple texts in batch.

        This processes texts in parallel for better performance.

        Args:
            texts: List of texts to process
            language: ISO 639-1 language code
            entity_types: List of entity types to include
            max_entities: Maximum entities per text

        Returns:
            List of entity lists, one per input text
        """
        if not texts:
            return []

        logger.info(f"Batch extracting entities from {len(texts)} texts")

        # Process texts in parallel
        tasks = [
            self.extract_entities(
                text=text,
                language=language,
                entity_types=entity_types,
                max_entities=max_entities,
            )
            for text in texts
        ]

        results = await asyncio.gather(*tasks)

        logger.info(f"Completed batch entity extraction for {len(texts)} texts")

        return results

    def clear_model(self):
        """
        Clear the loaded model from memory.

        Use this to free up GPU/CPU memory when the model is no longer needed.
        """
        if self._model_loaded:
            logger.info("Clearing transformer NER model from memory")
            self.pipeline = None
            self._model_loaded = False

            # Force garbage collection
            import gc

            gc.collect()

            # Clear CUDA cache if using GPU
            if self.device >= 0 and torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.info("Cleared CUDA cache")
