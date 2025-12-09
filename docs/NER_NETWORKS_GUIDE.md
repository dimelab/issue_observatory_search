# Named Entity Recognition (NER) Networks Guide

**Version**: 6.0.0
**Last Updated**: December 9, 2025

---

## Overview

Issue Observatory Search v6.0.0 introduces **Website → Named Entity** networks, a new network type that maps relationships between websites and the entities (people, organizations, locations, etc.) they discuss. This guide explains how to create, configure, and analyze NER networks.

---

## Table of Contents

1. [What are NER Networks?](#what-are-ner-networks)
2. [Entity Types](#entity-types)
3. [Extraction Methods](#extraction-methods)
4. [Creating NER Networks](#creating-ner-networks)
5. [Configuration Parameters](#configuration-parameters)
6. [Use Cases](#use-cases)
7. [Multilingual Support](#multilingual-support)
8. [Performance Considerations](#performance-considerations)
9. [Analysis Techniques](#analysis-techniques)
10. [Troubleshooting](#troubleshooting)

---

## What are NER Networks?

### Network Structure

NER networks are **bipartite graphs** with two node types:

1. **Website nodes**: Represent source websites or URLs
2. **Entity nodes**: Represent named entities mentioned in the content

**Edges**: Connect websites to entities they mention, weighted by:
- Entity frequency (how often mentioned)
- Entity confidence score (extraction confidence)
- Aggregated counts (if multiple pages from same domain)

### Example Network

```
[Website: nytimes.com] ──5──> [PERSON: Joe Biden]
                      ──3──> [ORG: United Nations]
                      ──2──> [LOC: Washington]

[Website: bbc.com]     ──4──> [PERSON: Joe Biden]
                      ──6──> [ORG: European Union]
                      ──1──> [LOC: London]
```

This reveals:
- Shared entities across sources (Joe Biden mentioned by both)
- Source specialization (BBC focuses on EU, NYT on UN)
- Geographic focus differences

---

## Entity Types

### Standard Entity Types (spaCy)

| Type | Description | Examples |
|------|-------------|----------|
| **PERSON** | People, including fictional | "Angela Merkel", "Harry Potter" |
| **ORG** | Organizations, companies, institutions | "Microsoft", "United Nations", "Harvard" |
| **GPE** | Geo-political entities (countries, cities, states) | "Germany", "New York", "California" |
| **LOC** | Non-GPE locations (mountains, bodies of water) | "Mount Everest", "Pacific Ocean" |
| **DATE** | Dates or periods | "2023", "last Monday", "the 90s" |
| **TIME** | Times smaller than a day | "3pm", "morning" |
| **MONEY** | Monetary values | "$1 million", "€50" |
| **PERCENT** | Percentages | "50%", "three quarters" |
| **FACILITY** | Buildings, airports, highways, bridges | "JFK Airport", "Golden Gate Bridge" |
| **PRODUCT** | Objects, vehicles, foods (not services) | "iPhone", "Tesla Model 3" |
| **EVENT** | Named events | "World War II", "Olympics" |
| **LAW** | Named laws | "GDPR", "Affordable Care Act" |
| **LANGUAGE** | Named languages | "English", "Mandarin" |
| **WORK_OF_ART** | Titles of books, songs, etc. | "Mona Lisa", "Harry Potter" |

### Recommended Entity Types for Networks

For most network analyses, focus on:

**Core Types** (always useful):
- `PERSON`: Key actors and individuals
- `ORG`: Organizations and institutions
- `GPE`: Geographic focus

**Extended Types** (add for specific domains):
- `LOC`: Non-political geographic features
- `EVENT`: Historical or current events
- `PRODUCT`: For technology/business analysis
- `LAW`: For policy/legal analysis

**Generally Skip**:
- `DATE`, `TIME`, `MONEY`, `PERCENT`: Too generic for network analysis
- `LANGUAGE`, `WORK_OF_ART`: Rarely useful for topical networks

---

## Extraction Methods

### 1. spaCy NER (`spacy`)

**Description**: Fast, accurate named entity recognition using spaCy's pre-trained models.

**Technology**:
- Statistical models trained on large corpora
- Language-specific models (en_core_web_sm, da_core_news_sm)
- CPU-efficient

**Pros**:
- ✅ Very fast (50-100ms per document)
- ✅ Low memory footprint
- ✅ High accuracy for common entities
- ✅ Supports English and Danish
- ✅ No additional dependencies

**Cons**:
- ❌ May miss domain-specific entities
- ❌ Less accurate on technical/specialized text
- ❌ Fixed entity types (can't add custom categories)

**Best For**:
- General news and web content
- Large-scale analysis (>1000 documents)
- When speed is priority
- English and Danish content

**Example Output**:
```json
[
  {"text": "Angela Merkel", "label": "PERSON", "confidence": 0.98},
  {"text": "European Union", "label": "ORG", "confidence": 0.95},
  {"text": "Germany", "label": "GPE", "confidence": 0.99}
]
```

---

### 2. Transformer NER (`transformer`)

**Description**: State-of-the-art multilingual NER using transformer models (XLM-RoBERTa).

**Technology**:
- Pre-trained on 100+ languages
- Model: `Davlan/xlm-roberta-base-ner-hrl`
- Deep learning architecture
- GPU-accelerated (optional)

**Pros**:
- ✅ Superior accuracy, especially on technical text
- ✅ Multilingual (10+ languages)
- ✅ Better at rare/unusual entity names
- ✅ Handles domain-specific terminology
- ✅ Cross-lingual consistency

**Cons**:
- ❌ 5-10x slower than spaCy
- ❌ Requires ~2GB additional disk space
- ❌ Higher memory usage (~500MB RAM)
- ❌ May require GPU for large batches

**Best For**:
- Technical/scientific content
- Multilingual corpora
- When accuracy is critical
- Domain-specific analysis
- Small-to-medium scale (<500 documents)

**Performance**:
- CPU: ~500ms per document
- GPU: ~100ms per document

**Example Output**:
```json
[
  {"text": "CRISPR-Cas9", "label": "MISC", "confidence": 0.92},
  {"text": "Jennifer Doudna", "label": "PER", "confidence": 0.96},
  {"text": "UC Berkeley", "label": "ORG", "confidence": 0.94}
]
```

---

## Creating NER Networks

### Basic Network Creation

```bash
POST /api/networks/generate

{
  "name": "Climate Policy Actors Network",
  "type": "website_ner",
  "session_ids": [1, 2, 3],
  "ner_config": {
    "extraction_method": "spacy",
    "entity_types": ["PERSON", "ORG", "GPE"],
    "confidence_threshold": 0.85,
    "max_entities_per_content": 100
  },
  "aggregate_by_domain": true
}
```

**Returns**:
```json
{
  "task_id": "abc123...",
  "status": "pending",
  "message": "Network generation started"
}
```

### Advanced Configuration

```bash
POST /api/networks/generate

{
  "name": "Scientific Collaboration Network",
  "type": "website_ner",
  "session_ids": [5, 6],
  "ner_config": {
    "extraction_method": "transformer",
    "entity_types": ["PERSON", "ORG"],
    "confidence_threshold": 0.90,
    "max_entities_per_content": 50
  },
  "aggregate_by_domain": false,
  "backboning": {
    "enabled": true,
    "algorithm": "disparity_filter",
    "alpha": 0.05
  }
}
```

---

## Configuration Parameters

### NERExtractionConfig

```python
class NERExtractionConfig:
    extraction_method: str                    # "spacy" or "transformer"
    entity_types: List[str]                   # Entity types to extract
    confidence_threshold: float               # Minimum confidence (0.0-1.0)
    max_entities_per_content: int             # Max entities per document
```

### Parameter Details

#### `extraction_method`

- **Type**: `"spacy"` | `"transformer"`
- **Default**: `"spacy"`
- **Description**: NER algorithm to use

**Recommendation**:
- Use `"spacy"` for general content and speed
- Use `"transformer"` for technical content and accuracy

---

#### `entity_types`

- **Type**: `List[str]`
- **Default**: `["PERSON", "ORG", "GPE", "LOC"]`
- **Valid Values**: See [Entity Types](#entity-types) section

**Examples**:

Political networks:
```json
["PERSON", "ORG", "GPE"]
```

Geographic focus:
```json
["GPE", "LOC", "FACILITY"]
```

Event-based analysis:
```json
["EVENT", "PERSON", "ORG", "GPE"]
```

---

#### `confidence_threshold`

- **Type**: `float`
- **Range**: `0.0` - `1.0`
- **Default**: `0.85`
- **Description**: Minimum confidence score to include entity

**Tuning Guide**:

| Threshold | Effect | Use When |
|-----------|--------|----------|
| 0.70-0.80 | More entities, more noise | Exploratory analysis |
| 0.80-0.90 | Balanced precision/recall | General use (**recommended**) |
| 0.90-0.95 | High precision, fewer entities | When accuracy critical |
| 0.95-1.00 | Very strict, may miss entities | Only for validation |

---

#### `max_entities_per_content`

- **Type**: `int`
- **Range**: `1` - `500`
- **Default**: `100`
- **Description**: Maximum entities to extract per document

**Tuning Guide**:

| Value | Effect | Use When |
|-------|--------|----------|
| 20-50 | Top entities only | Large networks, focus on key actors |
| 50-100 | Balanced coverage | General use (**recommended**) |
| 100-200 | Comprehensive extraction | Small networks, detailed analysis |
| 200+ | Extract all | Research, complete entity catalogs |

---

## Use Cases

### Use Case 1: Political Actor Mapping

**Goal**: Map which politicians and organizations are mentioned together across news sources

**Configuration**:
```json
{
  "extraction_method": "spacy",
  "entity_types": ["PERSON", "ORG", "GPE"],
  "confidence_threshold": 0.85,
  "max_entities_per_content": 80
}
```

**Analysis Questions**:
- Which politicians are most frequently mentioned?
- Which organizations appear across multiple sources?
- Are there source biases in entity coverage?

**Example Insights**:
- Liberal sources mention different politicians than conservative sources
- International orgs (UN, WHO) appear in global news, national orgs in local news

---

### Use Case 2: Scientific Collaboration Networks

**Goal**: Identify researchers and institutions in a research field

**Configuration**:
```json
{
  "extraction_method": "transformer",
  "entity_types": ["PERSON", "ORG"],
  "confidence_threshold": 0.90,
  "max_entities_per_content": 100
}
```

**Why Transformer**:
- Better at recognizing unusual names
- Handles institutional abbreviations (MIT, CERN, etc.)
- More accurate on technical content

**Analysis Questions**:
- Who are the key researchers?
- Which institutions are most prominent?
- Are there emerging research clusters?

---

### Use Case 3: Corporate Network Analysis

**Goal**: Map relationships between companies and executives mentioned in business news

**Configuration**:
```json
{
  "extraction_method": "spacy",
  "entity_types": ["PERSON", "ORG", "PRODUCT"],
  "confidence_threshold": 0.85,
  "max_entities_per_content": 60
}
```

**Analysis Questions**:
- Which executives are associated with which companies?
- How are products linked to organizations?
- Are there merger/acquisition patterns in mentions?

---

### Use Case 4: Geographic Event Mapping

**Goal**: Understand where events are happening and what locations are connected

**Configuration**:
```json
{
  "extraction_method": "spacy",
  "entity_types": ["GPE", "LOC", "EVENT", "ORG"],
  "confidence_threshold": 0.85,
  "max_entities_per_content": 100
}
```

**Analysis Questions**:
- Which locations are most frequently mentioned?
- How are events distributed geographically?
- Which organizations operate in which locations?

---

## Multilingual Support

### Supported Languages

#### spaCy Method

| Language | Model | Quality | Notes |
|----------|-------|---------|-------|
| English | `en_core_web_sm` | ⭐⭐⭐⭐⭐ | Best supported |
| Danish | `da_core_news_sm` | ⭐⭐⭐⭐ | Good accuracy |

#### Transformer Method

| Language | Quality | Notes |
|----------|---------|-------|
| English | ⭐⭐⭐⭐⭐ | Excellent |
| Danish | ⭐⭐⭐⭐⭐ | Excellent |
| German | ⭐⭐⭐⭐⭐ | Excellent |
| French | ⭐⭐⭐⭐⭐ | Excellent |
| Spanish | ⭐⭐⭐⭐⭐ | Excellent |
| + 95 more languages | ⭐⭐⭐⭐ | Good to excellent |

### Language Detection

The system automatically detects language from website content. You can also specify language explicitly in search sessions.

### Cross-Lingual Analysis

**Example**: Analyzing both English and Danish climate news

```json
{
  "extraction_method": "transformer",
  "entity_types": ["PERSON", "ORG", "GPE"],
  "confidence_threshold": 0.85,
  "max_entities_per_content": 100
}
```

**Benefits of Transformer**:
- Consistent entity recognition across languages
- Same entity (e.g., "Angela Merkel" vs "Angela Merkel") properly matched
- Better handling of transliterated names

---

## Performance Considerations

### Extraction Speed

#### spaCy Method

| Documents | CPU Time | GPU Time |
|-----------|----------|----------|
| 10 | 1s | N/A (CPU-only) |
| 100 | 8s | N/A |
| 1000 | 80s | N/A |

#### Transformer Method

| Documents | CPU Time | GPU Time |
|-----------|----------|----------|
| 10 | 5s | 1s |
| 100 | 50s | 8s |
| 1000 | 8m | 80s |

### Memory Requirements

| Method | RAM per Document | Total RAM (1000 docs) |
|--------|------------------|-----------------------|
| spaCy | ~50MB | ~2GB |
| Transformer (CPU) | ~500MB | ~10GB |
| Transformer (GPU) | ~200MB + 2GB VRAM | ~5GB + 2GB VRAM |

### Network Size

Typical NER networks are **denser** than keyword networks:

| Documents | Entities | Edges | File Size |
|-----------|----------|-------|-----------|
| 100 | 200-500 | 2000-5000 | 500KB-1MB |
| 500 | 500-1500 | 10K-30K | 2-5MB |
| 1000 | 1000-3000 | 30K-80K | 5-15MB |

### Optimization Tips

1. **Use spaCy for large scale**: 5-10x faster, same accuracy for general content

2. **Batch processing**: Process multiple documents together (automatic)

3. **Filter entity types**: Only extract needed types to reduce network size

4. **Adjust confidence threshold**: Higher threshold = fewer entities = smaller network

5. **Use GPU for transformer**: 5x speed improvement for large batches

6. **Apply backboning**: Reduce network complexity while preserving structure

---

## Analysis Techniques

### 1. Entity Centrality Analysis

**Question**: Which entities are most central to the discourse?

**Method**:
- Calculate degree centrality (how many websites mention entity)
- Calculate betweenness centrality (bridge between website clusters)

**Interpretation**:
- High degree = widely discussed entity
- High betweenness = entity connecting different topics/sources

---

### 2. Source Similarity by Shared Entities

**Question**: Which sources discuss similar entities?

**Method**:
- Project bipartite network to website-website network
- Edge weight = number of shared entities
- Cluster websites by similarity

**Interpretation**:
- Clusters reveal source communities
- Shared entities indicate topical overlap

---

### 3. Entity Co-occurrence Patterns

**Question**: Which entities appear together?

**Method**:
- Project bipartite network to entity-entity network
- Edge weight = number of websites mentioning both
- Identify entity clusters

**Interpretation**:
- Clusters reveal entity relationships
- Central entities in clusters are key actors

---

### 4. Temporal Entity Evolution

**Question**: How do entity mentions change over time?

**Method**:
- Create separate networks for time periods
- Track entity appearance/disappearance
- Measure centrality changes

**Interpretation**:
- Emerging entities = new topics/actors
- Declining entities = fading relevance

---

### 5. Cross-Source Entity Comparison

**Question**: Do different sources emphasize different entities?

**Method**:
- Group websites by source type (e.g., liberal vs conservative)
- Compare entity frequencies between groups
- Identify unique vs shared entities

**Interpretation**:
- Unique entities = source bias
- Shared entities = common ground

---

## Troubleshooting

### Problem: Too few entities extracted

**Possible Causes**:
- `confidence_threshold` too high
- Wrong `entity_types` selected
- Content has few named entities (e.g., abstract/theoretical text)

**Solutions**:
1. Lower `confidence_threshold` to 0.75-0.80
2. Add more entity types (e.g., `LOC`, `EVENT`)
3. Check if content is suitable for NER (factual > theoretical)
4. Try `transformer` method for better recall

---

### Problem: Too many generic/incorrect entities

**Possible Causes**:
- `confidence_threshold` too low
- Including noisy entity types (DATE, TIME, MONEY)
- Method not suitable for content type

**Solutions**:
1. Increase `confidence_threshold` to 0.90-0.95
2. Remove generic types: exclude `DATE`, `TIME`, `MONEY`, `PERCENT`
3. Use `transformer` for technical content
4. Reduce `max_entities_per_content`

---

### Problem: Slow extraction

**Possible Causes**:
- Using `transformer` method on CPU
- Large corpus size
- High `max_entities_per_content`

**Solutions**:
1. Switch to `spacy` method (5-10x faster)
2. Use batch processing (automatic)
3. Enable GPU for transformer method
4. Reduce `max_entities_per_content` to 50

---

### Problem: Multilingual entity mismatch

**Example**: "Angela Merkel" and "Ангела Меркель" treated as different entities

**Possible Causes**:
- Using `spacy` method (language-specific models)
- Different entity spellings/transliterations

**Solutions**:
1. Use `transformer` method (better cross-lingual consistency)
2. Post-process to normalize entity names
3. Use language-specific networks separately

---

### Problem: Missing domain-specific entities

**Example**: Technical terms, product names not recognized

**Possible Causes**:
- Using `spacy` (trained on general text)
- Entity doesn't fit standard categories

**Solutions**:
1. Switch to `transformer` method
2. Add `MISC` category to `entity_types`
3. Consider custom NER training (advanced)

---

## Best Practices

1. **Start with spaCy**: Faster and good enough for most use cases

2. **Focus entity types**: Only extract types relevant to your analysis

3. **Test confidence thresholds**: Use preview endpoint to find optimal threshold

4. **Consider corpus size**: spaCy for >500 docs, transformer for <500

5. **Use domain aggregation**: Aggregate by domain to reduce network complexity

6. **Apply backboning**: Essential for large NER networks (often very dense)

7. **Validate entities**: Manually check sample outputs to tune parameters

8. **Document configuration**: Record exact settings for reproducibility

9. **Compare methods**: Test both spaCy and transformer on sample to choose

10. **Monitor performance**: Track extraction time and adjust if needed

---

## Comparison with Keyword Networks

| Aspect | Keyword Networks | NER Networks |
|--------|------------------|--------------|
| **Focus** | Topics and concepts | Actors and places |
| **Node Types** | Websites → Keywords | Websites → Entities |
| **Density** | Medium | High (more entities per doc) |
| **Analysis** | Topical clustering | Actor relationships |
| **Speed** | Fast | Medium (spaCy) to Slow (transformer) |
| **Best For** | Content themes | Who/where analysis |

**Recommendation**: Use both types together for comprehensive analysis!

---

## Further Reading

- [Keyword Extraction Guide](KEYWORD_EXTRACTION_GUIDE.md)
- Phase 5 Documentation: API Updates
- Phase 6 Documentation: Service Layer
- Network Analysis Techniques
- spaCy NER Documentation
- Transformers NER Models

---

**Questions or Issues?**

Refer to the troubleshooting section or main documentation. For advanced configurations, consult the API reference.
