"""Noun extraction from text using spaCy with TF-IDF scoring."""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from collections import Counter

from backend.core.nlp.models import nlp_model_manager
from backend.core.nlp.tfidf import TFIDFCalculator
from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ExtractedNoun:
    """
    Represents a noun extracted from text with metadata.

    Attributes:
        word: The original word form
        lemma: The lemmatized (base) form of the word
        frequency: Number of times the word appears in the text
        tfidf_score: TF-IDF importance score
        positions: Character positions where the word appears
    """

    word: str
    lemma: str
    frequency: int
    tfidf_score: float
    positions: List[int] = field(default_factory=list)

    def __repr__(self) -> str:
        """String representation of ExtractedNoun."""
        return (
            f"ExtractedNoun(word='{self.word}', lemma='{self.lemma}', "
            f"freq={self.frequency}, tfidf={self.tfidf_score:.4f})"
        )


class NounExtractor:
    """
    Extract and rank nouns from text using spaCy NLP and TF-IDF scoring.

    This class identifies nouns in text, filters out stop words, and ranks
    them by importance using TF-IDF scores. It supports lemmatization to
    group different forms of the same word.

    Example:
        >>> extractor = NounExtractor()
        >>> text = "Python programming is great. Python developers love Python."
        >>> nouns = await extractor.extract_nouns(text, language="en", max_nouns=10)
        >>> for noun in nouns:
        ...     print(f"{noun.lemma}: {noun.tfidf_score:.4f}")
    """

    def __init__(self):
        """Initialize the noun extractor."""
        self.tfidf_calculator = TFIDFCalculator()

    async def extract_nouns(
        self,
        text: str,
        language: str = "en",
        max_nouns: int = 100,
        min_frequency: int = 2,
        corpus: Optional[List[str]] = None,
    ) -> List[ExtractedNoun]:
        """
        Extract nouns from text with TF-IDF ranking.

        This method:
        1. Tokenizes and POS-tags the text using spaCy
        2. Filters for nouns (excluding proper nouns optionally)
        3. Removes stop words
        4. Lemmatizes words to their base form
        5. Calculates TF-IDF scores
        6. Returns top N nouns by score

        Args:
            text: The text to extract nouns from
            language: ISO 639-1 language code (e.g., "en", "da")
            max_nouns: Maximum number of nouns to return
            min_frequency: Minimum frequency for a noun to be included
            corpus: Optional list of other documents for TF-IDF calculation.
                   If None, only TF (term frequency) is used.

        Returns:
            List of ExtractedNoun objects sorted by TF-IDF score (descending)

        Raises:
            ValueError: If text is empty or language is unsupported
            RuntimeError: If spaCy model is not installed
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for noun extraction")
            return []

        # Check text length and truncate if necessary
        if len(text) > settings.nlp_max_text_length:
            logger.warning(
                f"Text length {len(text)} exceeds maximum "
                f"{settings.nlp_max_text_length}, truncating"
            )
            text = text[: settings.nlp_max_text_length]

        logger.debug(
            f"Extracting nouns from text (length: {len(text)}, language: {language})"
        )

        # Get spaCy model
        nlp = await nlp_model_manager.get_model(language)

        # Process text in executor to avoid blocking
        loop = asyncio.get_event_loop()
        doc = await loop.run_in_executor(None, nlp, text)

        # Extract nouns with their metadata
        noun_data: Dict[str, Dict] = {}

        for token in doc:
            # Filter for nouns (NOUN) and exclude stop words
            if token.pos_ != "NOUN" or token.is_stop or token.is_punct:
                continue

            # Skip very short tokens (likely not meaningful)
            if len(token.text) < 2:
                continue

            # Use lemma as the key to group different forms
            lemma = token.lemma_.lower()
            word = token.text.lower()

            if lemma not in noun_data:
                noun_data[lemma] = {
                    "word": word,  # Store the first occurrence
                    "lemma": lemma,
                    "frequency": 0,
                    "positions": [],
                    "tokens": [],
                }

            noun_data[lemma]["frequency"] += 1
            noun_data[lemma]["positions"].append(token.idx)
            noun_data[lemma]["tokens"].append(word)

        # Filter by minimum frequency
        noun_data = {
            lemma: data
            for lemma, data in noun_data.items()
            if data["frequency"] >= min_frequency
        }

        if not noun_data:
            logger.info("No nouns found after filtering")
            return []

        logger.debug(
            f"Found {len(noun_data)} unique nouns (after frequency filter: {min_frequency})"
        )

        # Calculate TF-IDF scores
        # Create document as list of lemmas
        document_lemmas = [
            token.lemma_.lower()
            for token in doc
            if token.pos_ == "NOUN" and not token.is_stop and not token.is_punct
        ]

        # Create corpus for TF-IDF
        if corpus:
            # Process corpus documents
            corpus_docs = []
            for corpus_text in corpus:
                corpus_doc = await loop.run_in_executor(None, nlp, corpus_text)
                corpus_lemmas = [
                    token.lemma_.lower()
                    for token in corpus_doc
                    if token.pos_ == "NOUN"
                    and not token.is_stop
                    and not token.is_punct
                ]
                corpus_docs.append(corpus_lemmas)

            # Add current document to corpus
            corpus_docs.append(document_lemmas)
        else:
            # Use only the current document
            corpus_docs = [document_lemmas]

        # Calculate TF-IDF scores
        tfidf_scores = await self.tfidf_calculator.calculate_for_document(
            document_lemmas, corpus_docs
        )

        # Create ExtractedNoun objects
        extracted_nouns = []
        for lemma, data in noun_data.items():
            tfidf_score = tfidf_scores.get(lemma, 0.0)

            # Use the most common word form for this lemma
            word_counter = Counter(data["tokens"])
            most_common_word = word_counter.most_common(1)[0][0]

            extracted_nouns.append(
                ExtractedNoun(
                    word=most_common_word,
                    lemma=lemma,
                    frequency=data["frequency"],
                    tfidf_score=tfidf_score,
                    positions=data["positions"][:100],  # Limit positions to 100
                )
            )

        # Sort by TF-IDF score (descending)
        extracted_nouns.sort(key=lambda x: x.tfidf_score, reverse=True)

        # Return top N nouns
        result = extracted_nouns[:max_nouns]

        logger.info(
            f"Extracted {len(result)} nouns (top {max_nouns} by TF-IDF) "
            f"from text of {len(text)} characters"
        )

        return result

    async def extract_nouns_batch(
        self,
        texts: List[str],
        language: str = "en",
        max_nouns: int = 100,
        min_frequency: int = 2,
    ) -> List[List[ExtractedNoun]]:
        """
        Extract nouns from multiple texts in batch.

        This is more efficient than calling extract_nouns multiple times
        as it uses the texts as a corpus for TF-IDF calculation.

        Args:
            texts: List of texts to process
            language: ISO 639-1 language code
            max_nouns: Maximum nouns per document
            min_frequency: Minimum frequency per document

        Returns:
            List of noun lists, one per input text
        """
        if not texts:
            return []

        logger.info(f"Batch extracting nouns from {len(texts)} texts")

        # Process each text with the full corpus for TF-IDF
        tasks = [
            self.extract_nouns(
                text=text,
                language=language,
                max_nouns=max_nouns,
                min_frequency=min_frequency,
                corpus=[t for t in texts if t != text],  # Other texts as corpus
            )
            for text in texts
        ]

        results = await asyncio.gather(*tasks)

        logger.info(f"Completed batch noun extraction for {len(texts)} texts")

        return results
