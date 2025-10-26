"""Query expansion module for snowballing searches."""
import re
import logging
from collections import Counter, defaultdict
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from urllib.parse import urlparse

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ExpansionCandidate:
    """
    Represents a query expansion candidate.

    Attributes:
        term: The candidate term
        score: Overall score for the candidate
        sources: List of sources where this term appeared
        frequencies: Frequency in each source
        metadata: Additional metadata (TF-IDF scores, positions, etc.)
    """

    term: str
    score: float
    sources: List[str]
    frequencies: Dict[str, int]
    metadata: Dict


class QueryExpander:
    """
    Query expansion engine using multiple sources.

    Implements snowballing methodology by extracting related terms from:
    1. Search result metadata (titles, descriptions, URLs)
    2. Scraped content (high TF-IDF nouns, entities)
    3. Search engine suggestions
    4. Meta keywords and page structure

    Methods score and rank candidates to help users iteratively
    expand their search queries.
    """

    def __init__(
        self,
        min_frequency: int = 2,
        max_candidates: int = 100,
        similarity_threshold: float = 0.1,
    ):
        """
        Initialize query expander.

        Args:
            min_frequency: Minimum frequency for a term to be considered
            max_candidates: Maximum number of candidates to return
            similarity_threshold: Minimum cosine similarity to seed query
        """
        self.min_frequency = min_frequency
        self.max_candidates = max_candidates
        self.similarity_threshold = similarity_threshold

    def expand_from_search_results(
        self,
        results: List[Dict],
        seed_query: str,
    ) -> List[ExpansionCandidate]:
        """
        Extract expansion candidates from search results metadata.

        Analyzes titles, descriptions, and URLs to find relevant terms.

        Args:
            results: List of search result dicts with 'title', 'description', 'url'
            seed_query: Original query for similarity scoring

        Returns:
            List of ExpansionCandidate objects
        """
        logger.info(f"Expanding from {len(results)} search results")

        # Extract text from results
        title_terms = []
        description_terms = []
        url_terms = []

        for result in results:
            if result.get("title"):
                title_terms.extend(self._extract_meaningful_terms(result["title"]))
            if result.get("description"):
                description_terms.extend(self._extract_meaningful_terms(result["description"]))
            if result.get("url"):
                url_terms.extend(self._extract_url_terms(result["url"]))

        # Count frequencies by source
        candidates_map: Dict[str, Dict] = {}

        # Process titles (highest weight)
        for term in title_terms:
            if term not in candidates_map:
                candidates_map[term] = {
                    "term": term,
                    "sources": set(),
                    "frequencies": defaultdict(int),
                }
            candidates_map[term]["sources"].add("title")
            candidates_map[term]["frequencies"]["title"] += 1

        # Process descriptions
        for term in description_terms:
            if term not in candidates_map:
                candidates_map[term] = {
                    "term": term,
                    "sources": set(),
                    "frequencies": defaultdict(int),
                }
            candidates_map[term]["sources"].add("description")
            candidates_map[term]["frequencies"]["description"] += 1

        # Process URLs
        for term in url_terms:
            if term not in candidates_map:
                candidates_map[term] = {
                    "term": term,
                    "sources": set(),
                    "frequencies": defaultdict(int),
                }
            candidates_map[term]["sources"].add("url")
            candidates_map[term]["frequencies"]["url"] += 1

        # Create candidates
        candidates = []
        for term_data in candidates_map.values():
            total_freq = sum(term_data["frequencies"].values())
            if total_freq >= self.min_frequency:
                candidate = ExpansionCandidate(
                    term=term_data["term"],
                    score=0.0,  # Will be scored later
                    sources=list(term_data["sources"]),
                    frequencies=dict(term_data["frequencies"]),
                    metadata={},
                )
                candidates.append(candidate)

        # Score candidates
        candidates = self.score_candidates(candidates, seed_query, title_terms + description_terms)

        logger.info(f"Found {len(candidates)} candidates from search results")
        return candidates[:self.max_candidates]

    def expand_from_content(
        self,
        nouns: List[Dict],
        entities: List[Dict],
        seed_query: str,
        top_n: int = 50,
    ) -> List[ExpansionCandidate]:
        """
        Extract expansion candidates from analyzed content.

        Uses high TF-IDF nouns and named entities from scraped pages.

        Args:
            nouns: List of noun dicts with 'word', 'lemma', 'tfidf_score', 'frequency'
            entities: List of entity dicts with 'text', 'label', 'confidence'
            seed_query: Original query for similarity scoring
            top_n: Number of top terms to consider

        Returns:
            List of ExpansionCandidate objects
        """
        logger.info(f"Expanding from {len(nouns)} nouns and {len(entities)} entities")

        candidates_map: Dict[str, Dict] = {}

        # Process nouns (sorted by TF-IDF)
        sorted_nouns = sorted(nouns, key=lambda x: x.get("tfidf_score", 0), reverse=True)[:top_n]

        for noun in sorted_nouns:
            term = noun.get("lemma", noun.get("word", "")).lower()
            if not term or len(term) < 3:
                continue

            if term not in candidates_map:
                candidates_map[term] = {
                    "term": term,
                    "sources": set(),
                    "frequencies": defaultdict(int),
                    "metadata": {},
                }

            candidates_map[term]["sources"].add("content_noun")
            candidates_map[term]["frequencies"]["content_noun"] = noun.get("frequency", 1)
            candidates_map[term]["metadata"]["tfidf_score"] = noun.get("tfidf_score", 0.0)

        # Process entities
        entity_counter = Counter([e.get("text", "").lower() for e in entities if e.get("text")])

        for entity_text, freq in entity_counter.most_common(top_n):
            if not entity_text or len(entity_text) < 3:
                continue

            if entity_text not in candidates_map:
                candidates_map[entity_text] = {
                    "term": entity_text,
                    "sources": set(),
                    "frequencies": defaultdict(int),
                    "metadata": {},
                }

            candidates_map[entity_text]["sources"].add("content_entity")
            candidates_map[entity_text]["frequencies"]["content_entity"] = freq

            # Add entity label metadata
            entity_labels = [e.get("label") for e in entities if e.get("text", "").lower() == entity_text]
            if entity_labels:
                candidates_map[entity_text]["metadata"]["entity_labels"] = list(set(entity_labels))

        # Create candidates
        candidates = []
        for term_data in candidates_map.values():
            candidate = ExpansionCandidate(
                term=term_data["term"],
                score=0.0,
                sources=list(term_data["sources"]),
                frequencies=dict(term_data["frequencies"]),
                metadata=term_data.get("metadata", {}),
            )
            candidates.append(candidate)

        # Score candidates
        all_text = [n.get("word", "") for n in sorted_nouns] + [e.get("text", "") for e in entities]
        candidates = self.score_candidates(candidates, seed_query, all_text)

        logger.info(f"Found {len(candidates)} candidates from content")
        return candidates[:self.max_candidates]

    def expand_from_suggestions(
        self,
        suggestions: List[str],
        seed_query: str,
    ) -> List[ExpansionCandidate]:
        """
        Extract expansion candidates from search suggestions.

        Processes autocomplete and "people also search for" suggestions.

        Args:
            suggestions: List of suggestion strings
            seed_query: Original query for similarity scoring

        Returns:
            List of ExpansionCandidate objects
        """
        logger.info(f"Expanding from {len(suggestions)} suggestions")

        candidates = []
        for suggestion in suggestions:
            # Extract unique terms from each suggestion
            terms = self._extract_meaningful_terms(suggestion)

            for term in terms:
                # Skip if term is in seed query
                if term.lower() in seed_query.lower():
                    continue

                candidate = ExpansionCandidate(
                    term=term,
                    score=0.0,
                    sources=["suggestion"],
                    frequencies={"suggestion": 1},
                    metadata={"original_suggestion": suggestion},
                )
                candidates.append(candidate)

        # Score candidates
        candidates = self.score_candidates(candidates, seed_query, suggestions)

        logger.info(f"Found {len(candidates)} candidates from suggestions")
        return candidates[:self.max_candidates]

    def score_candidates(
        self,
        candidates: List[ExpansionCandidate],
        seed_query: str,
        corpus: List[str],
    ) -> List[ExpansionCandidate]:
        """
        Score expansion candidates using multiple factors.

        Scoring algorithm:
        1. Frequency score: How often the term appears
        2. Source diversity: Number of different sources
        3. Position score: Title > Description > URL > Content
        4. Similarity score: Cosine similarity to seed query
        5. TF-IDF score: If available from content analysis

        Args:
            candidates: List of candidates to score
            seed_query: Original query
            corpus: Text corpus for TF-IDF calculation

        Returns:
            Sorted list of scored candidates
        """
        if not candidates:
            return []

        # Calculate similarity scores
        try:
            vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
            all_texts = [seed_query] + [c.term for c in candidates] + corpus

            # Handle case where we have too few documents
            if len(all_texts) < 2:
                similarity_scores = [0.0] * len(candidates)
            else:
                tfidf_matrix = vectorizer.fit_transform(all_texts)
                query_vector = tfidf_matrix[0]
                candidate_vectors = tfidf_matrix[1:len(candidates)+1]
                similarity_scores = cosine_similarity(query_vector, candidate_vectors)[0]

        except Exception as e:
            logger.warning(f"Could not calculate similarity scores: {e}")
            similarity_scores = [0.0] * len(candidates)

        # Source weights
        source_weights = {
            "title": 3.0,
            "description": 2.0,
            "url": 1.5,
            "content_noun": 2.5,
            "content_entity": 3.0,
            "suggestion": 2.0,
            "meta_keyword": 1.5,
        }

        # Score each candidate
        for i, candidate in enumerate(candidates):
            # Frequency score (normalized)
            total_freq = sum(candidate.frequencies.values())
            freq_score = min(total_freq / 10.0, 1.0)  # Cap at 1.0

            # Source diversity score
            diversity_score = len(candidate.sources) / len(source_weights)

            # Position/source score
            position_score = sum(
                source_weights.get(source, 1.0) * freq
                for source, freq in candidate.frequencies.items()
            ) / sum(candidate.frequencies.values())
            position_score = position_score / max(source_weights.values())  # Normalize

            # Similarity score
            similarity_score = similarity_scores[i]

            # TF-IDF bonus if available
            tfidf_bonus = 0.0
            if "tfidf_score" in candidate.metadata:
                tfidf_bonus = min(candidate.metadata["tfidf_score"] / 10.0, 0.5)

            # Combined score (weighted average)
            combined_score = (
                0.25 * freq_score +
                0.20 * diversity_score +
                0.25 * position_score +
                0.20 * similarity_score +
                0.10 * tfidf_bonus
            )

            candidate.score = combined_score
            candidate.metadata["score_components"] = {
                "frequency": freq_score,
                "diversity": diversity_score,
                "position": position_score,
                "similarity": similarity_score,
                "tfidf_bonus": tfidf_bonus,
            }

        # Sort by score
        candidates.sort(key=lambda x: x.score, reverse=True)

        # Filter by similarity threshold
        candidates = [c for c in candidates if similarity_scores[candidates.index(c)] >= self.similarity_threshold]

        return candidates

    def filter_candidates(
        self,
        candidates: List[ExpansionCandidate],
        seed_query: str,
        min_score: float = 0.1,
        exclude_terms: Optional[Set[str]] = None,
    ) -> List[ExpansionCandidate]:
        """
        Filter candidates based on quality criteria.

        Args:
            candidates: List of candidates to filter
            seed_query: Original query
            min_score: Minimum score threshold
            exclude_terms: Optional set of terms to exclude

        Returns:
            Filtered list of candidates
        """
        if exclude_terms is None:
            exclude_terms = set()

        # Extract seed query terms
        seed_terms = set(self._extract_meaningful_terms(seed_query))

        filtered = []
        for candidate in candidates:
            # Skip low scores
            if candidate.score < min_score:
                continue

            # Skip excluded terms
            if candidate.term.lower() in exclude_terms:
                continue

            # Skip terms already in seed query
            if candidate.term.lower() in seed_terms:
                continue

            # Skip very short or very long terms
            if len(candidate.term) < 3 or len(candidate.term) > 50:
                continue

            # Skip pure numbers
            if candidate.term.isdigit():
                continue

            filtered.append(candidate)

        return filtered

    def _extract_meaningful_terms(self, text: str) -> List[str]:
        """
        Extract meaningful terms from text.

        Args:
            text: Input text

        Returns:
            List of terms
        """
        # Convert to lowercase
        text = text.lower()

        # Remove special characters but keep spaces and hyphens
        text = re.sub(r'[^a-z0-9\s\-]', ' ', text)

        # Split into words
        words = text.split()

        # Common stop words to filter
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'should', 'could', 'may', 'might', 'can', 'this', 'that', 'these',
            'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'them',
            'their', 'what', 'which', 'who', 'when', 'where', 'why', 'how',
        }

        # Filter and return meaningful terms
        meaningful = []
        for word in words:
            if len(word) >= 3 and word not in stop_words:
                meaningful.append(word)

        return meaningful

    def _extract_url_terms(self, url: str) -> List[str]:
        """
        Extract meaningful terms from URL.

        Args:
            url: URL string

        Returns:
            List of terms
        """
        try:
            parsed = urlparse(url)

            # Extract from path
            path_parts = parsed.path.strip('/').split('/')

            terms = []
            for part in path_parts:
                # Split on hyphens and underscores
                sub_parts = re.split(r'[-_]', part)
                for sub_part in sub_parts:
                    if len(sub_part) >= 3:
                        terms.append(sub_part.lower())

            return terms

        except Exception:
            return []
