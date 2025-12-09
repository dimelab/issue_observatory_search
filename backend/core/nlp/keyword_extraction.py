"""
Unified keyword extraction interface.

Supports multiple extraction methods:
- noun: Original spaCy noun extraction (backward compatible)
- all_pos: Extract nouns, verbs, adjectives (spaCy)
- tfidf: TF-IDF with bigrams and IDF weighting
- rake: RAKE algorithm with n-grams

Based on implementation from some2net (github.com/dimelab/some2net)
Adapted for Issue Observatory Search v6.0.0
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import List, Literal, Optional, Dict
from collections import Counter

from backend.core.nlp.models import nlp_model_manager
from backend.core.nlp.tfidf import TFIDFCalculator
from backend.core.nlp.rake_extraction import RAKEExtractor
from backend.config import settings

logger = logging.getLogger(__name__)

# Type alias for keyword extraction methods
KeywordMethod = Literal["noun", "all_pos", "tfidf", "rake"]


@dataclass
class KeywordConfig:
    """Configuration for keyword extraction."""

    method: KeywordMethod = "noun"
    max_keywords: int = 50
    min_frequency: int = 2

    # TF-IDF specific
    use_bigrams: bool = False
    idf_weight: float = 1.0  # 0.0 (pure TF) to 2.0 (IDF-heavy)

    # RAKE specific
    max_phrase_length: int = 3  # n-gram size for RAKE

    # POS filter specific (for "all_pos" method)
    include_pos: List[str] = field(
        default_factory=lambda: ["NOUN"]
    )  # For "all_pos", can include: NOUN, VERB, ADJ


@dataclass
class ExtractedKeyword:
    """
    Represents a keyword extracted from text.

    This is a unified data structure that works with all extraction methods.

    Attributes:
        word: The original word or phrase
        lemma: The lemmatized (base) form
        frequency: Number of times it appears
        score: Importance score (TF-IDF, RAKE, or frequency-based)
        word_count: Number of words in the keyword (1 for unigrams, 2+ for phrases)
        pos_tag: Part of speech tag (NOUN, VERB, ADJ, etc.) - optional
        positions: Character positions in text - optional
    """

    word: str
    lemma: str
    frequency: int
    score: float
    word_count: int = 1
    pos_tag: Optional[str] = None
    positions: List[int] = field(default_factory=list)

    def __repr__(self) -> str:
        """String representation of ExtractedKeyword."""
        return (
            f"ExtractedKeyword(word='{self.word}', lemma='{self.lemma}', "
            f"freq={self.frequency}, score={self.score:.4f}, "
            f"words={self.word_count})"
        )


class UniversalKeywordExtractor:
    """
    Unified interface for all keyword extraction methods.

    Supports:
    - noun: Original spaCy noun extraction (backward compatible with v5.0.0)
    - all_pos: Extract nouns, verbs, adjectives (spaCy-based)
    - tfidf: TF-IDF with optional bigrams and IDF weighting
    - rake: RAKE algorithm with configurable n-grams

    Example:
        >>> # Noun-only extraction (backward compatible)
        >>> extractor = UniversalKeywordExtractor()
        >>> config = KeywordConfig(method="noun", max_keywords=20)
        >>> keywords = await extractor.extract_keywords(
        ...     text="Python programming is great for data science.",
        ...     language="en",
        ...     config=config
        ... )

        >>> # RAKE extraction with 3-word phrases
        >>> config = KeywordConfig(
        ...     method="rake",
        ...     max_phrase_length=3,
        ...     max_keywords=15
        ... )
        >>> keywords = await extractor.extract_keywords(text, "en", config)

        >>> # TF-IDF with bigrams
        >>> config = KeywordConfig(
        ...     method="tfidf",
        ...     use_bigrams=True,
        ...     idf_weight=1.2
        ... )
        >>> keywords = await extractor.extract_keywords(text, "en", config)
    """

    def __init__(self):
        """Initialize the universal keyword extractor."""
        self.tfidf_calculator = None
        self.rake_extractor = None

    async def extract_keywords(
        self,
        text: str,
        language: str,
        config: KeywordConfig,
        corpus: Optional[List[str]] = None,
    ) -> List[ExtractedKeyword]:
        """
        Extract keywords based on configuration.

        This is the main entry point for keyword extraction.
        It dispatches to the appropriate extraction method based on config.method.

        Args:
            text: The text to extract keywords from
            language: ISO 639-1 language code (e.g., "en", "da")
            config: KeywordConfig specifying extraction method and parameters
            corpus: Optional list of other documents for TF-IDF calculation

        Returns:
            List of ExtractedKeyword objects sorted by score (descending)

        Raises:
            ValueError: If method is not supported or text is empty
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for keyword extraction")
            return []

        # Truncate text if too long
        if len(text) > settings.nlp_max_text_length:
            logger.warning(
                f"Text length {len(text)} exceeds maximum "
                f"{settings.nlp_max_text_length}, truncating"
            )
            text = text[: settings.nlp_max_text_length]

        logger.debug(
            f"Extracting keywords using method '{config.method}' "
            f"(language: {language}, max_keywords: {config.max_keywords})"
        )

        # Dispatch to appropriate extraction method
        if config.method == "noun":
            return await self._extract_nouns(text, language, config, corpus)
        elif config.method == "all_pos":
            return await self._extract_all_pos(text, language, config, corpus)
        elif config.method == "tfidf":
            return await self._extract_tfidf(text, language, config, corpus)
        elif config.method == "rake":
            return await self._extract_rake(text, language, config)
        else:
            raise ValueError(f"Unsupported extraction method: {config.method}")

    async def _extract_nouns(
        self,
        text: str,
        language: str,
        config: KeywordConfig,
        corpus: Optional[List[str]] = None,
    ) -> List[ExtractedKeyword]:
        """
        Extract nouns using spaCy (original method, backward compatible).

        This method:
        1. Uses spaCy to identify nouns
        2. Filters stop words
        3. Lemmatizes tokens
        4. Calculates TF-IDF scores
        5. Returns top N by score
        """
        nlp = await nlp_model_manager.get_model(language)

        # Process text
        loop = asyncio.get_event_loop()
        doc = await loop.run_in_executor(None, nlp, text)

        # Extract nouns with metadata
        noun_data: Dict[str, Dict] = {}

        for token in doc:
            # Filter for nouns only
            if token.pos_ != "NOUN" or token.is_stop or token.is_punct:
                continue

            # Skip very short tokens
            if len(token.text) < 2:
                continue

            lemma = token.lemma_.lower()
            word = token.text.lower()

            if lemma not in noun_data:
                noun_data[lemma] = {
                    "word": word,
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
            if data["frequency"] >= config.min_frequency
        }

        if not noun_data:
            logger.info("No nouns found after filtering")
            return []

        # Calculate TF-IDF scores
        document_lemmas = [
            token.lemma_.lower()
            for token in doc
            if token.pos_ == "NOUN" and not token.is_stop and not token.is_punct
        ]

        # Create corpus for TF-IDF
        if corpus:
            corpus_docs = []
            for corpus_text in corpus:
                corpus_doc = await loop.run_in_executor(None, nlp, corpus_text)
                corpus_lemmas = [
                    token.lemma_.lower()
                    for token in corpus_doc
                    if token.pos_ == "NOUN" and not token.is_stop and not token.is_punct
                ]
                corpus_docs.append(corpus_lemmas)
            corpus_docs.append(document_lemmas)
        else:
            corpus_docs = [document_lemmas]

        # Calculate TF-IDF
        if not self.tfidf_calculator:
            self.tfidf_calculator = TFIDFCalculator()

        tfidf_scores = await self.tfidf_calculator.calculate_for_document(
            document_lemmas, corpus_docs
        )

        # Create ExtractedKeyword objects
        keywords = []
        for lemma, data in noun_data.items():
            tfidf_score = tfidf_scores.get(lemma, 0.0)
            word_counter = Counter(data["tokens"])
            most_common_word = word_counter.most_common(1)[0][0]

            keywords.append(
                ExtractedKeyword(
                    word=most_common_word,
                    lemma=lemma,
                    frequency=data["frequency"],
                    score=tfidf_score,
                    word_count=1,
                    pos_tag="NOUN",
                    positions=data["positions"][:100],
                )
            )

        # Sort by score and return top N
        keywords.sort(key=lambda x: x.score, reverse=True)
        return keywords[: config.max_keywords]

    async def _extract_all_pos(
        self,
        text: str,
        language: str,
        config: KeywordConfig,
        corpus: Optional[List[str]] = None,
    ) -> List[ExtractedKeyword]:
        """
        Extract keywords from multiple POS tags (nouns, verbs, adjectives).

        Similar to _extract_nouns but includes configurable POS tags.
        """
        nlp = await nlp_model_manager.get_model(language)

        # Process text
        loop = asyncio.get_event_loop()
        doc = await loop.run_in_executor(None, nlp, text)

        # Get allowed POS tags
        allowed_pos = set(config.include_pos)

        # Extract tokens with metadata
        token_data: Dict[str, Dict] = {}

        for token in doc:
            # Filter by POS tags
            if token.pos_ not in allowed_pos or token.is_stop or token.is_punct:
                continue

            # Skip very short tokens
            if len(token.text) < 2:
                continue

            lemma = token.lemma_.lower()
            word = token.text.lower()

            if lemma not in token_data:
                token_data[lemma] = {
                    "word": word,
                    "lemma": lemma,
                    "frequency": 0,
                    "positions": [],
                    "tokens": [],
                    "pos_tag": token.pos_,
                }

            token_data[lemma]["frequency"] += 1
            token_data[lemma]["positions"].append(token.idx)
            token_data[lemma]["tokens"].append(word)

        # Filter by minimum frequency
        token_data = {
            lemma: data
            for lemma, data in token_data.items()
            if data["frequency"] >= config.min_frequency
        }

        if not token_data:
            logger.info(f"No tokens found for POS tags: {allowed_pos}")
            return []

        # Calculate TF-IDF scores
        document_lemmas = [
            token.lemma_.lower()
            for token in doc
            if token.pos_ in allowed_pos and not token.is_stop and not token.is_punct
        ]

        # Create corpus
        if corpus:
            corpus_docs = []
            for corpus_text in corpus:
                corpus_doc = await loop.run_in_executor(None, nlp, corpus_text)
                corpus_lemmas = [
                    token.lemma_.lower()
                    for token in corpus_doc
                    if token.pos_ in allowed_pos
                    and not token.is_stop
                    and not token.is_punct
                ]
                corpus_docs.append(corpus_lemmas)
            corpus_docs.append(document_lemmas)
        else:
            corpus_docs = [document_lemmas]

        # Calculate TF-IDF
        if not self.tfidf_calculator:
            self.tfidf_calculator = TFIDFCalculator()

        tfidf_scores = await self.tfidf_calculator.calculate_for_document(
            document_lemmas, corpus_docs
        )

        # Create ExtractedKeyword objects
        keywords = []
        for lemma, data in token_data.items():
            tfidf_score = tfidf_scores.get(lemma, 0.0)
            word_counter = Counter(data["tokens"])
            most_common_word = word_counter.most_common(1)[0][0]

            keywords.append(
                ExtractedKeyword(
                    word=most_common_word,
                    lemma=lemma,
                    frequency=data["frequency"],
                    score=tfidf_score,
                    word_count=1,
                    pos_tag=data["pos_tag"],
                    positions=data["positions"][:100],
                )
            )

        # Sort by score and return top N
        keywords.sort(key=lambda x: x.score, reverse=True)
        return keywords[: config.max_keywords]

    async def _extract_tfidf(
        self,
        text: str,
        language: str,
        config: KeywordConfig,
        corpus: Optional[List[str]] = None,
    ) -> List[ExtractedKeyword]:
        """
        Extract keywords using TF-IDF with optional bigrams and IDF weighting.

        This method focuses on statistical importance rather than linguistic structure.
        """
        nlp = await nlp_model_manager.get_model(language)

        # Process text
        loop = asyncio.get_event_loop()
        doc = await loop.run_in_executor(None, nlp, text)

        # Extract lemmas (excluding stop words and punctuation)
        document_lemmas = [
            token.lemma_.lower()
            for token in doc
            if not token.is_stop and not token.is_punct and len(token.text) >= 2
        ]

        if not document_lemmas:
            logger.info("No valid tokens for TF-IDF extraction")
            return []

        # Initialize TF-IDF calculator with configuration
        self.tfidf_calculator = TFIDFCalculator(
            use_bigrams=config.use_bigrams, idf_weight=config.idf_weight
        )

        # Create corpus
        if corpus:
            corpus_docs = []
            for corpus_text in corpus:
                corpus_doc = await loop.run_in_executor(None, nlp, corpus_text)
                corpus_lemmas = [
                    token.lemma_.lower()
                    for token in corpus_doc
                    if not token.is_stop
                    and not token.is_punct
                    and len(token.text) >= 2
                ]
                corpus_docs.append(corpus_lemmas)
            corpus_docs.append(document_lemmas)
        else:
            corpus_docs = [document_lemmas]

        # Calculate TF-IDF scores
        tfidf_scores = await self.tfidf_calculator.calculate_for_document(
            document_lemmas, corpus_docs
        )

        # Convert to ExtractedKeyword objects
        # Count frequencies
        lemma_counts = Counter(document_lemmas)

        keywords = []
        for term, score in tfidf_scores.items():
            word_count = len(term.split())  # 1 for unigrams, 2 for bigrams

            # Get frequency
            if word_count == 1:
                frequency = lemma_counts.get(term, 1)
            else:
                # For bigrams, count occurrences
                frequency = 1  # Approximate for bigrams

            keywords.append(
                ExtractedKeyword(
                    word=term,
                    lemma=term,
                    frequency=frequency,
                    score=score,
                    word_count=word_count,
                    pos_tag=None,
                    positions=[],
                )
            )

        # Sort by score and return top N
        keywords.sort(key=lambda x: x.score, reverse=True)
        return keywords[: config.max_keywords]

    async def _extract_rake(
        self,
        text: str,
        language: str,
        config: KeywordConfig,
    ) -> List[ExtractedKeyword]:
        """
        Extract keywords using RAKE algorithm.

        RAKE identifies key phrases (multi-word keywords) based on word co-occurrence patterns.
        """
        # Initialize RAKE extractor
        self.rake_extractor = RAKEExtractor(
            language=language,
            max_phrase_length=config.max_phrase_length,
            min_keyword_frequency=config.min_frequency,
        )

        # Extract RAKE keywords
        rake_keywords = await self.rake_extractor.extract_keywords(
            text=text, max_keywords=config.max_keywords, min_score=0.0
        )

        # Convert to ExtractedKeyword format
        keywords = []
        for rake_kw in rake_keywords:
            keywords.append(
                ExtractedKeyword(
                    word=rake_kw.phrase,
                    lemma=rake_kw.phrase,  # RAKE doesn't lemmatize
                    frequency=1,  # RAKE doesn't track frequency directly
                    score=rake_kw.score,
                    word_count=rake_kw.word_count,
                    pos_tag=None,
                    positions=[],
                )
            )

        return keywords

    async def extract_keywords_batch(
        self,
        texts: List[str],
        language: str,
        config: KeywordConfig,
    ) -> List[List[ExtractedKeyword]]:
        """
        Extract keywords from multiple texts in batch.

        This is more efficient than calling extract_keywords multiple times
        as it uses the texts as a corpus for TF-IDF calculation.

        Args:
            texts: List of texts to process
            language: ISO 639-1 language code
            config: KeywordConfig specifying extraction method and parameters

        Returns:
            List of keyword lists, one per input text
        """
        if not texts:
            return []

        logger.info(
            f"Batch extracting keywords from {len(texts)} texts "
            f"using method '{config.method}'"
        )

        # For TF-IDF-based methods, use texts as corpus
        if config.method in ["noun", "all_pos", "tfidf"]:
            tasks = [
                self.extract_keywords(
                    text=text,
                    language=language,
                    config=config,
                    corpus=[t for t in texts if t != text],
                )
                for text in texts
            ]
        else:
            # RAKE doesn't use corpus
            tasks = [
                self.extract_keywords(text=text, language=language, config=config)
                for text in texts
            ]

        results = await asyncio.gather(*tasks)

        logger.info(f"Completed batch keyword extraction for {len(texts)} texts")

        return results
