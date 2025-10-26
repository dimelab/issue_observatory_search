"""TF-IDF (Term Frequency-Inverse Document Frequency) calculation."""
import asyncio
import logging
import math
from typing import Dict, List
from collections import Counter

logger = logging.getLogger(__name__)


class TFIDFCalculator:
    """
    Calculate TF-IDF scores for terms in documents.

    TF-IDF is a numerical statistic that reflects how important a word is
    to a document in a collection (corpus) of documents.

    Formulas:
    - TF (Term Frequency): frequency of term in document / total terms in document
    - IDF (Inverse Document Frequency): log(total documents / documents containing term)
    - TF-IDF: TF * IDF

    Example:
        >>> calculator = TFIDFCalculator()
        >>> doc = ["hello", "world", "hello"]
        >>> corpus = [["hello", "world"], ["foo", "bar"], ["hello", "foo"]]
        >>> scores = await calculator.calculate_for_document(doc, corpus)
        >>> print(scores["hello"])
    """

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

    async def calculate_for_document(
        self, document: List[str], corpus: List[List[str]]
    ) -> Dict[str, float]:
        """
        Calculate TF-IDF scores for all unique terms in a document.

        This is more efficient than calling calculate_tfidf for each term
        individually, as it pre-calculates frequencies.

        Args:
            document: List of terms in the document
            corpus: List of all documents (including the target document)

        Returns:
            Dictionary mapping terms to their TF-IDF scores

        Example:
            >>> doc = ["python", "is", "great", "python", "rocks"]
            >>> corpus = [doc, ["java", "is", "good"], ["python", "programming"]]
            >>> scores = await calculator.calculate_for_document(doc, corpus)
        """
        if not document or not corpus:
            return {}

        # Calculate term frequencies for the document
        term_counts = Counter(document)
        doc_length = len(document)

        # Pre-calculate IDF for all unique terms
        idf_cache: Dict[str, float] = {}

        # Run IDF calculations in parallel for better performance
        async def calc_idf(term: str) -> tuple[str, float]:
            """Calculate IDF for a single term."""
            loop = asyncio.get_event_loop()
            idf = await loop.run_in_executor(
                None, self.calculate_idf, term, corpus
            )
            return term, idf

        # Calculate IDF for all unique terms
        tasks = [calc_idf(term) for term in term_counts.keys()]
        idf_results = await asyncio.gather(*tasks)
        idf_cache = dict(idf_results)

        # Calculate TF-IDF for each term
        tfidf_scores: Dict[str, float] = {}
        for term, count in term_counts.items():
            tf = count / doc_length
            idf = idf_cache.get(term, 0.0)
            tfidf_scores[term] = tf * idf

        logger.debug(
            f"Calculated TF-IDF for {len(tfidf_scores)} unique terms "
            f"in document of length {doc_length}"
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
