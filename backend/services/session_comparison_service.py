"""Session comparison service for analyzing multiple search sessions."""
import logging
import math
from typing import List, Dict, Any, Set, Tuple
from collections import Counter, defaultdict
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from scipy.stats import spearmanr

from backend.models.search import SearchSession, SearchQuery, SearchResult
from backend.models.user import User
from backend.models.analysis import ExtractedNoun, ExtractedEntity
from backend.models.website import WebsiteContent
from backend.core.search.domain_filter import DomainFilter

logger = logging.getLogger(__name__)


class SessionComparisonService:
    """
    Service for comparing multiple search sessions.

    Provides comprehensive comparison metrics:
    - URL and domain overlap
    - Ranking differences
    - Sphere distribution
    - Discourse analysis (noun/entity differences)
    """

    def __init__(self, db: AsyncSession, user: User):
        """
        Initialize session comparison service.

        Args:
            db: Database session
            user: Current user
        """
        self.db = db
        self.user = user
        self.domain_filter = DomainFilter()

    async def compare_sessions(
        self,
        session_ids: List[int],
        comparison_type: str = "full",
    ) -> Dict[str, Any]:
        """
        Perform comprehensive comparison of multiple sessions.

        Args:
            session_ids: List of session IDs to compare
            comparison_type: Type of comparison (full, urls, domains, discourse, rankings)

        Returns:
            Dict with comparison results

        Raises:
            ValueError: If sessions not found or not owned by user
        """
        logger.info(f"Comparing {len(session_ids)} sessions (type={comparison_type})")

        # Validate and load sessions
        sessions = await self._load_sessions(session_ids)

        if len(sessions) < 2:
            raise ValueError("Need at least 2 sessions to compare")

        # Load all results for each session
        session_data = []
        for session in sessions:
            data = await self._load_session_data(session.id)
            session_data.append(data)

        # Perform requested comparisons
        result = {
            "session_ids": session_ids,
            "session_names": [s.name for s in sessions],
            "comparison_type": comparison_type,
        }

        if comparison_type in ["full", "urls"]:
            result["url_comparison"] = self._compare_urls(session_data)

        if comparison_type in ["full", "domains"]:
            result["domain_comparison"] = self._compare_domains(session_data)

        if comparison_type in ["full", "rankings"]:
            result["ranking_comparison"] = await self._compare_rankings(session_data)

        if comparison_type in ["full", "spheres"]:
            result["sphere_comparison"] = self._compare_spheres(session_data)

        if comparison_type in ["full", "discourse"]:
            result["discourse_comparison"] = await self._compare_discourse(
                session_data
            )

        logger.info("Session comparison completed")
        return result

    async def calculate_url_overlap(
        self,
        session_ids: List[int],
    ) -> Dict[str, Any]:
        """
        Calculate URL overlap between sessions (Venn diagram data).

        Args:
            session_ids: List of session IDs

        Returns:
            Dict with overlap statistics and Venn diagram data
        """
        sessions = await self._load_sessions(session_ids)

        # Get URL sets for each session
        url_sets = []
        for session in sessions:
            results = await self._get_session_results(session.id)
            urls = {r.url for r in results}
            url_sets.append(urls)

        # Calculate overlaps
        overlap_data = self._calculate_set_overlaps(
            url_sets,
            [s.name for s in sessions],
        )

        return overlap_data

    async def calculate_domain_overlap(
        self,
        session_ids: List[int],
    ) -> Dict[str, Any]:
        """
        Calculate domain overlap between sessions.

        Args:
            session_ids: List of session IDs

        Returns:
            Dict with domain overlap data
        """
        sessions = await self._load_sessions(session_ids)

        # Get domain sets for each session
        domain_sets = []
        for session in sessions:
            results = await self._get_session_results(session.id)
            domains = {r.domain for r in results}
            domain_sets.append(domains)

        # Calculate overlaps
        overlap_data = self._calculate_set_overlaps(
            domain_sets,
            [s.name for s in sessions],
        )

        return overlap_data

    async def find_unique_results(
        self,
        session_ids: List[int],
    ) -> Dict[str, List[Dict]]:
        """
        Find results unique to each session.

        Args:
            session_ids: List of session IDs

        Returns:
            Dict mapping session names to unique results
        """
        sessions = await self._load_sessions(session_ids)

        # Get all URLs for each session
        session_urls = {}
        session_results_map = {}

        for session in sessions:
            results = await self._get_session_results(session.id)
            urls = {r.url for r in results}
            session_urls[session.id] = urls

            # Create URL to result mapping
            session_results_map[session.id] = {r.url: r for r in results}

        # Find unique URLs for each session
        unique_results = {}

        for session in sessions:
            # Get URLs from other sessions
            other_urls = set()
            for other_id in session_ids:
                if other_id != session.id:
                    other_urls.update(session_urls.get(other_id, set()))

            # Find unique URLs
            unique_urls = session_urls[session.id] - other_urls

            # Get result objects for unique URLs
            unique = []
            for url in unique_urls:
                result = session_results_map[session.id][url]
                unique.append({
                    "url": result.url,
                    "title": result.title,
                    "domain": result.domain,
                    "rank": result.rank,
                })

            unique_results[session.name] = unique

        return unique_results

    async def compare_rankings(
        self,
        session_ids: List[int],
    ) -> Dict[str, Any]:
        """
        Compare rankings for shared URLs across sessions.

        Args:
            session_ids: List of session IDs

        Returns:
            Dict with ranking comparison data including Spearman correlation
        """
        sessions = await self._load_sessions(session_ids)

        # Get results for each session
        session_results = {}
        for session in sessions:
            results = await self._get_session_results(session.id)
            # Map URL to rank
            session_results[session.id] = {r.url: r.rank for r in results}

        # Find shared URLs
        all_urls = [set(results.keys()) for results in session_results.values()]
        shared_urls = set.intersection(*all_urls) if all_urls else set()

        if not shared_urls:
            return {
                "shared_count": 0,
                "message": "No shared URLs found",
            }

        # Calculate ranking differences
        ranking_data = []
        for url in shared_urls:
            ranks = [session_results[sid][url] for sid in session_ids]
            ranking_data.append({
                "url": url,
                "ranks": ranks,
                "rank_difference": max(ranks) - min(ranks),
            })

        # Calculate Spearman correlation for pairs
        correlations = []
        if len(session_ids) >= 2:
            for i in range(len(session_ids)):
                for j in range(i + 1, len(session_ids)):
                    # Get rankings for shared URLs
                    ranks_i = [session_results[session_ids[i]][url] for url in shared_urls]
                    ranks_j = [session_results[session_ids[j]][url] for url in shared_urls]

                    # Calculate Spearman correlation
                    if len(ranks_i) > 1:
                        corr, pvalue = spearmanr(ranks_i, ranks_j)
                        correlations.append({
                            "session_pair": f"{sessions[i].name} vs {sessions[j].name}",
                            "correlation": round(corr, 3),
                            "p_value": round(pvalue, 4),
                        })

        return {
            "shared_count": len(shared_urls),
            "ranking_differences": sorted(
                ranking_data, key=lambda x: x["rank_difference"], reverse=True
            )[:20],
            "correlations": correlations,
        }

    async def _load_sessions(self, session_ids: List[int]) -> List[SearchSession]:
        """Load and validate sessions."""
        result = await self.db.execute(
            select(SearchSession).where(
                and_(
                    SearchSession.id.in_(session_ids),
                    SearchSession.user_id == self.user.id,
                )
            )
        )
        sessions = list(result.scalars().all())

        if len(sessions) != len(session_ids):
            found_ids = [s.id for s in sessions]
            missing = set(session_ids) - set(found_ids)
            raise ValueError(f"Sessions not found or not accessible: {missing}")

        return sessions

    async def _load_session_data(self, session_id: int) -> Dict[str, Any]:
        """Load all data for a session."""
        results = await self._get_session_results(session_id)

        return {
            "session_id": session_id,
            "results": results,
            "urls": {r.url for r in results},
            "domains": {r.domain for r in results},
            "url_count": len(results),
            "unique_domains": len({r.domain for r in results}),
        }

    async def _get_session_results(self, session_id: int) -> List[SearchResult]:
        """Get all results for a session."""
        # Get all queries for session
        queries = await self.db.execute(
            select(SearchQuery).where(SearchQuery.session_id == session_id)
        )
        query_ids = [q.id for q in queries.scalars().all()]

        if not query_ids:
            return []

        # Get all results
        results = await self.db.execute(
            select(SearchResult).where(SearchResult.query_id.in_(query_ids))
        )

        return list(results.scalars().all())

    def _compare_urls(self, session_data: List[Dict]) -> Dict[str, Any]:
        """Compare URLs across sessions."""
        url_sets = [data["urls"] for data in session_data]

        # Calculate Jaccard similarity
        similarities = []
        for i in range(len(url_sets)):
            for j in range(i + 1, len(url_sets)):
                intersection = len(url_sets[i] & url_sets[j])
                union = len(url_sets[i] | url_sets[j])
                jaccard = intersection / union if union > 0 else 0

                similarities.append({
                    "session_pair": f"{i} vs {j}",
                    "jaccard_similarity": round(jaccard, 3),
                    "intersection": intersection,
                    "union": union,
                })

        # Find common and unique URLs
        all_urls = set.union(*url_sets) if url_sets else set()
        common_urls = set.intersection(*url_sets) if url_sets else set()

        return {
            "total_unique_urls": len(all_urls),
            "common_urls_count": len(common_urls),
            "similarities": similarities,
            "url_counts": [len(urls) for urls in url_sets],
        }

    def _compare_domains(self, session_data: List[Dict]) -> Dict[str, Any]:
        """Compare domains across sessions."""
        domain_sets = [data["domains"] for data in session_data]

        # Calculate domain overlap
        all_domains = set.union(*domain_sets) if domain_sets else set()
        common_domains = set.intersection(*domain_sets) if domain_sets else set()

        # Calculate domain diversity (Shannon entropy)
        diversities = []
        for data in session_data:
            results = data["results"]
            domain_counts = Counter([r.domain for r in results])
            total = sum(domain_counts.values())

            entropy = 0
            for count in domain_counts.values():
                p = count / total
                entropy -= p * math.log2(p) if p > 0 else 0

            diversities.append(round(entropy, 3))

        return {
            "total_unique_domains": len(all_domains),
            "common_domains_count": len(common_domains),
            "common_domains": list(common_domains),
            "domain_counts": [len(domains) for domains in domain_sets],
            "domain_diversity": diversities,
        }

    async def _compare_rankings(self, session_data: List[Dict]) -> Dict[str, Any]:
        """Compare rankings for shared URLs."""
        # Build URL to rank mappings
        url_rankings = defaultdict(list)

        for i, data in enumerate(session_data):
            for result in data["results"]:
                url_rankings[result.url].append((i, result.rank))

        # Find URLs that appear in multiple sessions
        multi_session_urls = {
            url: ranks for url, ranks in url_rankings.items() if len(ranks) > 1
        }

        # Calculate ranking volatility
        volatility_scores = []
        for url, ranks in multi_session_urls.items():
            rank_values = [r[1] for r in ranks]
            volatility = max(rank_values) - min(rank_values)

            volatility_scores.append({
                "url": url,
                "appearances": len(ranks),
                "ranks": rank_values,
                "volatility": volatility,
            })

        return {
            "multi_session_urls": len(multi_session_urls),
            "most_volatile": sorted(
                volatility_scores, key=lambda x: x["volatility"], reverse=True
            )[:10],
        }

    def _compare_spheres(self, session_data: List[Dict]) -> Dict[str, Any]:
        """Compare sphere distributions across sessions."""
        sphere_distributions = []

        for data in session_data:
            # Classify each result
            spheres = defaultdict(int)
            for result in data["results"]:
                classification = self.domain_filter.classify_sphere(result.url)
                spheres[classification.sphere] += 1

            sphere_distributions.append(dict(spheres))

        # Calculate chi-square test statistic (simplified)
        # For production, use scipy.stats.chi2_contingency

        return {
            "sphere_distributions": sphere_distributions,
            "unique_spheres": list(set(
                sphere
                for dist in sphere_distributions
                for sphere in dist.keys()
            )),
        }

    async def _compare_discourse(self, session_data: List[Dict]) -> Dict[str, Any]:
        """Compare discourse (nouns/entities) across sessions."""
        discourse_data = []

        for data in session_data:
            session_id = data["session_id"]

            # Get all content IDs for this session
            results = data["results"]
            urls = [r.url for r in results]

            # Get website content
            contents = await self.db.execute(
                select(WebsiteContent).where(WebsiteContent.url.in_(urls))
            )
            content_list = list(contents.scalars().all())
            content_ids = [c.id for c in content_list]

            if not content_ids:
                discourse_data.append({
                    "session_id": session_id,
                    "nouns": [],
                    "entities": [],
                })
                continue

            # Get nouns
            nouns = await self.db.execute(
                select(ExtractedNoun).where(
                    ExtractedNoun.website_content_id.in_(content_ids)
                )
            )
            noun_list = list(nouns.scalars().all())

            # Aggregate nouns
            noun_freq = Counter()
            for noun in noun_list:
                noun_freq[noun.lemma] += noun.frequency

            # Get entities
            entities = await self.db.execute(
                select(ExtractedEntity).where(
                    ExtractedEntity.website_content_id.in_(content_ids)
                )
            )
            entity_list = list(entities.scalars().all())

            # Aggregate entities
            entity_freq = Counter([e.text for e in entity_list])

            discourse_data.append({
                "session_id": session_id,
                "top_nouns": noun_freq.most_common(20),
                "top_entities": entity_freq.most_common(20),
            })

        # Find unique and shared terms
        all_nouns = [set(dict(d["top_nouns"]).keys()) for d in discourse_data]
        all_entities = [set(dict(d["top_entities"]).keys()) for d in discourse_data]

        shared_nouns = set.intersection(*all_nouns) if all_nouns else set()
        shared_entities = set.intersection(*all_entities) if all_entities else set()

        return {
            "discourse_by_session": discourse_data,
            "shared_nouns": list(shared_nouns),
            "shared_entities": list(shared_entities),
        }

    def _calculate_set_overlaps(
        self,
        sets: List[Set],
        labels: List[str],
    ) -> Dict[str, Any]:
        """Calculate overlaps for multiple sets (Venn diagram data)."""
        n = len(sets)

        # Calculate all intersections
        overlaps = {}

        # Single sets
        for i in range(n):
            overlaps[f"only_{labels[i]}"] = len(sets[i] - set.union(*[sets[j] for j in range(n) if j != i]))

        # Pairwise intersections
        for i in range(n):
            for j in range(i + 1, n):
                intersection = sets[i] & sets[j]
                # Exclude items in other sets
                exclusive = intersection - set.union(*[sets[k] for k in range(n) if k not in [i, j]])
                overlaps[f"{labels[i]}_and_{labels[j]}"] = len(exclusive)

        # All sets intersection
        if n > 2:
            all_intersection = set.intersection(*sets)
            overlaps["all"] = len(all_intersection)

        # Jaccard similarity
        jaccard = {}
        for i in range(n):
            for j in range(i + 1, n):
                intersection = len(sets[i] & sets[j])
                union = len(sets[i] | sets[j])
                jaccard[f"{labels[i]}_vs_{labels[j]}"] = round(
                    intersection / union if union > 0 else 0, 3
                )

        return {
            "overlaps": overlaps,
            "jaccard_similarities": jaccard,
            "set_sizes": {labels[i]: len(sets[i]) for i in range(n)},
        }
