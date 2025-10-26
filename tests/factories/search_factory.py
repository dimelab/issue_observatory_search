"""
SearchResultFactory - Generate realistic synthetic search results.

This factory generates search engine results that mimic real search behavior:
- Realistic domain distributions (news, academic, government, etc.)
- Issue-specific keyword patterns and entities
- Rank-based relevance scores
- Support for multiple languages (English and Danish)
- Temporal variations in results
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import random
from faker import Faker

from .base import (
    set_seed,
    get_issue_vocabulary,
    weighted_choice,
    detect_language
)


class SearchResultFactory:
    """Generate synthetic search results for different issue types."""

    # Domain pools for realistic results
    DOMAINS = {
        'news': [
            'cnn.com', 'bbc.co.uk', 'reuters.com', 'theguardian.com',
            'nytimes.com', 'washingtonpost.com', 'theverge.com', 'wired.com'
        ],
        'academic': [
            'nature.com', 'sciencedirect.com', 'journals.plos.org',
            'academic.oup.com', 'springer.com', 'researchgate.net',
            'arxiv.org', 'scholar.google.com'
        ],
        'government': [
            'europa.eu', 'gov.uk', 'who.int', 'un.org',
            'congress.gov', 'whitehouse.gov', 'nih.gov', 'nasa.gov'
        ],
        'ngo': [
            'greenpeace.org', 'amnesty.org', 'hrw.org', 'eff.org',
            'oxfam.org', 'redcross.org', 'savethechildren.org'
        ],
        'blog': [
            'medium.com', 'wordpress.com', 'blogspot.com', 'substack.com',
            'ghost.io', 'tumblr.com', 'dev.to'
        ],
        'social': [
            'twitter.com', 'reddit.com', 'facebook.com',
            'linkedin.com', 'youtube.com', 'instagram.com'
        ],
        'danish': [
            'dr.dk', 'tv2.dk', 'politiken.dk', 'berlingske.dk',
            'information.dk', 'jyllands-posten.dk', 'bt.dk',
            'energinet.dk', 'ens.dk', 'kefm.dk'
        ]
    }

    # Issue-specific patterns for realistic search results
    ISSUE_PATTERNS = {
        'climate': {
            'keywords': [
                'climate', 'warming', 'carbon', 'emissions', 'renewable',
                'fossil', 'greenhouse', 'temperature', 'IPCC', 'Paris Agreement'
            ],
            'entities': [
                'IPCC', 'Paris Agreement', 'Greta Thunberg', 'COP28',
                'UN Climate Summit', 'Greenpeace', 'WWF'
            ],
            'weight_distribution': {
                'news': 0.3, 'academic': 0.2, 'government': 0.2,
                'ngo': 0.2, 'blog': 0.1
            }
        },
        'ai': {
            'keywords': [
                'AI', 'artificial intelligence', 'machine learning', 'neural',
                'algorithm', 'automation', 'GPT', 'deep learning', 'LLM'
            ],
            'entities': [
                'OpenAI', 'Google DeepMind', 'Anthropic', 'MIT',
                'Stanford AI Lab', 'Geoffrey Hinton', 'Sam Altman'
            ],
            'weight_distribution': {
                'academic': 0.3, 'news': 0.3, 'blog': 0.2, 'social': 0.2
            }
        },
        'renewable': {
            'keywords': [
                'wind', 'solar', 'renewable energy', 'turbine', 'panel',
                'battery', 'grid', 'storage', 'clean energy', 'green power'
            ],
            'entities': [
                'Ørsted', 'Vestas', 'Siemens Gamesa', 'IRENA',
                'International Renewable Energy Agency', 'Danish Energy Agency'
            ],
            'weight_distribution': {
                'news': 0.3, 'academic': 0.2, 'government': 0.2,
                'blog': 0.2, 'ngo': 0.1
            }
        },
        'vindmøller': {  # Danish renewable energy
            'keywords': [
                'vindmøller', 'havvind', 'landvind', 'grøn energi',
                'vedvarende energi', 'energiø', 'solenergi', 'vindenergi'
            ],
            'entities': [
                'Ørsted', 'Vestas', 'Energistyrelsen', 'Energinet',
                'Copenhagen Infrastructure Partners', 'Better Energy'
            ],
            'weight_distribution': {
                'danish': 0.4, 'government': 0.2, 'news': 0.2,
                'academic': 0.1, 'blog': 0.1
            }
        }
    }

    @classmethod
    def create_search_results(
        cls,
        query: str,
        num_results: int = 10,
        language: str = 'en',
        seed: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate synthetic search results for a query.

        Args:
            query: Search query string
            num_results: Number of results to generate
            language: Language code ('en' or 'da')
            seed: Random seed for reproducibility

        Returns:
            List of search result dictionaries with keys:
                - url: Result URL
                - title: Result title
                - description: Result snippet/description
                - rank: Search result rank (1-based)
                - domain: Domain name
                - retrieved_at: Timestamp when result was retrieved

        Example:
            >>> results = SearchResultFactory.create_search_results(
            ...     "climate change", num_results=5, seed=42
            ... )
            >>> assert len(results) == 5
            >>> assert results[0]['rank'] == 1
            >>> assert 'climate' in results[0]['title'].lower()
        """
        if seed is not None:
            set_seed(seed)

        fake = Faker()
        if seed is not None:
            Faker.seed(seed)

        # Determine issue type from query
        issue_type = cls._classify_query(query)
        pattern = cls.ISSUE_PATTERNS.get(issue_type, cls.ISSUE_PATTERNS['climate'])

        results = []
        for rank in range(1, num_results + 1):
            # Select domain based on weight distribution
            domain_type = weighted_choice(pattern['weight_distribution'], seed=seed)
            domain = random.choice(cls.DOMAINS[domain_type])

            # Generate URL with relevant path
            url_slug = fake.slug()
            if random.random() > 0.5:
                # Include keywords in URL for realism
                keyword = random.choice(pattern['keywords']).replace(' ', '-').lower()
                url_slug = f"{keyword}-{url_slug}"

            url = f"https://{domain}/{url_slug}"

            # Generate title with keywords
            title = cls._generate_title(query, pattern['keywords'], pattern['entities'], fake)

            # Generate description
            description = cls._generate_description(query, pattern['keywords'], title, fake)

            results.append({
                'url': url,
                'title': title,
                'description': description,
                'rank': rank,
                'domain': domain,
                'retrieved_at': datetime.now() - timedelta(hours=random.randint(0, 72))
            })

        return results

    @classmethod
    def create_bulk_results(
        cls,
        queries: List[str],
        results_per_query: int = 10,
        language: str = 'en',
        seed: Optional[int] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate search results for multiple queries efficiently.

        Args:
            queries: List of search queries
            results_per_query: Number of results per query
            language: Language code ('en' or 'da')
            seed: Random seed for reproducibility

        Returns:
            Dictionary mapping query to list of results

        Example:
            >>> queries = ['climate change', 'AI ethics', 'renewable energy']
            >>> all_results = SearchResultFactory.create_bulk_results(queries, 5)
            >>> assert len(all_results) == 3
            >>> assert len(all_results['climate change']) == 5
        """
        if seed is not None:
            set_seed(seed)

        results_map = {}
        for i, query in enumerate(queries):
            # Use different seed for each query if base seed provided
            query_seed = seed + i if seed is not None else None
            results_map[query] = cls.create_search_results(
                query, results_per_query, language, query_seed
            )

        return results_map

    @classmethod
    def create_temporal_results(
        cls,
        query: str,
        time_periods: List[datetime],
        num_results: int = 10,
        seed: Optional[int] = None
    ) -> Dict[datetime, List[Dict[str, Any]]]:
        """
        Generate search results across different time periods.

        Useful for testing temporal analysis and result evolution.

        Args:
            query: Search query
            time_periods: List of datetime objects representing different time points
            num_results: Number of results per time period
            seed: Random seed for reproducibility

        Returns:
            Dictionary mapping timestamp to results

        Example:
            >>> from datetime import datetime, timedelta
            >>> periods = [datetime.now() - timedelta(days=i) for i in [0, 30, 60]]
            >>> temporal_results = SearchResultFactory.create_temporal_results(
            ...     'climate policy', periods, 5
            ... )
            >>> assert len(temporal_results) == 3
        """
        if seed is not None:
            set_seed(seed)

        temporal_map = {}
        for i, timestamp in enumerate(time_periods):
            period_seed = seed + i if seed is not None else None
            results = cls.create_search_results(query, num_results, seed=period_seed)

            # Adjust retrieved_at to match time period
            for result in results:
                result['retrieved_at'] = timestamp - timedelta(
                    hours=random.randint(0, 24)
                )

            temporal_map[timestamp] = results

        return temporal_map

    @classmethod
    def _classify_query(cls, query: str) -> str:
        """
        Classify query into issue type based on keywords.

        Args:
            query: Search query string

        Returns:
            Issue type string
        """
        query_lower = query.lower()

        # Check for Danish keywords first
        danish_keywords = ['vindmøller', 'havvind', 'energi', 'dansk', 'danmark']
        if any(kw in query_lower for kw in danish_keywords):
            return 'vindmøller'

        # Check for AI keywords
        ai_keywords = ['ai', 'artificial intelligence', 'machine learning', 'neural', 'gpt']
        if any(kw in query_lower for kw in ai_keywords):
            return 'ai'

        # Check for renewable energy keywords
        renewable_keywords = ['wind', 'solar', 'renewable', 'turbine', 'clean energy']
        if any(kw in query_lower for kw in renewable_keywords):
            return 'renewable'

        # Default to climate
        return 'climate'

    @classmethod
    def _generate_title(
        cls,
        query: str,
        keywords: List[str],
        entities: List[str],
        fake: Faker
    ) -> str:
        """
        Generate realistic title with keywords and entities.

        Args:
            query: Original search query
            keywords: Relevant keywords for this issue
            entities: Named entities related to this issue
            fake: Faker instance

        Returns:
            Generated title string
        """
        templates = [
            "{entity} announces new {keyword} initiative",
            "How {keyword} is transforming {query}",
            "{keyword}: A comprehensive analysis",
            "Breaking: {entity} report on {keyword}",
            "The future of {query}: {keyword} perspectives",
            "{query} and {keyword}: What you need to know",
            "Understanding {keyword} in the context of {query}",
            "{entity}'s latest findings on {keyword}",
            "New research reveals {keyword} impact on {query}",
            "{keyword} solutions for {query} challenges"
        ]

        template = random.choice(templates)
        return template.format(
            query=query,
            keyword=random.choice(keywords),
            entity=random.choice(entities) if entities else fake.company()
        )

    @classmethod
    def _generate_description(
        cls,
        query: str,
        keywords: List[str],
        title: str,
        fake: Faker
    ) -> str:
        """
        Generate realistic description/snippet for search result.

        Args:
            query: Original search query
            keywords: Relevant keywords
            title: Generated title
            fake: Faker instance

        Returns:
            Generated description string
        """
        # Generate 2-3 sentences
        sentences = []

        # First sentence: introduce the topic
        intro_templates = [
            "This article explores {keyword} in relation to {query}.",
            "Recent developments in {keyword} have significant implications for {query}.",
            "Experts discuss the role of {keyword} in addressing {query}.",
            "A comprehensive look at how {keyword} affects {query} outcomes."
        ]
        sentences.append(
            random.choice(intro_templates).format(
                keyword=random.choice(keywords),
                query=query
            )
        )

        # Second sentence: add details
        detail_templates = [
            "The study examines {keyword1} and {keyword2} across multiple sectors.",
            "Key findings highlight the importance of {keyword1} for future {keyword2}.",
            "Researchers analyze {keyword1} trends and their impact on {keyword2}.",
            "The report provides insights into {keyword1} and {keyword2} dynamics."
        ]
        sentences.append(
            random.choice(detail_templates).format(
                keyword1=random.choice(keywords),
                keyword2=random.choice(keywords)
            )
        )

        # Occasionally add third sentence
        if random.random() > 0.5:
            conclusion_templates = [
                "Read more about the latest {keyword} developments.",
                "Learn how this affects {query} policy and practice.",
                "Expert commentary on {keyword} implications included.",
                "Full analysis and data visualization available."
            ]
            sentences.append(
                random.choice(conclusion_templates).format(
                    keyword=random.choice(keywords),
                    query=query
                )
            )

        return ' '.join(sentences)
