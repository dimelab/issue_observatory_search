"""
TF-IDF (Term Frequency-Inverse Document Frequency) calculation.

Enhanced with bigram support and configurable IDF weighting.
Based on implementation from some2net (github.com/dimelab/some2net)
Adapted for Issue Observatory Search v6.0.0
"""
import asyncio
import logging
import math
from typing import Dict, List, Set
from collections import Counter

logger = logging.getLogger(__name__)


class TFIDFCalculator:
    """
    Calculate TF-IDF scores for terms in documents.

    TF-IDF is a numerical statistic that reflects how important a word is
    to a document in a collection (corpus) of documents.

    Enhanced Features (v6.0.0):
    - Bigram support for multi-word phrases
    - Configurable IDF weighting for tuning term vs. document importance
    - Backward compatible with original implementation

    Formulas:
    - TF (Term Frequency): frequency of term in document / total terms in document
    - IDF (Inverse Document Frequency): log(total documents / documents containing term)
    - TF-IDF: TF * (IDF ^ idf_weight)
    - IDF Weight: 0.0 (pure TF) to 2.0 (IDF-heavy)

    Example:
        >>> # Standard TF-IDF
        >>> calculator = TFIDFCalculator()
        >>> doc = ["hello", "world", "hello"]
        >>> corpus = [["hello", "world"], ["foo", "bar"], ["hello", "foo"]]
        >>> scores = await calculator.calculate_for_document(doc, corpus)
        >>> print(scores["hello"])

        >>> # With bigrams and IDF weighting
        >>> calculator = TFIDFCalculator(use_bigrams=True, idf_weight=1.5)
        >>> scores = await calculator.calculate_for_document(doc, corpus)
        >>> print(scores.get("hello world", 0.0))  # Bigram score
    """

    def __init__(
        self,
        use_bigrams: bool = False,
        idf_weight: float = 1.0,
    ):
        """
        Initialize TF-IDF calculator with enhanced options.

        Args:
            use_bigrams: Include bigrams (2-word phrases) in addition to unigrams.
                        When True, both single words and word pairs are scored.
            idf_weight: Weight for IDF component (0.0-2.0)
                       - 1.0 = standard TF-IDF (default)
                       - <1.0 = favor term frequency (local importance)
                       - >1.0 = favor document uniqueness (global distinctiveness)
                       - 0.0 = pure term frequency (no IDF)
        """
        self.use_bigrams = use_bigrams
        self.idf_weight = max(0.0, min(2.0, idf_weight))  # Clamp to [0.0, 2.0]

        logger.debug(
            f"Initialized TFIDFCalculator: use_bigrams={use_bigrams}, "
            f"idf_weight={self.idf_weight}"
        )

    def calculate_tf(self, term: str, document: List[str]) -> float:
        """
        Calculate term frequency (TF) for a term in a document.

        TF measures how frequently a term appears in a document.
        Higher values indicate the term is more important to the document.

        Args:
            term: The term to calculate TF for
            document: List of terms (tokens) in the document

        Returns:
            Term frequency score (0.0 to 1.0)
        """
        if not document:
            return 0.0

        term_count = document.count(term)
        return term_count / len(document)

    def calculate_idf(self, term: str, corpus: List[List[str]]) -> float:
        """
        Calculate inverse document frequency (IDF) for a term across corpus.

        IDF measures how rare/common a term is across all documents.
        Higher values indicate the term is more distinctive.

        Args:
            term: The term to calculate IDF for
            corpus: List of documents (each document is a list of terms)

        Returns:
            IDF score (higher = more distinctive)
        """
        if not corpus:
            return 0.0

        # Count documents containing the term
        docs_with_term = sum(1 for doc in corpus if term in doc)

        if docs_with_term == 0:
            return 0.0

        # Add 1 to avoid division by zero and smooth the results
        return math.log((len(corpus) + 1) / (docs_with_term + 1)) + 1

    def _extract_ngrams(
        self, tokens: List[str], n: int = 2
    ) -> List[str]:
        """
        Extract n-grams from token list.

        Args:
            tokens: List of tokens
            n: N-gram size (2 for bigrams, 3 for trigrams, etc.)

        Returns:
            List of n-gram strings (space-separated)

        Example:
            >>> tokens = ["machine", "learning", "is", "great"]
            >>> bigrams = self._extract_ngrams(tokens, n=2)
            >>> # Returns: ["machine learning", "learning is", "is great"]
        """
        if not tokens or n < 2:
            return []

        ngrams = []
        for i in range(len(tokens) - n + 1):
            ngram = " ".join(tokens[i : i + n])
            ngrams.append(ngram)

        return ngrams

    def calculate_tfidf(
        self, term: str, document: List[str], corpus: List[List[str]]
    ) -> float:
        """
        Calculate TF-IDF score for a term.

        Combines term frequency and inverse document frequency to create
        a score that reflects term importance.

        Args:
            term: The term to calculate TF-IDF for
            document: List of terms in the target document
            corpus: List of all documents (for IDF calculation)

        Returns:
            TF-IDF score (higher = more important)
        """
        tf = self.calculate_tf(term, document)
        idf = self.calculate_idf(term, corpus)
        return tf * idf

    def calculate_tfidf_weighted(
        self,
        term: str,
        document: List[str],
        corpus: List[List[str]],
    ) -> float:
        """
        Calculate TF-IDF with weighted IDF component.

        This allows tuning the balance between term frequency (local importance)
        and document frequency (global distinctiveness).

        Formula: TF * (IDF ^ idf_weight)

        Args:
            term: The term to calculate TF-IDF for
            document: List of terms in the target document
            corpus: List of all documents (for IDF calculation)

        Returns:
            Weighted TF-IDF score

        Example:
            >>> # Standard TF-IDF (idf_weight=1.0)
            >>> calc = TFIDFCalculator(idf_weight=1.0)
            >>> score = calc.calculate_tfidf_weighted("python", doc, corpus)

            >>> # Emphasize document uniqueness (idf_weight=1.5)
            >>> calc = TFIDFCalculator(idf_weight=1.5)
            >>> score = calc.calculate_tfidf_weighted("python", doc, corpus)
        """
        tf = self.calculate_tf(term, document)
        idf = self.calculate_idf(term, corpus)

        # Apply IDF weighting
        # idf_weight=0.0: pure TF (no IDF)
        # idf_weight=1.0: standard TF-IDF
        # idf_weight>1.0: emphasize rare terms
        weighted_idf = math.pow(idf, self.idf_weight) if idf > 0 else 0.0

        return tf * weighted_idf

    async def calculate_for_document(
        self, document: List[str], corpus: List[List[str]]
    ) -> Dict[str, float]:
        """
        Calculate TF-IDF scores for all unique terms in a document.

        Enhanced in v6.0.0 to support:
        - Bigrams (if use_bigrams=True)
        - Weighted IDF (if idf_weight != 1.0)

        This is more efficient than calling calculate_tfidf for each term
        individually, as it pre-calculates frequencies.

        Args:
            document: List of terms in the document
            corpus: List of all documents (including the target document)

        Returns:
            Dictionary mapping terms (unigrams and optionally bigrams) to their TF-IDF scores

        Example:
            >>> # Standard TF-IDF
            >>> calc = TFIDFCalculator()
            >>> doc = ["python", "is", "great", "python", "rocks"]
            >>> corpus = [doc, ["java", "is", "good"], ["python", "programming"]]
            >>> scores = await calc.calculate_for_document(doc, corpus)

            >>> # With bigrams
            >>> calc = TFIDFCalculator(use_bigrams=True)
            >>> scores = await calc.calculate_for_document(doc, corpus)
            >>> # Now includes scores for "python is", "is great", etc.
        """
        if not document or not corpus:
            return {}

        # Collect all terms (unigrams and optionally bigrams)
        all_terms = document.copy()
        doc_length = len(document)

        if self.use_bigrams:
            bigrams = self._extract_ngrams(document, n=2)
            all_terms.extend(bigrams)
            logger.debug(
                f"Extracted {len(bigrams)} bigrams from document of {doc_length} tokens"
            )

        # Calculate term frequencies
        term_counts = Counter(all_terms)

        # Pre-calculate IDF for all unique terms
        idf_cache: Dict[str, float] = {}

        # Run IDF calculations in parallel for better performance
        async def calc_idf(term: str) -> tuple[str, float]:
            """Calculate IDF for a single term."""
            loop = asyncio.get_event_loop()

            # For bigrams, need to count in corpus differently
            if " " in term:
                # Bigram: check in corpus
                def count_bigram_idf():
                    docs_with_term = 0
                    for corp_doc in corpus:
                        corp_bigrams = self._extract_ngrams(corp_doc, n=2)
                        if term in corp_bigrams:
                            docs_with_term += 1

                    if docs_with_term == 0:
                        return 0.0
                    return math.log((len(corpus) + 1) / (docs_with_term + 1)) + 1

                idf = await loop.run_in_executor(None, count_bigram_idf)
            else:
                # Unigram: use standard IDF
                idf = await loop.run_in_executor(
                    None, self.calculate_idf, term, corpus
                )

            return term, idf

        # Calculate IDF for all unique terms
        tasks = [calc_idf(term) for term in term_counts.keys()]
        idf_results = await asyncio.gather(*tasks)
        idf_cache = dict(idf_results)

        # Calculate TF-IDF for each term with weighted IDF
        tfidf_scores: Dict[str, float] = {}

        # Adjust document length for bigrams
        effective_doc_length = len(all_terms)

        for term, count in term_counts.items():
            tf = count / effective_doc_length
            idf = idf_cache.get(term, 0.0)

            # Apply IDF weighting
            if self.idf_weight != 1.0:
                weighted_idf = math.pow(idf, self.idf_weight) if idf > 0 else 0.0
                tfidf_scores[term] = tf * weighted_idf
            else:
                tfidf_scores[term] = tf * idf

        unigram_count = len([t for t in tfidf_scores if ' ' not in t])
        bigram_count = len([t for t in tfidf_scores if ' ' in t])
        bigram_text = f', {bigram_count} bigrams' if self.use_bigrams else ''
        logger.debug(
            f"Calculated TF-IDF for {len(tfidf_scores)} unique terms "
            f"({unigram_count} unigrams{bigram_text})"
        )

        return tfidf_scores

    async def calculate_for_corpus(
        self, corpus: List[List[str]]
    ) -> List[Dict[str, float]]:
        """
        Calculate TF-IDF scores for all documents in a corpus.

        This is optimized for batch processing multiple documents.

        Args:
            corpus: List of documents (each document is a list of terms)

        Returns:
            List of TF-IDF score dictionaries, one per document

        Example:
            >>> corpus = [
            ...     ["python", "programming"],
            ...     ["java", "programming"],
            ...     ["python", "java"]
            ... ]
            >>> scores = await calculator.calculate_for_corpus(corpus)
            >>> print(scores[0]["python"])  # TF-IDF for "python" in first doc
        """
        if not corpus:
            return []

        # Calculate TF-IDF for each document in parallel
        tasks = [
            self.calculate_for_document(doc, corpus)
            for doc in corpus
        ]

        results = await asyncio.gather(*tasks)

        logger.info(f"Calculated TF-IDF for {len(corpus)} documents in corpus")

        return results

    def get_top_terms(
        self, tfidf_scores: Dict[str, float], top_n: int = 10
    ) -> List[tuple[str, float]]:
        """
        Get the top N terms by TF-IDF score.

        Args:
            tfidf_scores: Dictionary of term -> TF-IDF score
            top_n: Number of top terms to return

        Returns:
            List of (term, score) tuples sorted by score (descending)
        """
        sorted_terms = sorted(
            tfidf_scores.items(), key=lambda x: x[1], reverse=True
        )
        return sorted_terms[:top_n]
