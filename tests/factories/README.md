# Synthetic Data Generation Factories

This package provides comprehensive factories for generating realistic synthetic data for the Issue Observatory Search application. All factories support deterministic generation via seed parameters and follow realistic statistical distributions.

## Installation

All required dependencies are in `requirements.txt`:

```bash
pip install -r requirements.txt
```

Key dependencies:
- `faker>=22.0.0` - For generating realistic fake data
- `numpy>=1.26.3` - For statistical distributions
- `networkx>=3.2.1` - For network generation

## Quick Start

```python
from tests.factories import (
    SearchResultFactory,
    WebsiteContentFactory,
    NLPDataFactory,
    NetworkDataFactory
)

# Generate search results
results = SearchResultFactory.create_search_results(
    query="climate change",
    num_results=10,
    language='en',
    seed=42  # For reproducibility
)

# Generate website content
content = WebsiteContentFactory.create_website_content(
    url=results[0]['url'],
    issue_type='climate',
    depth=2,  # Include linked pages
    seed=42
)

# Generate NLP extractions
nouns = NLPDataFactory.generate_extracted_nouns(
    text=content['text'],
    language='en',
    top_n=20,
    seed=42
)

entities = NLPDataFactory.generate_extracted_entities(
    text=content['text'],
    num_entities=10,
    seed=42
)

# Generate networks
network = NetworkDataFactory.create_issue_website_network(
    num_queries=5,
    num_websites=50,
    seed=42
)
```

## Factory Components

### 1. SearchResultFactory (`search_factory.py`)

Generates realistic search engine results with:
- Domain-appropriate distributions (news, academic, government, NGO, etc.)
- Issue-specific keywords and entities
- Rank-based relevance
- Support for English and Danish
- Temporal variations

**Key Methods:**
- `create_search_results(query, num_results, language, seed)` - Generate results for single query
- `create_bulk_results(queries, results_per_query, language, seed)` - Bulk generation
- `create_temporal_results(query, time_periods, num_results, seed)` - Time-series results

**Example:**
```python
results = SearchResultFactory.create_search_results(
    query="vindmøller danmark",
    num_results=30,
    language='da',
    seed=42
)
# Returns list of dicts with: url, title, description, rank, domain, retrieved_at
```

### 2. WebsiteContentFactory (`content_factory.py`)

Generates structured website content with:
- Content types: news articles, academic papers, blogs, government reports
- Realistic HTML structure
- Issue-specific vocabulary
- Linked pages for depth testing
- Edge cases (empty, huge, unicode, malformed)

**Key Methods:**
- `create_website_content(url, issue_type, depth, seed)` - Generate page with structure
- `create_bulk_content(urls, issue_type, seed)` - Bulk content generation
- `create_edge_case_content(case_type, url, seed)` - Edge cases for robustness testing

**Example:**
```python
content = WebsiteContentFactory.create_website_content(
    url="https://nature.com/climate-study",
    issue_type='climate',
    depth=2,  # Main page + linked pages
    seed=42
)
# Returns dict with: url, html, text, linked_pages, metadata
```

### 3. NLPDataFactory (`nlp_factory.py`)

Generates realistic NLP extraction results:
- Noun extraction with Zipf's law frequency distribution
- TF-IDF scores following power law
- Named Entity Recognition (PERSON, ORG, LOC, DATE)
- Danish and English vocabularies
- Confidence scores and lemmatization

**Key Methods:**
- `generate_extracted_nouns(text, language, top_n, seed)` - Extract nouns with TF-IDF
- `generate_extracted_entities(text, num_entities, seed)` - NER results
- `generate_bulk_extractions(texts, language, seed)` - Bulk NLP processing
- `generate_sentiment_scores(num_documents, seed)` - Sentiment analysis

**Example:**
```python
nouns = NLPDataFactory.generate_extracted_nouns(
    text="Climate change requires urgent action...",
    language='en',
    top_n=20,
    seed=42
)
# Returns list of dicts with: text, lemma, count, tfidf_score

entities = NLPDataFactory.generate_extracted_entities(
    text="Ørsted announced new wind projects...",
    num_entities=10,
    seed=42
)
# Returns list of dicts with: text, type, count, confidence
```

### 4. NetworkDataFactory (`network_factory.py`)

Generates realistic network structures:
- Issue-website bipartite networks
- Website-noun bipartite networks
- Website-concept knowledge graphs (directed)
- Power law degree distribution
- Community structure
- GEXF export support

**Key Methods:**
- `create_issue_website_network(num_queries, num_websites, seed)` - Bipartite query→website
- `create_website_noun_network(num_websites, num_nouns, seed)` - Bipartite website→noun
- `create_website_concept_network(num_websites, num_concepts, seed)` - Knowledge graph
- `create_large_scale_network(size, seed)` - Performance testing networks
- `export_to_gexf(G, include_viz)` - Export to GEXF format

**Example:**
```python
network = NetworkDataFactory.create_issue_website_network(
    num_queries=5,
    num_websites=50,
    seed=42
)
# Returns NetworkX Graph with bipartite structure

# Export to GEXF
gexf_data = NetworkDataFactory.export_to_gexf(network)

# Calculate metrics
metrics = NetworkDataFactory.calculate_network_metrics(network)
```

### 5. Base Utilities (`base.py`)

Shared utilities used by all factories:
- `set_seed(seed)` - Set random seed for reproducibility
- `generate_zipf_distribution(n, alpha)` - Zipf's law for word frequencies
- `generate_power_law_distribution(n, gamma)` - Power law for network degrees
- `get_issue_vocabulary(issue_type)` - Issue-specific terms and entities
- `detect_language(text)` - Simple language detection
- `weighted_choice(choices, seed)` - Weighted random selection

## Testing Fixtures

All factories are integrated with pytest fixtures in `tests/conftest.py`:

```python
def test_my_feature(synthetic_search_results):
    """Use synthetic data in tests."""
    assert len(synthetic_search_results) == 10

def test_with_large_dataset(large_synthetic_dataset):
    """Test with comprehensive dataset."""
    assert len(large_synthetic_dataset['search_results']) == 100
    assert large_synthetic_dataset['network'].number_of_nodes() >= 1000
```

Available fixtures:
- `synthetic_search_results` - 10 search results
- `synthetic_search_results_bulk` - Multiple queries
- `synthetic_website_content` - Single page
- `synthetic_website_content_with_depth` - Page with links
- `synthetic_bulk_content` - Multiple pages
- `synthetic_nlp_data` - Nouns and entities
- `synthetic_nlp_bulk` - Multiple extractions
- `synthetic_network` - Issue-website network
- `synthetic_website_noun_network` - Website-noun network
- `synthetic_concept_network` - Concept knowledge graph
- `large_synthetic_dataset` - Complete dataset for performance testing

## Performance Tests

Run comprehensive performance tests:

```bash
pytest tests/test_synthetic_performance.py -v -s
```

Tests include:
- Generating 1000+ search results
- Processing 500+ documents
- Creating networks with 1000+ nodes
- GEXF export performance
- Bulk operations
- Edge case handling

## Demo Data Generation

Generate complete demo dataset for the application:

```bash
python scripts/generate_demo_data.py --num-topics 3 --results-per-query 30
```

This creates:
- Demo user account (username: demo_researcher, password: demo123)
- 3 research topics with multiple queries each
- Search results, website content, NLP extractions
- All network types
- Ready-to-use demo environment

## Realistic Data Characteristics

### Statistical Distributions

1. **Zipf's Law (Word Frequencies)**
   - Frequency of nth most common word ∝ 1/n
   - Used for: noun extraction, TF-IDF scores
   - Realistic word frequency patterns

2. **Power Law (Network Degrees)**
   - P(k) ∝ k^(-γ) where γ ≈ 2-3
   - Used for: network node degrees, link distributions
   - Few high-degree hubs, many low-degree nodes

### Multilingual Support

- **English**: Full vocabulary for climate, AI, renewable energy
- **Danish**: Native vocabulary (vindmøller, energi, klima, etc.)
- **Language Detection**: Automatic language inference from content

### Issue Types

Pre-configured vocabularies for:
- `climate` - Climate change, emissions, mitigation
- `ai` - Artificial intelligence, machine learning, ethics
- `renewable` - Wind, solar, renewable energy
- `vindmøller` - Danish renewable energy (wind energy focus)

## Edge Cases

Test robustness with edge case content:

```python
# Empty content
empty = WebsiteContentFactory.create_edge_case_content('empty')

# Very long document (50,000+ words)
huge = WebsiteContentFactory.create_edge_case_content('huge')

# Unicode and special characters
unicode = WebsiteContentFactory.create_edge_case_content('unicode')

# Malformed HTML
malformed = WebsiteContentFactory.create_edge_case_content('malformed')
```

## Best Practices

1. **Always use seeds for reproducibility**:
   ```python
   results = SearchResultFactory.create_search_results(query, seed=42)
   ```

2. **Use bulk methods for performance**:
   ```python
   contents = WebsiteContentFactory.create_bulk_content(urls, issue_type, seed=42)
   ```

3. **Match language to issue type**:
   ```python
   # Danish issues
   results = SearchResultFactory.create_search_results(
       "vindmøller", language='da', seed=42
   )

   # English issues
   results = SearchResultFactory.create_search_results(
       "climate change", language='en', seed=42
   )
   ```

4. **Test with realistic volumes**:
   ```python
   # Use large_synthetic_dataset fixture for performance tests
   def test_performance(large_synthetic_dataset):
       # 100 queries, 3000 results, 1000+ node network
       pass
   ```

## Architecture

```
tests/factories/
├── __init__.py              # Package exports
├── base.py                  # Shared utilities and distributions
├── search_factory.py        # Search result generation
├── content_factory.py       # Website content generation
├── nlp_factory.py           # NLP extraction generation
├── network_factory.py       # Network structure generation
└── README.md                # This file
```

## Contributing

When adding new factories or features:

1. Follow existing patterns (class-based factories with class methods)
2. Support `seed` parameter for deterministic generation
3. Include comprehensive docstrings with examples
4. Add corresponding pytest fixtures in `conftest.py`
5. Add performance tests in `test_synthetic_performance.py`
6. Update this README with new features

## References

- **Zipf's Law**: G.K. Zipf, "Human Behavior and the Principle of Least Effort" (1949)
- **Power Law Networks**: A.-L. Barabási & R. Albert, "Emergence of scaling in random networks" (1999)
- **Issue Mapping**: Rogers, R. "Mapping Public Web Space with the Issuecrawler" (2010)

## Support

For questions or issues with synthetic data generation:
1. Check this README and docstrings in factory classes
2. Review test examples in `test_synthetic_performance.py`
3. Run `pytest tests/test_synthetic_performance.py -v` to verify installation
