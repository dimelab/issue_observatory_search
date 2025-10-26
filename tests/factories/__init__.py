"""
Synthetic data generation factories for Issue Observatory Search.

This package provides comprehensive factories for generating realistic
synthetic data for testing and demonstration purposes:

- SearchResultFactory: Generate search engine results
- WebsiteContentFactory: Generate website content with HTML
- NLPDataFactory: Generate NLP extraction results (nouns, entities)
- NetworkDataFactory: Generate network structures (bipartite, knowledge graphs)

All factories support:
- Deterministic generation via seed parameter
- Realistic statistical distributions (Zipf's law, power law)
- Multiple languages (English and Danish)
- Edge cases for robustness testing
- Bulk generation for performance testing

Example usage:
    >>> from tests.factories import SearchResultFactory, WebsiteContentFactory
    >>>
    >>> # Generate search results
    >>> results = SearchResultFactory.create_search_results(
    ...     "climate change", num_results=10, seed=42
    ... )
    >>>
    >>> # Generate website content
    >>> content = WebsiteContentFactory.create_website_content(
    ...     results[0]['url'], 'climate', depth=2, seed=42
    ... )
    >>>
    >>> # Generate NLP extractions
    >>> from tests.factories import NLPDataFactory
    >>> nouns = NLPDataFactory.generate_extracted_nouns(
    ...     content['text'], language='en', top_n=20, seed=42
    ... )
    >>>
    >>> # Generate networks
    >>> from tests.factories import NetworkDataFactory
    >>> network = NetworkDataFactory.create_issue_website_network(
    ...     num_queries=5, num_websites=50, seed=42
    ... )
"""

from .base import (
    set_seed,
    generate_zipf_distribution,
    generate_power_law_distribution,
    get_issue_vocabulary,
    detect_language,
    generate_realistic_tfidf_scores,
    weighted_choice,
    generate_zipf_frequencies
)

from .search_factory import SearchResultFactory
from .content_factory import WebsiteContentFactory
from .nlp_factory import NLPDataFactory
from .network_factory import NetworkDataFactory

__all__ = [
    # Base utilities
    'set_seed',
    'generate_zipf_distribution',
    'generate_power_law_distribution',
    'get_issue_vocabulary',
    'detect_language',
    'generate_realistic_tfidf_scores',
    'weighted_choice',
    'generate_zipf_frequencies',

    # Factories
    'SearchResultFactory',
    'WebsiteContentFactory',
    'NLPDataFactory',
    'NetworkDataFactory',
]

__version__ = '1.0.0'
