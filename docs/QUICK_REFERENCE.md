# Quick Reference: LLM Concept Extraction & Network Backboning

## Executive Summary

This document provides quick-reference answers to the two critical specification gaps:

### 1. LLM-Based Concept Extraction (Full Text Approach)

**Selected Model**: OpenAI GPT-4o-mini
- **Cost**: $0.15 per 1M input tokens, $0.60 per 1M output tokens
- **Performance**: 2-5 seconds per website (typical), 10-30 seconds (large websites with summarization)
- **Quality**: Excellent for concept extraction with full context

**Input**: Full textual content from ALL pages of a website (not just noun phrases)

**Fallback Chain**: GPT-4o-mini → Claude 3 Haiku → Ollama (local LLM) → Rule-based clustering → Top nouns

**Caching Strategy**: Two-level (Redis + Database), content-hash based, 1-week TTL, 90%+ hit rate expected

**Cost per 1000 websites**: ~$23 first run, ~$2.30 subsequent runs (90% cached)
**Cost Comparison**: ~165x more expensive than noun-based approach, but significantly better quality

### 2. Network Backboning

**Selected Algorithm**: Disparity Filter (Serrano et al., 2009)
- **Rationale**: Statistically principled, fast O(E), widely validated
- **Default α**: 0.05 (standard significance level)
- **Performance**: <30s for 1000-node networks

**Network-Specific Defaults**:
- Search-website: α=0.1 (lenient)
- Website-noun: α=0.05 (standard)
- Website-concept: α=0.01-0.03 (aggressive, 80-85% reduction)

---

## LLM Concept Extraction - Key Decisions

### Model Selection

| Model | Cost (per 1M tokens) | Speed | Use Case |
|-------|---------------------|-------|----------|
| **GPT-4o-mini** ✓ | $0.15/$0.60 | 2-5s | Primary (full text) |
| Claude 3 Haiku | $0.25/$1.25 | 2-5s | Fallback #1 |
| **Ollama (llama3.1)** ✓ | **Free** | 10-30s | Fallback #2 (local) |
| Rule-based clustering | Free | 1-2s | Fallback #3 |
| Top nouns | Free | <1s | Fallback #4 (last resort) |

**Decision**: GPT-4o-mini for primary with Ollama as zero-cost local fallback

### Prompt Template (Updated for Full Text)

```python
PROMPT = """You are an expert research assistant. Analyze the full textual content
from this website and distill it into 3-7 high-level conceptual themes.

Guidelines:
- Read and comprehend the entire website content
- Identify overarching themes that capture main topics
- Use clear, academic language
- Concepts should be 2-5 words each
- Focus on substantive topics, not generic web elements
- Look for recurring topics, key arguments, central themes

Content: {website_content}
Language: {language}
Output:
"""
```

### Configuration

```python
# Optimal settings
DEFAULT_MODEL = "gpt-4o-mini"
TEMPERATURE = 0.3  # Low for consistency
MAX_TOKENS = 500
MAX_CONTENT_LENGTH = 120000  # Token limit for full text (~120K)
CHUNK_SIZE = 100000  # For very large websites

# Ollama settings
OLLAMA_ENABLED = True
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1"  # or "mistral", "qwen", etc.

# Summarization settings
ENABLE_SUMMARIZATION = True
SUMMARIZATION_THRESHOLD = 120000  # Tokens
```

### Caching (Updated for Full Text)

```python
# Cache key structure (now based on website and content hash)
content_hash = hashlib.md5(website_content.encode()).hexdigest()
cache_key = f"concept:v2:website:{website_id}:{content_hash}:{model}:{temperature}"

# TTL
CACHE_TTL = 168 hours  # 1 week

# Levels
# L1: Redis (fast, 90%+ hit rate for unchanged content)
# L2: Database (persistent backup)

# Cache invalidation
# Content hash changes when ANY page on website is re-scraped
```

### Rate Limiting

```python
# API limits (OpenAI tier-dependent)
RPM_LIMIT = 10000  # Requests per minute
TPM_LIMIT = 2000000  # Tokens per minute

# User limits
USER_EXTRACTIONS_PER_HOUR = 100
USER_EXTRACTIONS_PER_DAY = 1000
```

### Error Handling (Updated Fallback Chain)

```python
# Retry strategy
MAX_RETRIES = 3
RETRY_DELAY = exponential_backoff(2, 10)

# Fallback chain (5 stages)
1. GPT-4o-mini (primary, confidence=1.0)
2. Claude 3 Haiku (fallback, confidence=0.9)
3. Ollama local LLM (fallback, confidence=0.7, zero cost)
4. Rule-based clustering (fallback, confidence=0.5, extract nouns from content first)
5. Top nouns (last resort, confidence=0.3)

# Ollama availability check
async def check_ollama():
    response = await httpx.get(f"{OLLAMA_BASE_URL}/api/tags")
    return response.status_code == 200
```

---

## Network Backboning - Key Decisions

### Algorithm Selection

| Algorithm | Complexity | Use Case | Speed |
|-----------|-----------|----------|-------|
| **Disparity Filter** ✓ | O(E) | Most networks | Fast |
| Noise-Corrected | O(E × k) | Dense, high-quality | Slower |
| Threshold | O(E) | Simple filtering | Fast |

**Decision**: Disparity filter for statistical rigor and performance

### Algorithm Theory

**Disparity filter tests**: Is this edge weight unusual for this node?

```python
# For edge (i,j) with weight w_ij
α_ij = (1 - w_ij / Σw_i)^(k_i - 1)

# Keep edge if: α_ij < α (significance threshold)
# Where:
#   w_ij = edge weight
#   Σw_i = sum of all edge weights from node i
#   k_i = degree of node i
#   α = significance level (default 0.05)
```

### Default Parameters by Network Type

```python
# Search-website networks (sparse)
SEARCH_WEBSITE_ALPHA = 0.1
SEARCH_WEBSITE_MIN_DEGREE = 1

# Website-noun networks (medium density)
WEBSITE_NOUN_ALPHA = 0.05
WEBSITE_NOUN_MIN_DEGREE = 2

# Website-concept networks (dense)
WEBSITE_CONCEPT_ALPHA = 0.01  # Very strict
WEBSITE_CONCEPT_TARGET_REDUCTION = 0.85  # Remove 85% of edges
WEBSITE_CONCEPT_MIN_DEGREE = 2
```

### Configuration

```python
@dataclass
class BackboningConfig:
    algorithm: str = "disparity_filter"
    alpha: float = 0.05
    threshold: Optional[float] = None
    preserve_disconnected: bool = False
    min_edge_weight: Optional[float] = None
```

### Performance

```python
# Expected performance (single-threaded)
EDGES_1K: "<0.1s"
EDGES_10K: "<1s"
EDGES_100K: "<10s"
EDGES_1M: "<2min"

# Target: <30s for 1000-node network ✓
```

### Validation Metrics

```python
# Quality checks
WEIGHT_CORRELATION: ">0.7"  # High-weight edges preserved
CONNECTIVITY_PRESERVATION: ">0.5"  # Structure maintained
COMMUNITY_SIMILARITY: ">0.5"  # Communities preserved

# Typical reduction
EDGE_REDUCTION: "70-90%"
WEIGHT_RETENTION: "60-80%"
```

---

## API Integration

### Request Schema

```json
{
  "name": "Climate Concepts Network",
  "type": "website_concept",
  "session_ids": [1, 2, 3],
  "backboning": {
    "enabled": true,
    "algorithm": "disparity_filter",
    "alpha": 0.05,
    "target_reduction": 0.8
  },
  "config": {
    "languages": ["da", "en"],
    "llm_model": "gpt-4o-mini",
    "llm_temperature": 0.3
  }
}
```

### Response Schema

```json
{
  "network_id": 123,
  "task_id": "abc-123",
  "status": "completed",
  "metadata": {
    "node_count": 450,
    "edge_count": 1200,
    "original_edge_count": 8000,
    "backboning_applied": true,
    "backboning_algorithm": "disparity_filter",
    "backboning_alpha": 0.05,
    "edge_reduction_percentage": 85.0,
    "weight_retention_percentage": 72.5,
    "concept_extraction": {
      "websites_processed": 150,
      "concepts_extracted": 450,
      "cache_hit_rate": 92.0,
      "avg_concepts_per_website": 3.0,
      "total_cost_usd": 0.21
    }
  },
  "download_url": "/api/network/download/123"
}
```

---

## Database Schema Updates

### Concept Metadata

```sql
ALTER TABLE extracted_concepts
ADD COLUMN model_used VARCHAR(50),
ADD COLUMN temperature FLOAT,
ADD COLUMN token_count INTEGER,
ADD COLUMN processing_time FLOAT,
ADD COLUMN cache_hit BOOLEAN DEFAULT FALSE,
ADD COLUMN quality_score FLOAT,
ADD COLUMN extraction_method VARCHAR(20) DEFAULT 'llm';
```

### Backboning Metadata

```sql
ALTER TABLE network_exports
ADD COLUMN backboning_applied BOOLEAN DEFAULT FALSE,
ADD COLUMN backboning_algorithm VARCHAR(50),
ADD COLUMN backboning_alpha FLOAT,
ADD COLUMN original_edge_count INTEGER,
ADD COLUMN backboning_statistics JSONB;
```

### Cost Tracking

```sql
CREATE TABLE llm_api_usage (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    model VARCHAR(50),
    operation VARCHAR(50),
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd DECIMAL(10, 6),
    success BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Environment Variables

```bash
# LLM Configuration
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEFAULT_LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=500
MAX_CONTENT_LENGTH=120000

# Ollama Configuration (Local LLM)
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
OLLAMA_TIMEOUT=300

# Content Processing
ENABLE_SUMMARIZATION=true
SUMMARIZATION_THRESHOLD_TOKENS=120000
CHUNK_SIZE_TOKENS=100000

# Rate Limiting
LLM_RPM_LIMIT=10000
LLM_TPM_LIMIT=2000000
USER_EXTRACTIONS_PER_HOUR=100
USER_EXTRACTIONS_PER_DAY=1000

# Caching
CONCEPT_CACHE_TTL_HOURS=168
CONCEPT_CACHE_ENABLED=true

# Backboning
BACKBONE_ALPHA=0.05
BACKBONE_ALGORITHM=disparity_filter

# Cost Control
TRACK_LLM_COSTS=true
COST_ALERT_THRESHOLD_USD=100.0

# Fallbacks
ENABLE_OLLAMA_FALLBACK=true
ENABLE_CLUSTERING_FALLBACK=true
ENABLE_NOUN_FALLBACK=true
```

---

## Dependencies

```bash
# Install all required packages
pip install networkx>=3.0 \
    backbone-network>=1.0.0 \
    openai>=1.0.0 \
    anthropic>=0.8.0 \
    tenacity>=8.2.0 \
    tiktoken>=0.5.0 \
    httpx>=0.24.0 \
    sentence-transformers>=2.2.0 \
    scikit-learn>=1.3.0 \
    spacy>=3.6.0 \
    aioredis>=2.0.0

# Install Ollama (optional, for local LLM)
curl https://ollama.ai/install.sh | sh
ollama pull llama3.1
```

---

## Usage Examples

### 1. Basic Concept Extraction (Updated for Full Text)

```python
from app.services import ConceptExtractionService

# Initialize
service = ConceptExtractionService(db, redis, llm_client)

# Extract concepts from website (aggregates all pages automatically)
result = await service.extract_concepts(
    website_id=123,
    user_id=456,
    force_refresh=False  # Use cache if available
)

print(f"Extracted {len(result.concepts)} concepts")
print(f"Pages processed: {result.page_count}")
print(f"Tokens: {result.token_count}")
print(f"Was summarized: {result.was_summarized}")
print(f"Cache hit: {result.cache_hit}")
print(f"Cost: ${result.cost_usd:.4f}")
print(f"Method: {result.extraction_method}")  # 'llm', 'ollama', 'clustering', 'fallback'

for concept in result.concepts:
    print(f"  - {concept.text} (confidence: {concept.confidence})")
```

### 2. Network Generation with Backboning

```python
from app.services import NetworkService
from app.core.network import BackboningConfig

# Configure backboning
backboning = BackboningConfig(
    algorithm="disparity_filter",
    alpha=0.05,
    target_reduction=0.8
)

# Generate network
network = await network_service.generate_network(
    network_type="website_concept",
    session_ids=[1, 2, 3],
    user_id=456,
    backboning_config=backboning
)

print(f"Generated network with {network.node_count} nodes")
print(f"Edge reduction: {network.edge_reduction_percentage}%")
```

### 3. Adaptive Backboning

```python
from app.core.network import AdaptiveBackboner

backboner = AdaptiveBackboner()

# Automatically find alpha to achieve 80% reduction
backboned, stats = await backboner.apply_backboning_with_target(
    graph=original_graph,
    target_reduction=0.8,
    tolerance=0.05
)

print(f"Achieved {stats['reduction_percentage']}% reduction")
print(f"Optimal alpha: {stats['alpha']}")
```

---

## Troubleshooting

### High LLM Costs

```python
# Check cache hit rate
SELECT
    COUNT(*) FILTER (WHERE cache_hit = true) * 100.0 / COUNT(*) as cache_hit_rate
FROM extracted_concepts
WHERE created_at > NOW() - INTERVAL '24 hours';

# Should be >85% after warmup
# If low:
# 1. Check Redis connection
# 2. Verify cache_key generation
# 3. Review TTL settings
```

### Slow Backboning

```python
# Profile backboning
import cProfile

cProfile.run('backboner.apply_backboning(graph)')

# Common issues:
# 1. Very dense graph (>100K edges) → use chunking
# 2. Complex algorithm → switch to disparity filter
# 3. Large graph components → process separately
```

### Poor Concept Quality

```python
# Check quality scores
SELECT
    AVG(quality_score) as avg_quality,
    model_used,
    extraction_method
FROM extracted_concepts
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY model_used, extraction_method;

# If quality <0.7:
# 1. Review prompt template
# 2. Adjust temperature
# 3. Increase top_n_nouns
# 4. Check source noun quality
```

---

## Performance Benchmarks

### LLM Concept Extraction (Full Text Approach)

| Websites | Cache Cold | Cache Warm | Cost (First Run) | Cost (Cached) |
|----------|-----------|------------|------------------|---------------|
| 10 | ~30-50s | ~1s | $0.23 | $0.02 |
| 100 | ~5-8min | ~10s | $2.30 | $0.23 |
| 1000 | ~1-2hr | ~2min | $23.00 | $2.30 |
| 10000 | ~10-20hr | ~20min | $230.00 | $23.00 |

*Note: Assumes mix of typical (15K tokens) and large (100K+ tokens) websites*
*Large websites require summarization, adding processing time*

### Network Backboning

| Edges | Disparity Filter | Noise-Corrected | Threshold |
|-------|-----------------|-----------------|-----------|
| 1K | 0.08s | 0.4s | 0.05s |
| 10K | 0.7s | 4.2s | 0.4s |
| 100K | 8.5s | 52s | 3.8s |
| 1M | 105s | 15min | 42s |

### End-to-End Network Generation

| Websites | Nodes | Edges | Time | Cost |
|----------|-------|-------|------|------|
| 50 | 300 | 2K | <10s | $0.007 |
| 150 | 900 | 8K | ~25s | $0.021 |
| 500 | 2500 | 30K | ~90s | $0.070 |

---

## Monitoring Queries

### LLM Usage

```sql
-- Daily cost by model
SELECT
    DATE(created_at) as date,
    model,
    COUNT(*) as requests,
    SUM(input_tokens) as input_tokens,
    SUM(output_tokens) as output_tokens,
    SUM(cost_usd) as total_cost
FROM llm_api_usage
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at), model
ORDER BY date DESC, total_cost DESC;
```

### Backboning Statistics

```sql
-- Backboning effectiveness
SELECT
    type,
    backboning_algorithm,
    AVG(original_edge_count) as avg_original_edges,
    AVG(edge_count) as avg_backboned_edges,
    AVG((backboning_statistics->>'reduction_percentage')::float) as avg_reduction,
    AVG((backboning_statistics->>'weight_retention_percentage')::float) as avg_weight_retention
FROM network_exports
WHERE backboning_applied = true
  AND created_at > NOW() - INTERVAL '30 days'
GROUP BY type, backboning_algorithm;
```

### Cache Performance

```sql
-- Cache hit rates
SELECT
    DATE(created_at) as date,
    COUNT(*) FILTER (WHERE cache_hit = true) * 100.0 / COUNT(*) as cache_hit_rate,
    AVG(processing_time) as avg_processing_time,
    COUNT(*) as total_extractions
FROM extracted_concepts
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

---

## Best Practices

### LLM Concept Extraction

1. **Always use caching** - 90%+ hit rate saves significant cost
2. **Batch when possible** - Group up to 5 websites per API call
3. **Filter input nouns** - Use TF-IDF to select top 50 nouns
4. **Validate output** - Check for 2-10 concepts, >0.2 relevance
5. **Monitor costs** - Set alerts at $100/day threshold
6. **Use fallbacks** - Implement full fallback chain for reliability

### Network Backboning

1. **Choose appropriate α** - Lower for concept networks, higher for search networks
2. **Validate results** - Check weight correlation >0.7
3. **Consider network type** - Different defaults for different types
4. **Profile performance** - Optimize for your specific network sizes
5. **Test on samples** - Validate on small subset before full processing
6. **Document parameters** - Store backboning config in metadata

---

## FAQ

**Q: Why process full text instead of just noun phrases?**
A: Full text provides complete context, enabling the LLM to understand themes, arguments, and topics holistically. This produces significantly better concept quality than keyword-based extraction, despite higher cost (~165x).

**Q: Why GPT-4o-mini and not GPT-4?**
A: GPT-4o-mini is 95% cheaper ($0.15 vs $30 per 1M tokens) with sufficient quality for concept extraction. GPT-4's extra capability isn't needed for this task. With full text processing, costs are already 165x higher than noun-based approach.

**Q: What is Ollama and why use it?**
A: Ollama runs open-source LLMs locally (llama3.1, mistral, etc.) with zero API costs. It's the third fallback option after GPT-4o-mini and Claude fail. Ideal for high-volume processing or when API budgets are exceeded.

**Q: How do you handle very large websites (>120K tokens)?**
A: Three-stage strategy:
1) <120K tokens: Use directly
2) 120K-500K tokens: Summarize first, then extract concepts
3) >500K tokens: Chunk, summarize each chunk, combine summaries, then extract

**Q: Why disparity filter over simpler threshold?**
A: Disparity filter is statistically principled (p-value based), preserves local structure, and is widely validated in digital methods research. Simple thresholds are arbitrary and can miss important weak edges.

**Q: Can I disable backboning?**
A: Yes, set `backboning.enabled = false` in API request. Note that concept networks without backboning may be very dense (>50K edges).

**Q: How often should cache be warmed?**
A: Run nightly for most-accessed content. Cache TTL of 1 week means content is automatically re-extracted weekly. Content hash changes if ANY page is re-scraped.

**Q: What if OpenAI is down?**
A: System automatically falls back through 5 stages: GPT-4o-mini → Claude Haiku → Ollama (local) → Clustering → Top nouns. Service continues with degraded quality but zero downtime.

**Q: How to reduce LLM costs?**
A: 1) Use Ollama for high volumes (zero API cost), 2) Increase cache TTL, 3) Enable aggressive caching, 4) Process only changed websites, 5) Use simpler noun-based extraction for less critical analyses, 6) Set up Ollama on dedicated inference server.

---

## Support & Documentation

- **Full Specifications**:
  - `LLM_CONCEPT_EXTRACTION_SPECIFICATION.md` (60+ pages)
  - `NETWORK_BACKBONING_SPECIFICATION.md` (50+ pages)
- **Implementation Guide**: `IMPLEMENTATION_ROADMAP.md`
- **Code Examples**: See specifications for complete implementations
- **Testing**: Comprehensive test suites provided in specifications

---

## Version History

- **v1.0** (2025-10-22): Initial specifications
  - LLM concept extraction with GPT-4o-mini
  - Disparity filter backboning
  - Caching, rate limiting, error handling
  - Full API integration
  - Complete implementation roadmap
