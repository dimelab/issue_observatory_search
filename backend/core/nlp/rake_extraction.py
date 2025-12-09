"""
RAKE-based keyword extraction with n-gram support.

Based on implementation from some2net (github.com/dimelab/some2net)
Adapted for Issue Observatory Search v6.0.0
"""
import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional

from rake_nltk import Rake

logger = logging.getLogger(__name__)


@dataclass
class RAKEKeyword:
    """
    Represents a keyword phrase extracted using RAKE algorithm.

    Attributes:
        phrase: The extracted keyword phrase (can be multiple words)
        score: RAKE importance score
        word_count: Number of words in the phrase (n-gram length)
    """

    phrase: str
    score: float
    word_count: int

    def __repr__(self) -> str:
        """String representation of RAKEKeyword."""
        return (
            f"RAKEKeyword(phrase='{self.phrase}', "
            f"score={self.score:.4f}, words={self.word_count})"
        )


class RAKEExtractor:
    """
    RAKE (Rapid Automatic Keyword Extraction) implementation.

    RAKE is a keyword extraction algorithm that identifies key phrases
    by analyzing word co-occurrence and word frequency patterns.

    Based on some2net implementation with enhancements for multilingual support.

    Key Features:
    - Extracts multi-word phrases (n-grams) as keywords
    - Language-aware stopword handling
    - Configurable phrase length
    - Scoring based on word degree and frequency ratios

    Example:
        >>> extractor = RAKEExtractor(language="english", max_phrase_length=3)
        >>> keywords = await extractor.extract_keywords(
        ...     text="Machine learning is transforming artificial intelligence research.",
        ...     max_keywords=5
        ... )
        >>> for kw in keywords:
        ...     print(f"{kw.phrase}: {kw.score:.4f}")
    """

    def __init__(
        self,
        language: str = "english",
        max_phrase_length: int = 3,
        min_keyword_frequency: int = 1,
    ):
        """
        Initialize RAKE extractor.

        Args:
            language: Language for stopwords. Supported: "english", "danish"
                     Maps to NLTK stopword corpora
            max_phrase_length: Maximum n-gram size (1-5 words).
                              Higher values extract longer phrases
            min_keyword_frequency: Minimum frequency threshold for a keyword
                                   to be included in results
        """
        # Map language codes to NLTK language names
        language_map = {
            "en": "english",
            "english": "english",
            "da": "danish",
            "danish": "danish",
        }

        nltk_language = language_map.get(language.lower(), "english")

        self.language = language
        self.max_phrase_length = max_phrase_length
        self.min_keyword_frequency = min_keyword_frequency

        # Initialize RAKE with configuration
        try:
            self.rake = Rake(
                language=nltk_language,
                max_length=max_phrase_length,
                min_length=1,
                include_repeated_phrases=False,
            )
            logger.debug(
                f"Initialized RAKE extractor: language={nltk_language}, "
                f"max_phrase_length={max_phrase_length}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize RAKE extractor: {e}")
            # Fall back to English if language not supported
            self.rake = Rake(
                language="english",
                max_length=max_phrase_length,
                min_length=1,
                include_repeated_phrases=False,
            )
            logger.warning(
                f"Falling back to English stopwords due to initialization error"
            )

    async def extract_keywords(
        self,
        text: str,
        max_keywords: int = 50,
        min_score: float = 0.0,
    ) -> List[RAKEKeyword]:
        """
        Extract keywords using RAKE algorithm.

        This method:
        1. Tokenizes text and identifies candidate phrases
        2. Calculates word degree and frequency
        3. Scores phrases using degree/frequency ratio
        4. Returns top-scoring phrases as keywords

        Args:
            text: The text to extract keywords from
            max_keywords: Maximum number of keywords to return
            min_score: Minimum score threshold for including a keyword

        Returns:
            List of RAKEKeyword objects sorted by score (descending)

        Example:
            >>> text = "Artificial intelligence and machine learning revolutionize data science."
            >>> keywords = await extractor.extract_keywords(text, max_keywords=3)
            >>> # Returns phrases like "artificial intelligence", "machine learning", etc.
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for RAKE extraction")
            return []

        # Run RAKE extraction in executor to avoid blocking
        loop = asyncio.get_event_loop()

        def _extract():
            """Internal function to run RAKE extraction."""
            try:
                # Extract keywords
                self.rake.extract_keywords_from_text(text)

                # Get ranked phrases with scores
                ranked_phrases = self.rake.get_ranked_phrases_with_scores()

                return ranked_phrases
            except Exception as e:
                logger.error(f"RAKE extraction failed: {e}")
                return []

        ranked_phrases = await loop.run_in_executor(None, _extract)

        if not ranked_phrases:
            logger.info("No keywords extracted by RAKE")
            return []

        # Convert to RAKEKeyword objects
        keywords = []
        for score, phrase in ranked_phrases:
            # Skip if below minimum score
            if score < min_score:
                continue

            # Count words in phrase
            word_count = len(phrase.split())

            # Skip if doesn't meet frequency requirement
            # (RAKE score includes frequency, so low scores = low frequency)
            if score < self.min_keyword_frequency:
                continue

            keywords.append(
                RAKEKeyword(
                    phrase=phrase.lower(),
                    score=score,
                    word_count=word_count,
                )
            )

            # Stop if we've reached max_keywords
            if len(keywords) >= max_keywords:
                break

        logger.info(
            f"Extracted {len(keywords)} keywords using RAKE "
            f"(from {len(ranked_phrases)} total phrases)"
        )

        return keywords

    async def extract_keywords_batch(
        self,
        texts: List[str],
        max_keywords: int = 50,
        min_score: float = 0.0,
    ) -> List[List[RAKEKeyword]]:
        """
        Extract keywords from multiple texts in batch.

        This processes each text independently using RAKE.

        Args:
            texts: List of texts to process
            max_keywords: Maximum keywords per text
            min_score: Minimum score threshold

        Returns:
            List of keyword lists, one per input text
        """
        if not texts:
            return []

        logger.info(f"Batch extracting RAKE keywords from {len(texts)} texts")

        # Process each text in parallel
        tasks = [
            self.extract_keywords(
                text=text, max_keywords=max_keywords, min_score=min_score
            )
            for text in texts
        ]

        results = await asyncio.gather(*tasks)

        logger.info(f"Completed batch RAKE extraction for {len(texts)} texts")

        return results
