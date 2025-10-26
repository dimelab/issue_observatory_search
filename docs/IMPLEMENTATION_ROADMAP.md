# Implementation Roadmap: LLM Concept Extraction & Network Backboning

## Overview

This document provides a prioritized implementation roadmap for the two critical gaps identified:
1. **LLM-based concept extraction** from full website content (not just noun phrases)
2. **Network backboning** for complexity reduction

Both features are essential for the website-concept network generation capability.

**Key Update**: The LLM extraction approach has been revised to process **full textual content** from all scraped pages of a website, rather than extracted noun phrases. This provides better context and higher-quality concepts, but requires text aggregation, chunking strategies, and updated cost estimates.

## Implementation Priority

### Phase 1: Core Backboning (Week 1)
**Priority: HIGH** - Required for all network types, simpler implementation

1. **Install Dependencies**
   ```bash
   pip install backbone-network networkx>=3.0 numpy scipy
   ```

2. **Implement Core Backboning** (`app/core/network/backboning.py`)
   - `NetworkBackboner` class with disparity filter
   - `BackboningConfig` dataclass
   - Basic validation and statistics

3. **Integration with Network Builders** (`app/core/network/builders/*.py`)
   - Add backboning step to each builder
   - Pass backboning config from API
   - Store statistics in metadata

4. **Database Schema Updates**
   ```sql
   ALTER TABLE network_exports
   ADD COLUMN backboning_applied BOOLEAN DEFAULT FALSE,
   ADD COLUMN backboning_algorithm VARCHAR(50),
   ADD COLUMN backboning_alpha FLOAT,
   ADD COLUMN original_edge_count INTEGER,
   ADD COLUMN backboning_statistics JSONB;
   ```

5. **API Updates** (`app/api/network.py`)
   - Add `NetworkBackboningConfig` to request schema
   - Include backboning stats in response
   - Add defaults for each network type

6. **Testing**
   - Unit tests for disparity filter
   - Integration tests with sample networks
   - Performance benchmarks

**Deliverable**: All network types support optional backboning

**Estimated Time**: 3-5 days

---

### Phase 2: LLM Concept Extraction Foundation (Week 2-3)
**Priority: HIGH** - Required for website-concept networks

1. **Install Dependencies**
   ```bash
   pip install openai anthropic tenacity sentence-transformers scikit-learn tiktoken httpx
   ```

2. **Configuration Setup** (`app/core/config.py`)
   - Add `ConceptExtractionConfig` settings
   - Environment variables for API keys
   - Rate limit configuration
   - Ollama configuration
   - Chunking/summarization settings

3. **Database Schema Updates**
   ```sql
   -- Enhance extracted_concepts table
   ALTER TABLE extracted_concepts
   ADD COLUMN model_used VARCHAR(50),
   ADD COLUMN temperature FLOAT,
   ADD COLUMN token_count INTEGER,
   ADD COLUMN processing_time FLOAT,
   ADD COLUMN cache_hit BOOLEAN DEFAULT FALSE,
   ADD COLUMN quality_score FLOAT,
   ADD COLUMN extraction_method VARCHAR(20) DEFAULT 'llm',  -- 'llm', 'ollama', 'clustering', 'fallback'
   ADD COLUMN page_count INTEGER DEFAULT 1,
   ADD COLUMN was_summarized BOOLEAN DEFAULT FALSE;

   -- Create cache table (note: website_id instead of content_id, content_hash instead of noun_hash)
   CREATE TABLE concept_extraction_cache (
       id SERIAL PRIMARY KEY,
       website_id INTEGER REFERENCES websites(id),
       cache_key VARCHAR(255) UNIQUE,
       content_hash VARCHAR(32),  -- Hash of aggregated website content
       model VARCHAR(50),
       temperature FLOAT,
       concepts JSONB,
       token_count INTEGER,
       page_count INTEGER DEFAULT 1,
       was_summarized BOOLEAN DEFAULT FALSE,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       expires_at TIMESTAMP
   );

   -- Create cost tracking table
   CREATE TABLE llm_api_usage (
       id SERIAL PRIMARY KEY,
       user_id INTEGER REFERENCES users(id),
       website_id INTEGER REFERENCES websites(id),
       model VARCHAR(50),
       operation VARCHAR(50),  -- 'concept_extraction', 'summarization', 'refinement'
       input_tokens INTEGER,
       output_tokens INTEGER,
       cost_usd DECIMAL(10, 6),
       success BOOLEAN,
       error_type VARCHAR(50),
       was_summarized BOOLEAN DEFAULT FALSE,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
   ```

4. **Text Aggregation** (`app/core/analysis/content_aggregator.py`)
   - `WebsiteContentAggregator` class
   - Aggregate text from all scraped pages per website
   - Text cleaning and normalization
   - Token counting with tiktoken

5. **Chunking & Summarization** (`app/core/analysis/chunking_strategy.py`)
   - `ContentChunkingStrategy` class
   - Handle websites exceeding 120K token limit
   - Implement summarization for large content
   - Multi-stage summarization for very large sites

6. **Core Implementation** (`app/core/analysis/concept_extractor.py`)
   - `ConceptExtractor` class
   - OpenAI API integration with full text prompts
   - Prompt engineering for full content
   - Response parsing
   - Basic error handling

7. **Ollama Integration** (`app/core/analysis/ollama_client.py`)
   - `OllamaClient` class
   - `OllamaConceptExtractor` class
   - Local LLM integration
   - Availability checking

8. **Caching Layer** (`app/core/analysis/concept_cache.py`)
   - Redis L1 cache
   - Database L2 cache
   - Content-hash based cache keys
   - TTL management

9. **Testing**
   - Unit tests with mocked LLM responses
   - Integration tests with real API (small scale)
   - Test text aggregation and chunking
   - Prompt quality validation

**Deliverable**: Basic concept extraction working with full-text processing and caching

**Estimated Time**: 7-10 days (increased due to text aggregation complexity)

---

### Phase 3: LLM Robustness & Rate Limiting (Week 3-4)
**Priority: MEDIUM** - Essential for production reliability

1. **Rate Limiting** (`app/core/analysis/rate_limiter.py`)
   - `APIRateLimiter` for OpenAI limits
   - `UserRateLimiter` for per-user quotas
   - Redis-based tracking

2. **Enhanced Error Handling**
   - Retry logic with exponential backoff
   - Fallback to Claude Haiku
   - Fallback to Ollama (local LLM)
   - Rule-based clustering fallback (extract nouns from full text first)
   - Top-nouns fallback (final resort)

3. **Ollama Deployment** (Optional but recommended)
   - Install Ollama on server: `curl https://ollama.ai/install.sh | sh`
   - Download model: `ollama pull llama3.1`
   - Configure service: `OLLAMA_BASE_URL=http://localhost:11434`
   - Test availability before extraction
   - Document deployment for inference server option

4. **Monitoring & Logging**
   - Structured logging for all LLM calls (including Ollama)
   - Success/failure metrics per model
   - Cost tracking (zero cost for Ollama)
   - Performance monitoring
   - Summarization tracking

5. **API Endpoints** (`app/api/analysis.py`)
   - `POST /api/analysis/extract-concepts` (accepts website_ids now)
   - `GET /api/analysis/concepts/{website_id}`
   - Rate limit headers
   - Async processing for large batches
   - Return summarization stats

6. **Celery Tasks** (`app/tasks/concept_extraction.py`)
   - `extract_concepts_task` for background processing
   - Handle text aggregation per website
   - Progress tracking (show page count, token count)
   - Batch processing

7. **Testing**
   - Error handling scenarios
   - Rate limit testing
   - Fallback mechanism validation (all 5 stages)
   - Ollama integration testing
   - Large website handling

**Deliverable**: Production-ready concept extraction with full error handling and Ollama fallback

**Estimated Time**: 5-7 days (increased for Ollama integration)

---

### Phase 4: Website-Concept Network Builder (Week 4-5)
**Priority: HIGH** - Primary feature depending on Phase 2 & 3

1. **Network Builder** (`app/core/network/builders/website_concept.py`)
   - `WebsiteConceptBuilder` class
   - Automatic concept extraction trigger
   - Similarity-based edge creation
   - Embedding generation

2. **Integration with Concept Extraction**
   - Check for existing concepts
   - Trigger extraction if missing
   - Handle extraction failures gracefully

3. **Backboning Integration**
   - Apply aggressive backboning (α=0.01-0.03)
   - Target 80-85% edge reduction
   - Validate result quality

4. **API Integration**
   - Update `/api/network/generate` endpoint
   - Add website_concept config options
   - Return extraction statistics

5. **Testing**
   - End-to-end tests with real data
   - Performance benchmarks (target: <30s for 1000 nodes)
   - Quality validation

**Deliverable**: Full website-concept network generation

**Estimated Time**: 3-5 days

---

### Phase 5: Advanced Features (Week 5-6)
**Priority: LOW** - Nice-to-have enhancements

1. **Advanced Backboning**
   - Noise-corrected backbone algorithm
   - Adaptive parameter selection
   - Multiple weight types support

2. **LLM Enhancements**
   - Concept refinement prompts
   - Quality scoring
   - Concept clustering
   - Multi-language optimization

3. **Cost Optimization**
   - Batch processing optimization
   - Prompt compression
   - Cache warming strategies

4. **User Features**
   - Backboning presets (conservative, standard, aggressive)
   - Custom concept prompts
   - Cost reports
   - Quality dashboards

**Deliverable**: Enhanced features and optimizations

**Estimated Time**: 5-7 days

---

## Technical Dependencies

### External Libraries

```requirements.txt
# Core dependencies
networkx>=3.0
numpy>=1.24.0
scipy>=1.10.0

# Backboning
backbone-network>=1.0.0

# LLM Integration
openai>=1.0.0
anthropic>=0.8.0
tenacity>=8.2.0
tiktoken>=0.5.0  # Token counting for GPT models
httpx>=0.24.0    # For Ollama API calls

# NLP & Embeddings
sentence-transformers>=2.2.0
scikit-learn>=1.3.0
spacy>=3.6.0  # For noun extraction in fallback

# Async & Caching
aioredis>=2.0.0
asyncio>=3.4.3
```

### API Keys Required

```env
# LLM APIs
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Configuration
DEFAULT_LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.3
MAX_CONTENT_LENGTH=120000
CONCEPT_CACHE_TTL_HOURS=168

# Ollama (Local LLM)
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1

# Summarization
ENABLE_SUMMARIZATION=true
SUMMARIZATION_THRESHOLD_TOKENS=120000
```

---

## Integration Points

### 1. Database Models

Update SQLAlchemy models:

```python
# app/models/network.py
class NetworkExport(Base):
    # ... existing fields ...
    backboning_applied = Column(Boolean, default=False)
    backboning_algorithm = Column(String(50))
    backboning_alpha = Column(Float)
    original_edge_count = Column(Integer)
    backboning_statistics = Column(JSON)

# app/models/analysis.py
class ExtractedConcept(Base):
    # ... existing fields ...
    model_used = Column(String(50))
    temperature = Column(Float)
    token_count = Column(Integer)
    processing_time = Column(Float)
    cache_hit = Column(Boolean, default=False)
    quality_score = Column(Float)
    extraction_method = Column(String(20), default='llm')
```

### 2. Service Layer

Create new services:

```python
# app/services/concept_extraction_service.py
class ConceptExtractionService:
    def __init__(self, db: AsyncSession, redis, llm_client):
        self.db = db
        self.cache = ConceptCache(redis, db)
        self.extractor = ConceptExtractor(llm_client)
        self.rate_limiter = APIRateLimiter()

    async def extract_concepts(
        self,
        content_id: int,
        user_id: int,
        force_refresh: bool = False
    ) -> ConceptExtractionResult:
        # Implementation from spec
        pass

# app/services/network_service.py
class NetworkService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.backboner = NetworkBackboner()

    async def generate_network(
        self,
        network_type: str,
        session_ids: List[int],
        user_id: int,
        backboning_config: Optional[BackboningConfig] = None
    ) -> NetworkExport:
        # Implementation with backboning
        pass
```

### 3. API Routers

Update routers:

```python
# app/api/network.py
@router.post("/generate")
async def generate_network(
    request: NetworkGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    network_service: NetworkService = Depends(get_network_service)
):
    # Validate backboning config
    backboning_config = request.backboning or BackboningParameters.for_network_type(
        request.type,
        node_count=estimated_nodes,
        edge_count=estimated_edges
    )

    # Generate network
    result = await network_service.generate_network(
        network_type=request.type,
        session_ids=request.session_ids,
        user_id=current_user.id,
        backboning_config=backboning_config
    )

    return result

# app/api/analysis.py
@router.post("/extract-concepts")
async def extract_concepts(
    request: ConceptExtractionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    concept_service: ConceptExtractionService = Depends(get_concept_service)
):
    # Rate limiting
    # Extract concepts
    # Return results
    pass
```

### 4. Celery Tasks

Create background tasks:

```python
# app/tasks/concept_extraction.py
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def extract_concepts_task(
    self,
    content_ids: List[int],
    user_id: int,
    force_refresh: bool = False
):
    # Batch concept extraction
    # Update progress
    # Handle errors
    pass

# app/tasks/network_generation.py
@celery_app.task(bind=True)
def generate_network_task(
    self,
    network_type: str,
    session_ids: List[int],
    user_id: int,
    backboning_config: dict
):
    # 1. Extract concepts if needed (for website_concept type)
    # 2. Build network
    # 3. Apply backboning
    # 4. Export to GEXF
    # 5. Store metadata
    pass
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_backboning.py
def test_disparity_filter()
def test_bipartite_preservation()
def test_weight_normalization()

# tests/test_concept_extraction.py
def test_prompt_generation()
def test_response_parsing()
def test_cache_hit()
def test_fallback_mechanisms()
```

### Integration Tests

```python
# tests/integration/test_concept_extraction.py
async def test_full_extraction_pipeline()
async def test_rate_limiting()
async def test_cost_tracking()

# tests/integration/test_network_generation.py
async def test_website_concept_network()
async def test_backboning_integration()
```

### Performance Tests

```python
# tests/performance/test_network_performance.py
def test_1000_node_network_under_30s()
def test_backboning_performance()
def test_concept_extraction_throughput()
```

---

## Monitoring & Observability

### Metrics to Track

1. **Concept Extraction**
   - Extractions per hour/day
   - Cache hit rate
   - Average latency
   - Success rate by model
   - Cost per extraction
   - Token usage

2. **Backboning**
   - Networks backboned
   - Average reduction percentage
   - Processing time by network size
   - Validation scores

3. **Network Generation**
   - Networks generated per type
   - Average generation time
   - Success/failure rates
   - Size distribution

### Logging

```python
import structlog

logger = structlog.get_logger(__name__)

# Concept extraction
logger.info(
    "concept_extraction_completed",
    content_id=content_id,
    model=model,
    concepts_count=len(concepts),
    tokens=token_count,
    duration=duration,
    cache_hit=cache_hit
)

# Backboning
logger.info(
    "network_backboning_completed",
    network_id=network_id,
    algorithm=algorithm,
    original_edges=original_edges,
    backboned_edges=backboned_edges,
    reduction_pct=reduction_pct,
    duration=duration
)
```

### Alerts

1. **High Error Rate**: >10% LLM failures in 1 hour
2. **High Cost**: Daily LLM cost exceeds threshold
3. **Slow Performance**: Network generation >60s
4. **Low Cache Hit Rate**: <50% cache hits

---

## Cost Estimation

### LLM Costs (GPT-4o-mini) - Updated for Full Text Processing

**Assumptions:**
- Average website: 5 scraped pages
- Average content: ~15,000 tokens (after cleaning)
- Large websites: 100K+ tokens (requiring summarization)
- Output: ~100 tokens per extraction
- Price: $0.15/1M input, $0.60/1M output

**Cost per website (typical):**
- Input: 15,000 tokens × $0.15/1M = $0.00225
- Output: 100 tokens × $0.60/1M = $0.00006
- **Total: ~$0.0023 per website**

**Cost per website (large, with summarization):**
- Summarization: 100,000 tokens × $0.15/1M = $0.015
- Extraction: 50,000 tokens × $0.15/1M = $0.0075
- **Total: ~$0.023 per large website**

**Scale (first run):**
- 1,000 websites: ~$23 (mix of typical and large)
- 10,000 websites: ~$230
- 100,000 websites: ~$2,300

**With 90% cache hit rate** (subsequent runs):
- 1,000 websites: $2.30
- 10,000 websites: $23
- 100,000 websites: $230

**Cost Comparison:**
- Old approach (nouns): $0.14 per 1,000 websites
- New approach (full text): $23 per 1,000 websites (first run)
- **Trade-off**: ~165x more expensive, but significantly better quality

### Ollama Costs (Local LLM)

**Setup:**
- One-time: Server with GPU (~$500-2000 hardware or $0.50-2/hr cloud GPU)
- Running costs: Electricity/compute time
- **API costs: $0** (no external API calls)

**When to use Ollama:**
- Very high volume (>100K websites/month)
- API budget constraints
- Data privacy requirements
- After initial GPT-4o-mini extraction for quality baseline

### Infrastructure Costs

- Redis (caching): ~$10/month
- Additional database storage: ~$10/month (more data with full text)
- Monitoring/logging: ~$5/month
- Ollama server (optional): ~$50-200/month (depending on GPU)

**Total monthly overhead: ~$25-225 + LLM costs**

---

## Migration Plan

### Existing Data

If there's already scraped content without concepts:

1. **Gradual Migration**
   - Extract concepts on-demand when network is generated
   - Background job to extract for popular content
   - Cache warming for frequently accessed content

2. **Bulk Extraction** (optional)
   ```python
   # Migration script
   async def migrate_existing_content():
       content_items = await db.query(WebsiteContent).filter(
           ~WebsiteContent.extracted_concepts.any()
       ).all()

       for content in content_items:
           await concept_service.extract_concepts(
               content_id=content.id,
               user_id=content.user_id
           )
   ```

---

## Risk Mitigation

### Technical Risks

1. **LLM API Downtime**
   - **Mitigation**: Multiple fallback models, rule-based fallback
   - **Impact**: Reduced quality, continued operation

2. **High Costs**
   - **Mitigation**: Aggressive caching, rate limiting, cost alerts
   - **Impact**: Budget overruns

3. **Poor Concept Quality**
   - **Mitigation**: Validation prompts, quality scoring, user feedback
   - **Impact**: Less useful networks

4. **Performance Issues**
   - **Mitigation**: Caching, async processing, optimization
   - **Impact**: Slow user experience

### Operational Risks

1. **API Key Exposure**
   - **Mitigation**: Environment variables, key rotation, access controls
   - **Impact**: Security breach, cost theft

2. **Rate Limit Exhaustion**
   - **Mitigation**: Per-user quotas, tiered limits, queue management
   - **Impact**: Service degradation

---

## Success Criteria

### Phase 1 (Backboning)
- [ ] All network types support backboning
- [ ] Performance: <30s for 1000-node network
- [ ] Validation: >0.7 weight correlation
- [ ] Tests: >90% coverage

### Phase 2 (Concept Extraction)
- [ ] Concepts extracted from website content
- [ ] Cache hit rate: >85% after warmup
- [ ] Average latency: <2s per website
- [ ] Tests: >85% coverage

### Phase 3 (Robustness)
- [ ] Error rate: <5%
- [ ] Fallback mechanisms working
- [ ] Rate limiting effective
- [ ] Cost tracking accurate

### Phase 4 (Website-Concept Networks)
- [ ] Full pipeline working end-to-end
- [ ] Performance target met
- [ ] Quality validation passing
- [ ] User documentation complete

### Phase 5 (Polish)
- [ ] Advanced features implemented
- [ ] User feedback incorporated
- [ ] Optimizations applied
- [ ] Production monitoring deployed

---

## Next Steps

1. **Review Specifications**
   - `LLM_CONCEPT_EXTRACTION_SPECIFICATION.md`
   - `NETWORK_BACKBONING_SPECIFICATION.md`

2. **Set Up Development Environment**
   - Install dependencies
   - Configure API keys
   - Set up Redis

3. **Create Feature Branch**
   ```bash
   git checkout -b feature/concept-extraction-backboning
   ```

4. **Start with Phase 1**
   - Implement core backboning
   - Write tests
   - Integration

5. **Iterate Through Phases**
   - Review and test each phase
   - Adjust based on findings
   - Document learnings

---

## Questions for Product Owner

1. **Priority**: Should we implement both features in parallel or sequentially?
2. **Budget**: What's the acceptable monthly LLM cost budget?
3. **Quality**: What's the minimum acceptable concept quality score?
4. **Performance**: Is <30s network generation a hard requirement?
5. **Features**: Are advanced features (Phase 5) required for launch?
6. **Migration**: Should we bulk-extract concepts for existing content?

---

## Conclusion

This roadmap provides a structured, phased approach to implementing both LLM concept extraction and network backboning. The specifications are detailed, production-ready, and aligned with digital methods research requirements.

**Key Strengths:**
- Scientifically rigorous algorithms
- Comprehensive error handling
- Cost-effective implementation
- Research reproducibility
- Performance optimized

**Estimated Total Time**: 4-6 weeks for full implementation

**Estimated Monthly Cost**: $20 infrastructure + $10-50 LLM costs (depending on usage)

Start with Phase 1 (backboning) as it's simpler, foundational, and benefits all network types immediately. Then build out LLM extraction with proper caching and error handling to ensure production reliability.
