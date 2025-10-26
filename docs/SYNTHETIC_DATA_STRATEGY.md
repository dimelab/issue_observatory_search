# Synthetic Data Generation Strategy - Issue Observatory Search

## Overview
Synthetic data is crucial for testing the Issue Observatory Search application, particularly for:
- Testing scraping at scale without hitting real websites
- Simulating various network structures and patterns
- Testing NLP processing with diverse content
- Performance testing with realistic data volumes
- Demonstrating the tool's capabilities without real searches

---

## Synthetic Data Components

### 1. Mock Search Results
Generate realistic search engine results for testing without API calls.

```python
# backend/tests/factories/search_factory.py
import random
from faker import Faker
from datetime import datetime, timedelta

fake = Faker()

class SearchResultFactory:
    """Generate synthetic search results for different issue types"""
    
    # Domain pools for realistic results
    DOMAINS = {
        'news': ['cnn.com', 'bbc.co.uk', 'reuters.com', 'theguardian.com', 'nytimes.com'],
        'academic': ['nature.com', 'sciencedirect.com', 'journals.plos.org', 'academic.edu'],
        'government': ['europa.eu', 'gov.uk', 'who.int', 'un.org', 'congress.gov'],
        'ngo': ['greenpeace.org', 'amnesty.org', 'hrw.org', 'eff.org'],
        'blog': ['medium.com', 'wordpress.com', 'blogspot.com', 'substack.com'],
        'social': ['twitter.com', 'reddit.com', 'facebook.com', 'linkedin.com'],
        'danish': ['dr.dk', 'tv2.dk', 'politiken.dk', 'berlingske.dk', 'information.dk']
    }
    
    # Issue-specific keyword patterns
    ISSUE_PATTERNS = {
        'climate_change': {
            'keywords': ['climate', 'warming', 'carbon', 'emissions', 'renewable', 'fossil'],
            'entities': ['IPCC', 'Paris Agreement', 'Greta Thunberg', 'COP28'],
            'weight_distribution': {'news': 0.3, 'academic': 0.2, 'government': 0.2, 'ngo': 0.2, 'blog': 0.1}
        },
        'artificial_intelligence': {
            'keywords': ['AI', 'machine learning', 'neural', 'algorithm', 'automation', 'GPT'],
            'entities': ['OpenAI', 'Google DeepMind', 'MIT', 'Stanford AI Lab'],
            'weight_distribution': {'academic': 0.3, 'news': 0.3, 'blog': 0.2, 'social': 0.2}
        },
        'renewable_energy_denmark': {
            'keywords': ['vindmøller', 'wind', 'solar', 'grøn energi', 'Ørsted', 'havvind'],
            'entities': ['Ørsted', 'Vestas', 'Danish Energy Agency', 'DONG Energy'],
            'weight_distribution': {'danish': 0.4, 'government': 0.2, 'news': 0.2, 'academic': 0.2}
        }
    }
    
    @classmethod
    def create_search_results(cls, query: str, num_results: int = 10, language: str = 'en'):
        """Generate synthetic search results for a query"""
        results = []
        
        # Determine issue type from query
        issue_type = cls._classify_query(query)
        pattern = cls.ISSUE_PATTERNS.get(issue_type, cls.ISSUE_PATTERNS['climate_change'])
        
        for rank in range(1, num_results + 1):
            # Select domain based on weight distribution
            domain_type = cls._weighted_choice(pattern['weight_distribution'])
            domain = random.choice(cls.DOMAINS[domain_type])
            
            # Generate URL with relevant path
            url_slug = fake.slug()
            if random.random() > 0.5:
                # Include keywords in URL
                keyword = random.choice(pattern['keywords']).replace(' ', '-').lower()
                url_slug = f"{keyword}-{url_slug}"
            
            url = f"https://{domain}/{url_slug}"
            
            # Generate title with keywords
            title = cls._generate_title(query, pattern['keywords'], pattern['entities'])
            
            # Generate description
            description = cls._generate_description(query, pattern['keywords'], title)
            
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
    def _generate_title(cls, query: str, keywords: list, entities: list):
        """Generate realistic title with keywords"""
        templates = [
            "{entity} announces new {keyword} initiative",
            "How {keyword} is transforming {query}",
            "{keyword}: A comprehensive analysis",
            "Breaking: {entity} report on {keyword}",
            "The future of {query}: {keyword} perspectives",
            "{query} and {keyword}: What you need to know"
        ]
        
        template = random.choice(templates)
        return template.format(
            query=query,
            keyword=random.choice(keywords),
            entity=random.choice(entities) if entities else fake.company()
        )
```

### 2. Mock Website Content
Generate realistic website content for scraping tests.

```python
# backend/tests/factories/content_factory.py
class WebsiteContentFactory:
    """Generate synthetic website content for different domains"""
    
    CONTENT_TEMPLATES = {
        'news_article': {
            'structure': ['headline', 'byline', 'lead', 'body_paragraphs', 'quotes'],
            'avg_length': 800,
            'noun_density': 0.15
        },
        'academic_paper': {
            'structure': ['title', 'abstract', 'introduction', 'methodology', 'results', 'conclusion'],
            'avg_length': 3000,
            'noun_density': 0.20
        },
        'blog_post': {
            'structure': ['title', 'intro', 'sections', 'conclusion', 'comments'],
            'avg_length': 1200,
            'noun_density': 0.12
        },
        'government_report': {
            'structure': ['title', 'executive_summary', 'sections', 'recommendations', 'appendix'],
            'avg_length': 2000,
            'noun_density': 0.18
        }
    }
    
    @classmethod
    def create_website_content(cls, url: str, issue_type: str, depth: int = 1):
        """Generate synthetic website content with realistic structure"""
        
        # Determine content type from URL
        content_type = cls._determine_content_type(url)
        template = cls.CONTENT_TEMPLATES[content_type]
        
        # Generate main content
        content = cls._generate_structured_content(template, issue_type)
        
        # Generate linked pages for depth > 1
        linked_pages = []
        if depth > 1:
            num_links = random.randint(3, 10)
            for _ in range(num_links):
                linked_url = cls._generate_related_url(url)
                linked_content = cls._generate_structured_content(template, issue_type)
                linked_pages.append({
                    'url': linked_url,
                    'content': linked_content
                })
        
        return {
            'url': url,
            'html': cls._wrap_in_html(content),
            'text': cls._extract_text(content),
            'linked_pages': linked_pages,
            'metadata': {
                'title': content.get('title', ''),
                'language': cls._detect_language(url),
                'word_count': len(content.get('text', '').split()),
                'scraped_at': datetime.now()
            }
        }
    
    @classmethod
    def _generate_structured_content(cls, template: dict, issue_type: str):
        """Generate content following template structure"""
        fake = Faker()
        content_parts = []
        
        # Get relevant vocabulary for the issue
        vocab = cls._get_issue_vocabulary(issue_type)
        
        for section in template['structure']:
            if section == 'headline' or section == 'title':
                text = cls._generate_headline(vocab)
            elif section == 'abstract':
                text = cls._generate_abstract(vocab, 150)
            elif section == 'body_paragraphs' or section == 'sections':
                text = cls._generate_paragraphs(vocab, 5, template['noun_density'])
            elif section == 'quotes':
                text = cls._generate_quotes(vocab, 3)
            else:
                text = cls._generate_generic_section(vocab, 100)
            
            content_parts.append({'section': section, 'text': text})
        
        return {
            'title': content_parts[0]['text'],
            'sections': content_parts,
            'text': ' '.join([part['text'] for part in content_parts])
        }
```

### 3. Mock NLP Extracted Data
Generate realistic noun and entity extraction results.

```python
# backend/tests/factories/nlp_factory.py
class NLPDataFactory:
    """Generate synthetic NLP extraction results"""
    
    DANISH_NOUNS = ['energi', 'vindmølle', 'klima', 'bæredygtighed', 'forskning', 
                     'teknologi', 'miljø', 'udvikling', 'samfund', 'økonomi']
    
    ENGLISH_NOUNS = ['energy', 'climate', 'technology', 'research', 'policy', 
                      'sustainability', 'innovation', 'development', 'system', 'analysis']
    
    ENTITIES = {
        'PERSON': ['Anders Fogh Rasmussen', 'Greta Thunberg', 'Bill Gates', 'Elon Musk'],
        'ORG': ['European Union', 'Vestas', 'Ørsted', 'Google', 'UN', 'WHO'],
        'LOC': ['Denmark', 'Copenhagen', 'Brussels', 'Silicon Valley', 'Beijing'],
        'DATE': ['2024', 'January 2025', 'next decade', 'by 2030']
    }
    
    @classmethod
    def generate_extracted_nouns(cls, text: str, language: str = 'en', top_n: int = 20):
        """Generate realistic noun extraction with TF-IDF scores"""
        
        noun_pool = cls.ENGLISH_NOUNS if language == 'en' else cls.DANISH_NOUNS
        
        # Add some domain-specific nouns based on text content
        if 'climate' in text.lower() or 'klima' in text.lower():
            noun_pool += ['emissions', 'carbon', 'temperature', 'renewable']
        
        # Generate nouns with realistic frequency distribution (Zipf's law)
        nouns = []
        for i, noun in enumerate(random.sample(noun_pool, min(top_n, len(noun_pool)))):
            count = int(100 / (i + 1))  # Zipf distribution
            tfidf_score = random.uniform(0.1, 0.9) * (1 / (i + 1))
            
            nouns.append({
                'text': noun,
                'lemma': noun.lower(),
                'count': count,
                'tfidf_score': round(tfidf_score, 4)
            })
        
        return sorted(nouns, key=lambda x: x['tfidf_score'], reverse=True)
    
    @classmethod
    def generate_extracted_entities(cls, text: str, num_entities: int = 10):
        """Generate realistic NER results"""
        entities = []
        
        for entity_type in cls.ENTITIES.keys():
            num_of_type = random.randint(1, num_entities // len(cls.ENTITIES))
            
            for _ in range(num_of_type):
                entity = random.choice(cls.ENTITIES[entity_type])
                count = random.randint(1, 10)
                confidence = random.uniform(0.7, 0.99)
                
                entities.append({
                    'text': entity,
                    'type': entity_type,
                    'count': count,
                    'confidence': round(confidence, 3)
                })
        
        return entities
```

### 4. Mock Network Data
Generate realistic network structures for testing visualizations.

```python
# backend/tests/factories/network_factory.py
import networkx as nx

class NetworkDataFactory:
    """Generate synthetic network data for different network types"""
    
    @classmethod
    def create_issue_website_network(cls, num_queries: int = 5, num_websites: int = 50):
        """Generate search query to website network"""
        G = nx.Graph()
        
        # Add query nodes
        queries = [f"query_{i}" for i in range(num_queries)]
        for query in queries:
            G.add_node(query, node_type='query', color='#3b82f6')
        
        # Add website nodes with realistic domain distribution
        websites = []
        domain_distribution = {
            '.com': 0.4, '.org': 0.2, '.edu': 0.1, 
            '.gov': 0.1, '.dk': 0.1, '.eu': 0.1
        }
        
        for i in range(num_websites):
            domain = np.random.choice(
                list(domain_distribution.keys()),
                p=list(domain_distribution.values())
            )
            website = f"website{i}{domain}"
            websites.append(website)
            G.add_node(website, node_type='website', color='#10b981')
        
        # Add edges with rank-based weights (power law distribution)
        for query in queries:
            # Each query connects to subset of websites
            num_results = random.randint(10, 30)
            connected_sites = random.sample(websites, min(num_results, len(websites)))
            
            for rank, site in enumerate(connected_sites, 1):
                weight = 1 / rank  # Higher rank = lower weight
                G.add_edge(query, site, weight=weight, rank=rank)
        
        return G
    
    @classmethod
    def create_website_noun_network(cls, num_websites: int = 30, num_nouns: int = 100):
        """Generate website to noun bipartite network"""
        G = nx.Graph()
        
        # Add website nodes
        websites = [f"site_{i}.com" for i in range(num_websites)]
        for site in websites:
            G.add_node(site, node_type='website', bipartite=0)
        
        # Add noun nodes with categories
        noun_categories = {
            'technical': ['algorithm', 'data', 'system', 'network', 'protocol'],
            'environmental': ['climate', 'energy', 'sustainability', 'emissions', 'renewable'],
            'social': ['society', 'community', 'policy', 'governance', 'equality'],
            'economic': ['market', 'investment', 'growth', 'innovation', 'trade']
        }
        
        nouns = []
        for category, terms in noun_categories.items():
            for term in terms:
                for variant in [term, f"{term}s", f"{term}_research", f"new_{term}"]:
                    nouns.append(variant)
                    G.add_node(variant, node_type='noun', bipartite=1, category=category)
        
        # Connect with TF-IDF weighted edges
        for site in websites:
            # Each website connects to subset of nouns
            site_nouns = random.sample(nouns, random.randint(5, 20))
            
            for noun in site_nouns:
                # Generate realistic TF-IDF weight
                tfidf = random.uniform(0.1, 0.9)
                G.add_edge(site, noun, weight=tfidf)
        
        return G
    
    @classmethod
    def create_website_concept_network(cls, num_websites: int = 25, num_concepts: int = 15):
        """Generate website to concept knowledge graph"""
        G = nx.DiGraph()  # Directed for knowledge flow
        
        # Define concept clusters (following Rogers' issue mapping)
        concept_clusters = {
            'scientific_consensus': {
                'concepts': ['peer-reviewed research', 'empirical evidence', 'scientific method'],
                'color': '#3b82f6'
            },
            'policy_debate': {
                'concepts': ['regulatory framework', 'government intervention', 'policy instruments'],
                'color': '#8b5cf6'
            },
            'public_discourse': {
                'concepts': ['public opinion', 'media representation', 'social movements'],
                'color': '#10b981'
            },
            'economic_impacts': {
                'concepts': ['market dynamics', 'cost-benefit analysis', 'economic growth'],
                'color': '#f59e0b'
            }
        }
        
        # Add websites
        for i in range(num_websites):
            G.add_node(f"website_{i}", node_type='website')
        
        # Add concepts and connections
        for cluster_name, cluster_data in concept_clusters.items():
            for concept in cluster_data['concepts']:
                G.add_node(concept, node_type='concept', cluster=cluster_name, 
                          color=cluster_data['color'])
                
                # Connect to relevant websites
                num_connections = random.randint(3, 10)
                connected_sites = random.sample(
                    [n for n in G.nodes() if G.nodes[n].get('node_type') == 'website'],
                    num_connections
                )
                
                for site in connected_sites:
                    relevance = random.uniform(0.5, 1.0)
                    G.add_edge(site, concept, weight=relevance)
        
        return G
```

### 5. Test Scenarios with Synthetic Data

```python
# backend/tests/test_with_synthetic_data.py
class SyntheticDataTestSuite:
    """Comprehensive tests using synthetic data"""
    
    @pytest.fixture
    def synthetic_search_session(self):
        """Create a complete synthetic search session"""
        session = {
            'name': 'Climate Change Controversy Mapping',
            'queries': [
                'climate change scientific consensus',
                'climate change skepticism',
                'renewable energy solutions',
                'carbon emissions policy'
            ],
            'results': {},
            'scraped_content': {},
            'extracted_data': {}
        }
        
        # Generate search results for each query
        for query in session['queries']:
            results = SearchResultFactory.create_search_results(query, 50)
            session['results'][query] = results
            
            # Generate scraped content for top results
            for result in results[:10]:
                content = WebsiteContentFactory.create_website_content(
                    result['url'], 'climate_change', depth=2
                )
                session['scraped_content'][result['url']] = content
                
                # Generate NLP extractions
                nouns = NLPDataFactory.generate_extracted_nouns(content['text'])
                entities = NLPDataFactory.generate_extracted_entities(content['text'])
                session['extracted_data'][result['url']] = {
                    'nouns': nouns,
                    'entities': entities
                }
        
        return session
    
    def test_large_scale_scraping(self, synthetic_search_session):
        """Test system performance with large amounts of synthetic data"""
        # Simulate 1000 websites being scraped
        websites = []
        for i in range(1000):
            url = f"https://example{i}.com/article"
            content = WebsiteContentFactory.create_website_content(url, 'climate_change')
            websites.append(content)
        
        # Test batch processing
        start_time = time.time()
        processed = batch_process_websites(websites)
        processing_time = time.time() - start_time
        
        assert len(processed) == 1000
        assert processing_time < 60  # Should process 1000 sites in under a minute
    
    def test_network_generation_performance(self):
        """Test network generation with realistic data volumes"""
        # Generate large network
        G = NetworkDataFactory.create_issue_website_network(
            num_queries=20, 
            num_websites=500
        )
        
        # Test GEXF export performance
        start_time = time.time()
        gexf_data = export_to_gexf(G)
        export_time = time.time() - start_time
        
        assert export_time < 5  # Should export in under 5 seconds
        assert G.number_of_nodes() == 520
        assert G.number_of_edges() > 200
```

### 6. Demo Data Generation Script

```python
# scripts/generate_demo_data.py
"""
Generate synthetic demo data for showcasing the application
"""
import asyncio
from backend.tests.factories import *

async def generate_demo_data():
    """Generate comprehensive demo dataset"""
    
    print("Generating demo data for Issue Observatory Search...")
    
    # 1. Create demo user
    demo_user = await create_user(
        username="demo_researcher",
        email="researcher@university.edu",
        password="demo123"
    )
    
    # 2. Generate multiple research sessions
    research_topics = [
        {
            'name': 'Danish Renewable Energy Landscape',
            'queries': [
                'vindmøller danmark',
                'grøn energi danske virksomheder',
                'havvind projekter Nordsøen',
                'energiø Bornholm'
            ],
            'language': 'da'
        },
        {
            'name': 'AI Ethics Debate Mapping',
            'queries': [
                'AI ethics concerns',
                'algorithmic bias examples',
                'AI regulation EU',
                'artificial general intelligence risks'
            ],
            'language': 'en'
        },
        {
            'name': 'Climate Change Discourse Analysis',
            'queries': [
                'climate emergency',
                'climate hoax claims',
                'IPCC reports',
                'net zero targets criticism'
            ],
            'language': 'en'
        }
    ]
    
    for topic in research_topics:
        # Create search session
        session = await create_search_session(
            user_id=demo_user.id,
            name=topic['name']
        )
        
        # Generate search results
        for query in topic['queries']:
            results = SearchResultFactory.create_search_results(
                query, 
                num_results=30,
                language=topic['language']
            )
            
            # Store results
            await store_search_results(session.id, query, results)
            
            # Generate scraped content for top 10
            for result in results[:10]:
                content = WebsiteContentFactory.create_website_content(
                    result['url'],
                    issue_type=query.split()[0].lower(),
                    depth=2
                )
                
                # Store content
                await store_website_content(result['url'], content)
                
                # Generate and store NLP extractions
                nouns = NLPDataFactory.generate_extracted_nouns(
                    content['text'],
                    language=topic['language']
                )
                entities = NLPDataFactory.generate_extracted_entities(content['text'])
                
                await store_nlp_extractions(result['url'], nouns, entities)
        
        # Generate networks
        for network_type in ['issue_website', 'website_noun', 'website_concept']:
            if network_type == 'issue_website':
                G = NetworkDataFactory.create_issue_website_network(
                    num_queries=len(topic['queries']),
                    num_websites=len(results) * len(topic['queries'])
                )
            elif network_type == 'website_noun':
                G = NetworkDataFactory.create_website_noun_network()
            else:
                G = NetworkDataFactory.create_website_concept_network()
            
            # Store network
            await store_network(session.id, network_type, G)
    
    print(f"✅ Generated demo data for {len(research_topics)} research topics")
    print(f"📊 Total synthetic websites: {len(research_topics) * 30 * 4}")
    print(f"🔗 Generated {len(research_topics) * 3} networks")
    
if __name__ == "__main__":
    asyncio.run(generate_demo_data())
```

## Benefits of Synthetic Data

### 1. **Testing at Scale**
- Test with 1000s of websites without real scraping
- Verify performance under load
- Test pagination and filtering with large datasets

### 2. **Reproducible Testing**
- Consistent test data across development environments
- Deterministic test outcomes
- Version control test data generation

### 3. **Edge Case Testing**
- Test with extreme data volumes
- Unusual character sets and languages
- Network structures with specific properties

### 4. **Demo & Training**
- Safe demonstration environment
- Training data for new users
- Showcase all features without real API costs

### 5. **Development Speed**
- No waiting for real scraping
- No API rate limits during testing
- Rapid iteration on features

## Implementation Prompt for Claude Code

```
Acting as the BACKEND DEVELOPER agent, please implement synthetic data generation for testing:

1. Create a `backend/tests/factories/` directory
2. Implement the SearchResultFactory for generating mock search results
3. Implement the WebsiteContentFactory for generating mock website content
4. Implement the NLPDataFactory for generating mock NLP extractions
5. Implement the NetworkDataFactory for generating test networks
6. Create a demo data generation script in `scripts/generate_demo_data.py`
7. Add pytest fixtures using the factories for testing
8. Create performance tests using large synthetic datasets

The synthetic data should:
- Be realistic and follow real-world patterns (Zipf's law for word frequency, power law for network connections)
- Support both Danish and English content
- Include edge cases (very long content, special characters, empty results)
- Be deterministic when seeded for reproducible tests

This will allow us to test the entire pipeline without external dependencies.
```

## Testing Strategy with Synthetic Data

### Unit Tests
- Test individual components with small synthetic datasets
- Verify data transformations
- Test error handling with malformed synthetic data

### Integration Tests
- Test full pipeline with synthetic data
- Verify data flow between components
- Test database operations with bulk synthetic data

### Performance Tests
- Load testing with 10,000+ synthetic websites
- Network generation with 1,000+ nodes
- Concurrent user simulation with synthetic sessions

### UI/UX Testing
- Test interface with various data volumes
- Verify visualization with different network structures
- Test responsiveness with large synthetic datasets

This synthetic data approach will significantly improve development speed, testing reliability, and demonstration capabilities!
