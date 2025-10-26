"""Named Entity Recognition (NER) using spaCy."""
import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict
from collections import Counter

from backend.core.nlp.models import nlp_model_manager
from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    """
    Represents a named entity extracted from text.

    Attributes:
        text: The entity text as it appears in the document
        label: Entity type (PERSON, ORG, GPE, LOC, DATE, EVENT, PRODUCT, etc.)
        start: Character position where entity starts
        end: Character position where entity ends
        confidence: Optional confidence score (if available from model)
    """

    text: str
    label: str
    start: int
    end: int
    confidence: Optional[float] = None

    def __repr__(self) -> str:
        """String representation of ExtractedEntity."""
        conf_str = f", conf={self.confidence:.2f}" if self.confidence else ""
        return f"ExtractedEntity(text='{self.text}', label='{self.label}'{conf_str})"


class NamedEntityExtractor:
    """
    Extract named entities from text using spaCy's NER models.

    Named entities are real-world objects like persons, organizations,
    locations, dates, etc. This class provides filtering, deduplication,
    and frequency analysis.

    Supported entity types (depends on spaCy model):
    - PERSON: People, including fictional
    - ORG: Companies, agencies, institutions
    - GPE: Countries, cities, states (geopolitical entities)
    - LOC: Non-GPE locations, mountain ranges, bodies of water
    - DATE: Absolute or relative dates or periods
    - TIME: Times smaller than a day
    - MONEY: Monetary values
    - PERCENT: Percentage values
    - FACILITY: Buildings, airports, highways, bridges
    - PRODUCT: Objects, vehicles, foods, etc.
    - EVENT: Named hurricanes, battles, wars, sports events
    - LAW: Named documents made into laws
    - LANGUAGE: Any named language
    - WORK_OF_ART: Titles of books, songs, etc.

    Example:
        >>> extractor = NamedEntityExtractor()
        >>> text = "Apple Inc. was founded by Steve Jobs in Cupertino, California."
        >>> entities = await extractor.extract_entities(text, language="en")
        >>> for entity in entities:
        ...     print(f"{entity.text} ({entity.label})")
        Apple Inc. (ORG)
        Steve Jobs (PERSON)
        Cupertino (GPE)
        California (GPE)
    """

    # Entity types to extract by default
    DEFAULT_ENTITY_TYPES = [
        "PERSON",
        "ORG",
        "GPE",
        "LOC",
        "DATE",
        "EVENT",
        "PRODUCT",
    ]

    async def extract_entities(
        self,
        text: str,
        language: str = "en",
        entity_types: Optional[List[str]] = None,
        min_confidence: float = 0.0,
        deduplicate: bool = True,
    ) -> List[ExtractedEntity]:
        """
        Extract named entities from text.

        Args:
            text: The text to extract entities from
            language: ISO 639-1 language code (e.g., "en", "da")
            entity_types: List of entity types to extract (e.g., ["PERSON", "ORG"]).
                         If None, uses DEFAULT_ENTITY_TYPES.
            min_confidence: Minimum confidence score (0.0-1.0). Currently not
                           used as spaCy doesn't provide confidence by default.
            deduplicate: If True, remove duplicate entities (same text + label)

        Returns:
            List of ExtractedEntity objects

        Raises:
            ValueError: If text is empty or language is unsupported
            RuntimeError: If spaCy model is not installed
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for entity extraction")
            return []

        # Check text length and truncate if necessary
        if len(text) > settings.nlp_max_text_length:
            logger.warning(
                f"Text length {len(text)} exceeds maximum "
                f"{settings.nlp_max_text_length}, truncating"
            )
            text = text[: settings.nlp_max_text_length]

        # Use default entity types if none provided
        if entity_types is None:
            entity_types = self.DEFAULT_ENTITY_TYPES

        logger.debug(
            f"Extracting entities from text (length: {len(text)}, "
            f"language: {language}, types: {entity_types})"
        )

        # Get spaCy model
        nlp = await nlp_model_manager.get_model(language)

        # Process text in executor to avoid blocking
        loop = asyncio.get_event_loop()
        doc = await loop.run_in_executor(None, nlp, text)

        # Extract entities
        entities = []
        seen_entities = set()  # For deduplication

        for ent in doc.ents:
            # Filter by entity type
            if ent.label_ not in entity_types:
                continue

            # Skip very short entities (likely noise)
            if len(ent.text.strip()) < 2:
                continue

            # Create entity object
            entity = ExtractedEntity(
                text=ent.text.strip(),
                label=ent.label_,
                start=ent.start_char,
                end=ent.end_char,
                confidence=None,  # spaCy doesn't provide confidence by default
            )

            # Deduplicate if requested
            if deduplicate:
                entity_key = (entity.text.lower(), entity.label)
                if entity_key in seen_entities:
                    continue
                seen_entities.add(entity_key)

            entities.append(entity)

        logger.info(
            f"Extracted {len(entities)} entities from text of {len(text)} characters"
        )

        return entities

    async def extract_entities_with_counts(
        self,
        text: str,
        language: str = "en",
        entity_types: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, int]]:
        """
        Extract entities and return with frequency counts.

        This is useful for understanding which entities are most prominent
        in the text.

        Args:
            text: The text to extract entities from
            language: ISO 639-1 language code
            entity_types: List of entity types to extract

        Returns:
            Dictionary mapping entity types to dictionaries of entity text -> count

        Example:
            >>> result = await extractor.extract_entities_with_counts(text)
            >>> print(result["PERSON"])
            {"Steve Jobs": 3, "Tim Cook": 1}
        """
        # Extract entities without deduplication
        entities = await self.extract_entities(
            text=text,
            language=language,
            entity_types=entity_types,
            deduplicate=False,
        )

        # Count entities by type
        entity_counts: Dict[str, Counter] = {}

        for entity in entities:
            if entity.label not in entity_counts:
                entity_counts[entity.label] = Counter()

            entity_counts[entity.label][entity.text] += 1

        # Convert Counter to dict
        result = {
            label: dict(counter) for label, counter in entity_counts.items()
        }

        logger.debug(
            f"Entity counts by type: {[(k, len(v)) for k, v in result.items()]}"
        )

        return result

    async def extract_entities_batch(
        self,
        texts: List[str],
        language: str = "en",
        entity_types: Optional[List[str]] = None,
    ) -> List[List[ExtractedEntity]]:
        """
        Extract entities from multiple texts in batch.

        This processes multiple texts in parallel for better performance.

        Args:
            texts: List of texts to process
            language: ISO 639-1 language code
            entity_types: List of entity types to extract

        Returns:
            List of entity lists, one per input text
        """
        if not texts:
            return []

        logger.info(f"Batch extracting entities from {len(texts)} texts")

        # Process texts in parallel
        tasks = [
            self.extract_entities(
                text=text, language=language, entity_types=entity_types
            )
            for text in texts
        ]

        results = await asyncio.gather(*tasks)

        logger.info(f"Completed batch entity extraction for {len(texts)} texts")

        return results

    def get_entity_types(self, language: str = "en") -> List[str]:
        """
        Get available entity types for a language.

        Args:
            language: ISO 639-1 language code

        Returns:
            List of entity type labels

        Note:
            This is synchronous as it just returns known types.
            Actual availability depends on the spaCy model.
        """
        # Common entity types across most spaCy models
        common_types = [
            "PERSON",
            "ORG",
            "GPE",
            "LOC",
            "DATE",
            "TIME",
            "MONEY",
            "PERCENT",
            "FACILITY",
            "PRODUCT",
            "EVENT",
            "LAW",
            "LANGUAGE",
            "WORK_OF_ART",
        ]

        # Language-specific adjustments
        if language == "da":
            # Danish model might have different labels
            return ["PER", "ORG", "LOC", "MISC"] + common_types

        return common_types

    def filter_entities_by_type(
        self, entities: List[ExtractedEntity], entity_types: List[str]
    ) -> List[ExtractedEntity]:
        """
        Filter entities by type.

        Args:
            entities: List of entities to filter
            entity_types: Entity types to keep

        Returns:
            Filtered list of entities
        """
        return [ent for ent in entities if ent.label in entity_types]

    def group_entities_by_type(
        self, entities: List[ExtractedEntity]
    ) -> Dict[str, List[ExtractedEntity]]:
        """
        Group entities by their type.

        Args:
            entities: List of entities to group

        Returns:
            Dictionary mapping entity types to lists of entities
        """
        grouped: Dict[str, List[ExtractedEntity]] = {}

        for entity in entities:
            if entity.label not in grouped:
                grouped[entity.label] = []
            grouped[entity.label].append(entity)

        return grouped
