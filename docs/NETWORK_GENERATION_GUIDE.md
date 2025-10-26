# Network Generation - Quick Reference Guide

## Quick Start

### 1. Generate a Search-Website Network

```python
from backend.services.network_service import NetworkService
from backend.schemas.network import NetworkBackboningConfig

async with async_session() as session:
    service = NetworkService(session)

    network = await service.generate_search_website_network(
        user_id=1,
        name="My Research Network",
        session_ids=[1, 2, 3],
        weight_method="inverse_rank",
        aggregate_by_domain=True,
        backboning_config=NetworkBackboningConfig(
            enabled=True,
            algorithm="disparity_filter",
            alpha=0.05
        )
    )

    print(f"Network ID: {network.id}")
    print(f"Nodes: {network.node_count}, Edges: {network.edge_count}")
    print(f"Download: /api/networks/{network.id}/download")
```

### 2. Generate a Website-Noun Network

```python
network = await service.generate_website_noun_network(
    user_id=1,
    name="Climate Discourse Network",
    session_ids=[1, 2, 3],
    top_n_nouns=50,
    languages=["en", "da"],  # English + Danish
    min_tfidf_score=0.01,
    aggregate_by_domain=True,
    backboning_config=NetworkBackboningConfig(
        enabled=True,
        algorithm="disparity_filter",
        alpha=0.05
    )
)
```

### 3. Generate via API (Async)

```bash
curl -X POST http://localhost:8000/api/networks/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Climate Network",
    "type": "search_website",
    "session_ids": [1, 2, 3],
    "backboning": {
      "enabled": true,
      "algorithm": "disparity_filter",
      "alpha": 0.05
    }
  }'
```

---

## Network Types

### search_website
- **Nodes:** Search queries + Websites
- **Edges:** Query found website at rank X
- **Weights:** Based on search ranking
- **Use case:** Map search engine results, analyze query-website associations

### website_noun
- **Nodes:** Websites + Nouns (from NLP)
- **Edges:** Website contains noun with TF-IDF score
- **Weights:** TF-IDF scores
- **Use case:** Discourse analysis, vocabulary mapping, issue framing

### website_concept (Coming in Phase 7)
- **Nodes:** Websites + Concepts (from LLM)
- **Edges:** Website discusses concept
- **Weights:** Relevance scores
- **Use case:** High-level thematic analysis

---

## Backboning Algorithms

### Disparity Filter (Recommended)
```python
NetworkBackboningConfig(
    enabled=True,
    algorithm="disparity_filter",
    alpha=0.05,  # Significance level (0.01-0.1)
    min_edge_weight=0.01  # Optional threshold
)
```
- **Best for:** Statistical significance-based filtering
- **Preserves:** Locally significant edges
- **Speed:** Fast for <10k nodes

### Threshold Filter
```python
NetworkBackboningConfig(
    enabled=True,
    algorithm="threshold",
    threshold=0.5  # Minimum edge weight
)
```
- **Best for:** Simple weight cutoff
- **Speed:** Very fast

### Top-K Filter
```python
NetworkBackboningConfig(
    enabled=True,
    algorithm="top_k",
    k=1000  # Keep top 1000 edges
)
```
- **Best for:** Fixed-size networks
- **Speed:** Very fast

---

## Configuration Options

### Search-Website Networks

```python
{
    "weight_method": "inverse_rank",  # or "exponential_decay", "fixed"
    "aggregate_by_domain": True,  # Group URLs by domain
}
```

**Weight Methods:**
- `inverse_rank`: 1/rank (rank 1 = 1.0, rank 10 = 0.1)
- `exponential_decay`: exp(-rank/10) - smoother decay
- `fixed`: All edges weight 1.0

### Website-Noun Networks

```python
{
    "top_n_nouns": 50,  # Top N nouns per website
    "languages": ["en", "da"],  # Filter by language (None = all)
    "min_tfidf_score": 0.01,  # Minimum TF-IDF threshold
    "aggregate_by_domain": True,  # Aggregate by domain
}
```

---

## API Endpoints Reference

### POST /api/networks/generate
Generate a new network (async)

**Request:**
```json
{
  "name": "Network Name",
  "type": "search_website",
  "session_ids": [1, 2, 3],
  "top_n_nouns": 50,
  "languages": ["en"],
  "min_tfidf_score": 0.01,
  "aggregate_by_domain": true,
  "weight_method": "inverse_rank",
  "backboning": {
    "enabled": true,
    "algorithm": "disparity_filter",
    "alpha": 0.05
  }
}
```

**Response:** 202 Accepted
```json
{
  "task_id": "abc-123-def",
  "status": "pending",
  "message": "Network generation started..."
}
```

### GET /api/networks
List user's networks

**Parameters:**
- `page` (int, default 1): Page number
- `per_page` (int, default 20): Results per page
- `type` (string, optional): Filter by network type
- `session_id` (int, optional): Filter by session

**Response:** 200 OK
```json
{
  "total": 42,
  "page": 1,
  "per_page": 20,
  "networks": [...]
}
```

### GET /api/networks/{id}
Get network details

**Response:** 200 OK
```json
{
  "id": 1,
  "user_id": 1,
  "name": "Climate Network",
  "type": "search_website",
  "session_ids": [1, 2, 3],
  "file_path": "/data/networks/1/network_123.gexf",
  "file_size": 250000,
  "node_count": 1000,
  "edge_count": 2500,
  "backboning_applied": true,
  "backboning_algorithm": "disparity_filter",
  "backboning_alpha": 0.05,
  "original_edge_count": 5000,
  "backboning_statistics": {
    "edge_retention_rate": 0.5,
    "nodes_removed": 50
  },
  "metadata": {...},
  "created_at": "2025-10-24T12:00:00Z"
}
```

### GET /api/networks/{id}/download
Download GEXF file

**Response:** 200 OK (application/xml)
- Downloads GEXF file for Gephi

### GET /api/networks/{id}/statistics
Get detailed graph statistics

**Response:** 200 OK
```json
{
  "node_count": 1000,
  "edge_count": 2500,
  "density": 0.025,
  "avg_degree": 5.0,
  "min_degree": 1,
  "max_degree": 150,
  "node_types": {
    "query": 100,
    "website": 900
  },
  "connected_components": 1,
  "largest_component_size": 1000,
  "avg_weight": 0.35,
  "min_weight": 0.01,
  "max_weight": 1.0
}
```

### DELETE /api/networks/{id}
Delete network

**Response:** 204 No Content

---

## Gephi Workflow

### 1. Generate & Download
```bash
# Generate network
curl -X POST http://localhost:8000/api/networks/generate \
  -H "Authorization: Bearer $TOKEN" \
  -d '{...}' > task.json

# Wait for completion (check task status)

# Download GEXF
curl http://localhost:8000/api/networks/42/download \
  -H "Authorization: Bearer $TOKEN" \
  -o network.gexf
```

### 2. Open in Gephi
1. **File → Open** → Select `network.gexf`
2. **Import options:**
   - Graph type: Undirected
   - Import as: New workspace

### 3. Apply Layout
**For bipartite networks:**
1. **Layout → ForceAtlas 2**
2. Settings:
   - Scaling: 2.0
   - Prevent Overlap: ✓
   - LinLog mode: ✓ (for bipartite)
   - Gravity: 1.0
3. **Run** until stabilized (1-2 minutes)

**Alternative layouts:**
- **Fruchterman Reingold:** Good for small networks
- **Yifan Hu:** Fast, good for medium networks
- **OpenOrd:** Best for large networks (>5000 nodes)

### 4. Style Nodes
**Colors** (pre-configured):
- Queries: Blue
- Websites: Green
- Nouns: Orange

**Sizes** (pre-configured by degree):
- Already scaled 10-100
- Optional: Appearance → Nodes → Ranking → Degree

### 5. Filter Network
**Filters panel:**
1. **Topology → Degree Range**
   - Min: 2 (remove isolates)
   - Max: 1000

2. **Attributes → Range → weight**
   - Min: 0.1 (keep high-weight edges)

3. **Attributes → Partition → node_type**
   - Select specific types

### 6. Export Visualization
1. **Preview** tab
   - Preset: Default
   - Show labels: For nodes with degree > 10
2. **Export:**
   - SVG: Vector (scalable)
   - PNG: Raster (fixed size)
   - PDF: Print-ready

---

## Common Patterns

### Pattern 1: Compare Multiple Query Sets
```python
# Generate separate networks for different time periods
network_2023 = await service.generate_search_website_network(
    name="Climate 2023",
    session_ids=[1, 2, 3]
)

network_2024 = await service.generate_search_website_network(
    name="Climate 2024",
    session_ids=[4, 5, 6]
)

# Compare in Gephi side-by-side
```

### Pattern 2: Multi-Language Discourse Analysis
```python
# Generate separate networks per language
network_en = await service.generate_website_noun_network(
    name="Climate Discourse (English)",
    languages=["en"],
    top_n_nouns=100
)

network_da = await service.generate_website_noun_network(
    name="Climate Discourse (Danish)",
    languages=["da"],
    top_n_nouns=100
)
```

### Pattern 3: Progressive Backboning
```python
# Generate with different alpha values
for alpha in [0.01, 0.05, 0.1]:
    network = await service.generate_search_website_network(
        name=f"Network (alpha={alpha})",
        session_ids=[1, 2, 3],
        backboning_config=NetworkBackboningConfig(
            enabled=True,
            alpha=alpha
        )
    )
```

### Pattern 4: Domain vs URL Analysis
```python
# Domain-level (institutional analysis)
network_domains = await service.generate_search_website_network(
    name="Institutional Network",
    aggregate_by_domain=True
)

# URL-level (page-specific analysis)
network_urls = await service.generate_search_website_network(
    name="Page-Level Network",
    aggregate_by_domain=False
)
```

---

## Performance Tips

### 1. Use Backboning for Large Networks
```python
# Without backboning: 10,000 edges
# With backboning (α=0.05): ~2,500 edges (75% reduction)
backboning_config=NetworkBackboningConfig(
    enabled=True,
    algorithm="disparity_filter",
    alpha=0.05
)
```

### 2. Limit Nouns per Website
```python
# Instead of all nouns (slow)
top_n_nouns=1000

# Use reasonable limit (fast)
top_n_nouns=50
```

### 3. Filter by Language
```python
# All languages (slower, mixed results)
languages=None

# Specific languages (faster, cleaner)
languages=["en", "da"]
```

### 4. Aggregate by Domain
```python
# URLs (many nodes, complex)
aggregate_by_domain=False

# Domains (fewer nodes, clearer structure)
aggregate_by_domain=True
```

### 5. Monitor Task Progress
```python
# Check Celery task status
from backend.celery_app import celery_app

task = celery_app.AsyncResult(task_id)
print(task.state)  # PENDING, PROGRESS, SUCCESS, FAILURE
print(task.info)   # Progress details
```

---

## Troubleshooting

### Network has no nodes
**Cause:** No data in specified sessions
**Solution:** Check session IDs, verify scraping/analysis completed

### Generation takes too long (>30s)
**Cause:** Large network or complex queries
**Solutions:**
1. Enable backboning
2. Reduce top_n_nouns
3. Filter by language
4. Aggregate by domain

### File not found on download
**Cause:** Network file deleted or corrupted
**Solution:** Regenerate network

### Backboning removes too many edges
**Cause:** Alpha too low
**Solution:** Increase alpha (try 0.1 or 0.2)

### Out of memory error
**Cause:** Network too large
**Solutions:**
1. Reduce sessions
2. Enable aggressive backboning
3. Set network_max_nodes/edges lower

---

## Best Practices

### 1. Name Networks Descriptively
```python
# Bad
name="Network1"

# Good
name="Climate_Search_EN_2024_Q1"
```

### 2. Use Backboning by Default
```python
# Always enable for networks >500 edges
backboning_config=NetworkBackboningConfig(enabled=True)
```

### 3. Document Configuration
```python
# Store metadata about your research design
metadata = {
    "research_question": "...",
    "query_strategy": "...",
    "date_range": "2024-01-01 to 2024-03-31"
}
```

### 4. Version Control Networks
```python
# Use descriptive names with versions
name="Climate_Network_v1.0"
name="Climate_Network_v2.0_with_backboning"
```

### 5. Clean Up Old Networks
```python
# Run periodic cleanup
await service.cleanup_old_networks(days=30)
```

---

## References

### Academic
- **Serrano et al. (2009):** Disparity filter algorithm
- **Richard Rogers:** Digital Methods for Internet Research
- **Venturini et al.:** Issue Mapping methodology

### Documentation
- NetworkX: https://networkx.org/
- Gephi: https://gephi.org/
- GEXF Format: https://gexf.net/

### Code
- Network builders: `backend/core/networks/`
- API endpoints: `backend/api/networks.py`
- Service: `backend/services/network_service.py`
- Tasks: `backend/tasks/network_tasks.py`

---

**Last Updated:** October 24, 2025
**Version:** 1.0.0
