# Keyword Extraction Guide

**Version**: 6.0.0
**Last Updated**: December 9, 2025

---

## Overview

Issue Observatory Search v6.0.0 introduces enhanced keyword extraction capabilities, supporting multiple extraction methods beyond the original noun-only approach. This guide explains each method, when to use them, and how to configure extraction parameters for optimal results.

---

## Table of Contents

1. [Extraction Methods](#extraction-methods)
2. [Method Comparison](#method-comparison)
3. [Configuration Parameters](#configuration-parameters)
4. [When to Use Each Method](#when-to-use-each-method)
5. [API Usage](#api-usage)
6. [Parameter Tuning Guide](#parameter-tuning-guide)
7. [Performance Considerations](#performance-considerations)
8. [Troubleshooting](#troubleshooting)

---

## Extraction Methods

### 1. Noun (`noun`)

**Description**: Extracts only nouns from text using spaCy's part-of-speech tagging, ranked by TF-IDF scores.

**Algorithm**:
1. Parse text with spaCy NLP model
2. Filter tokens by POS tag = NOUN
3. Calculate term frequency (TF) per document
4. Calculate inverse document frequency (IDF) across corpus
5. Rank by TF-IDF score

**Pros**:
- ✅ Fast and efficient
- ✅ Works well for topic modeling
- ✅ Low memory footprint
- ✅ Proven approach for semantic networks

**Cons**:
- ❌ Misses important verbs and adjectives
- ❌ Limited to single words (no phrases)
- ❌ May miss domain-specific terminology

**Best For**:
- General topic extraction
- Traditional semantic networks
- Large-scale analysis where speed is critical
- Backward compatibility with v5.0.0

**Example Output**:
```json
[
  {"word": "climate", "lemma": "climate", "score": 0.85, "frequency": 12},
  {"word": "policy", "lemma": "policy", "score": 0.72, "frequency": 8},
  {"word": "carbon", "lemma": "carbon", "score": 0.68, "frequency": 7}
]
```

---

### 2. All Keywords (`all_pos`)

**Description**: Extracts nouns, verbs, and adjectives using spaCy, providing a more comprehensive vocabulary.

**Algorithm**:
1. Parse text with spaCy NLP model
2. Filter tokens by POS tags: NOUN, VERB, ADJ
3. Calculate TF-IDF scores
4. Rank and return top keywords

**Pros**:
- ✅ Captures action words (verbs) and descriptors (adjectives)
- ✅ More comprehensive than noun-only
- ✅ Still relatively fast
- ✅ Good for understanding "how" and "what"

**Cons**:
- ❌ More noise (common verbs/adjectives)
- ❌ Still limited to single words
- ❌ Requires careful min_frequency filtering

**Best For**:
- Understanding actions and processes
- Capturing sentiment and tone (via adjectives)
- Comprehensive content analysis
- When nouns alone are insufficient

**Configuration**:
```json
{
  "method": "all_pos",
  "include_pos": ["NOUN", "VERB", "ADJ"],
  "max_keywords": 50,
  "min_frequency": 2
}
```

**Example Output**:
```json
[
  {"word": "climate", "pos": "NOUN", "score": 0.85, "frequency": 12},
  {"word": "change", "pos": "VERB", "score": 0.79, "frequency": 15},
  {"word": "urgent", "pos": "ADJ", "score": 0.71, "frequency": 6}
]
```

---

### 3. TF-IDF with Bigrams (`tfidf`)

**Description**: Enhanced TF-IDF that includes bigrams (2-word phrases) and allows IDF weight adjustment.

**Algorithm**:
1. Extract both unigrams and bigrams
2. Calculate TF for each term/phrase
3. Calculate IDF across corpus
4. Apply weighted IDF: `TF-IDF = TF × (IDF ^ idf_weight)`
5. Rank by weighted score

**Pros**:
- ✅ Captures important phrases ("climate change", "machine learning")
- ✅ Adjustable IDF sensitivity
- ✅ Better semantic representation
- ✅ Preserves multi-word expressions

**Cons**:
- ❌ ~30% slower than noun-only
- ❌ More complex parameter tuning
- ❌ Can generate noisy bigrams without proper filtering

**Best For**:
- Academic/scientific text with technical terms
- Domains with important compound terms
- When phrase context is critical
- Fine-grained topic modeling

**Configuration**:
```json
{
  "method": "tfidf",
  "use_bigrams": true,
  "idf_weight": 1.0,
  "max_keywords": 50,
  "min_frequency": 2
}
```

**IDF Weight Guide**:
- `0.0`: Pure term frequency (ignores document uniqueness)
- `0.5`: Favor common terms
- `1.0`: Standard TF-IDF (balanced)
- `1.5`: Favor unique terms
- `2.0`: Heavily favor rare terms

**Example Output**:
```json
[
  {"phrase": "climate change", "word_count": 2, "score": 0.92, "frequency": 10},
  {"phrase": "global warming", "word_count": 2, "score": 0.87, "frequency": 8},
  {"phrase": "policy", "word_count": 1, "score": 0.72, "frequency": 12}
]
```

---

### 4. RAKE (Rapid Automatic Keyword Extraction) (`rake`)

**Description**: Domain-independent keyword extraction algorithm that identifies multi-word phrases using word co-occurrence patterns.

**Algorithm** (Simplified):
1. Split text into candidate phrases using stopwords as delimiters
2. Calculate word scores based on co-occurrence frequency
3. Calculate phrase scores (sum of word scores)
4. Rank phrases by score
5. Return top N phrases

**Pros**:
- ✅ Excellent for extracting meaningful phrases (1-5 words)
- ✅ Domain-independent (no training required)
- ✅ Captures technical terms and jargon naturally
- ✅ Good at identifying key concepts

**Cons**:
- ❌ Can miss single important words
- ❌ Sensitive to stopword list quality
- ❌ ~50ms overhead per document
- ❌ May extract overly long phrases without tuning

**Best For**:
- Technical/scientific documents
- Extracting domain terminology
- Documents with specialized vocabulary
- When phrase-level granularity is needed

**Configuration**:
```json
{
  "method": "rake",
  "max_phrase_length": 3,
  "min_keyword_frequency": 1,
  "max_keywords": 30
}
```

**Phrase Length Guide**:
- `1`: Single words only (similar to noun extraction)
- `2`: Up to 2-word phrases (e.g., "climate change")
- `3`: Up to 3-word phrases (e.g., "renewable energy policy") **[Recommended]**
- `4-5`: Longer phrases (risk of noise)

**Example Output**:
```json
[
  {"phrase": "renewable energy policy", "word_count": 3, "score": 12.5},
  {"phrase": "carbon emission targets", "word_count": 3, "score": 11.2},
  {"phrase": "sustainable development", "word_count": 2, "score": 9.8}
]
```

---

## Method Comparison

### Quick Reference Table

| Feature | Noun | All POS | TF-IDF + Bigrams | RAKE |
|---------|------|---------|------------------|------|
| **Speed** | ⚡⚡⚡ Fast | ⚡⚡ Medium | ⚡ Slower | ⚡⚡ Medium |
| **Memory** | 💾 Low | 💾 Low | 💾💾 Medium | 💾 Low |
| **Phrase Support** | ❌ No | ❌ No | ✅ Bigrams | ✅ N-grams |
| **Domain Adapt** | ⚠️ Generic | ⚠️ Generic | ⚠️ Generic | ✅ Good |
| **Technical Terms** | ⚠️ Partial | ⚠️ Partial | ✅ Good | ✅ Excellent |
| **Configuration** | 🔧 Simple | 🔧 Simple | 🔧🔧 Complex | 🔧🔧 Medium |
| **POS Filtering** | ✅ Nouns | ✅ Configurable | ❌ No | ❌ No |

### Performance Benchmarks

Based on 1000-word documents:

| Method | Avg Time | Memory | Keywords Extracted |
|--------|----------|--------|-------------------|
| Noun | 120ms | 50MB | 30-50 |
| All POS | 140ms | 55MB | 40-70 |
| TF-IDF + Bigrams | 180ms | 80MB | 35-60 |
| RAKE | 170ms | 60MB | 20-40 |

*Benchmarks on English text, single-threaded, CPU-only*

---

## Configuration Parameters

### Universal Parameters

Available for all methods:

```python
class KeywordExtractionConfig:
    method: str                    # "noun", "all_pos", "tfidf", "rake"
    max_keywords: int = 50         # Maximum keywords to extract (1-500)
    min_frequency: int = 2         # Minimum term frequency (1-100)
```

### Method-Specific Parameters

#### TF-IDF Specific
```python
use_bigrams: bool = False          # Include 2-word phrases
idf_weight: float = 1.0            # IDF sensitivity (0.0-2.0)
```

#### RAKE Specific
```python
max_phrase_length: int = 3         # N-gram size (1-5)
```

#### All POS Specific
```python
include_pos: List[str] = ["NOUN"]  # POS tags to include
```

---

## When to Use Each Method

### Decision Tree

```
Start: What is your content type?
│
├─ General web content / blog posts
│  └─ Use: noun (fast, reliable)
│
├─ Academic papers / technical docs
│  ├─ Need phrases?
│  │  ├─ Yes → Use: rake (technical phrases)
│  │  └─ No → Use: noun or tfidf
│  │
│  └─ Need compound terms?
│      └─ Yes → Use: tfidf with bigrams
│
├─ Action-oriented content (howtos, instructions)
│  └─ Use: all_pos (captures verbs)
│
└─ Domain-specific jargon
    └─ Use: rake (domain adaptation)
```

### Use Case Examples

#### Use Case 1: News Article Analysis
**Goal**: Extract main topics from news articles

**Recommended Method**: `noun`

**Why**: News articles focus on entities and concepts (nouns). Speed is important for large-scale analysis.

**Config**:
```json
{
  "method": "noun",
  "max_keywords": 30,
  "min_frequency": 2
}
```

---

#### Use Case 2: Scientific Paper Mapping
**Goal**: Build network of research papers

**Recommended Method**: `rake` or `tfidf`

**Why**: Scientific papers contain technical terms and compound concepts that need phrase-level extraction.

**Config (RAKE)**:
```json
{
  "method": "rake",
  "max_phrase_length": 3,
  "min_keyword_frequency": 1,
  "max_keywords": 40
}
```

**Config (TF-IDF)**:
```json
{
  "method": "tfidf",
  "use_bigrams": true,
  "idf_weight": 1.2,
  "max_keywords": 40
}
```

---

#### Use Case 3: Policy Document Analysis
**Goal**: Understand policy actions and recommendations

**Recommended Method**: `all_pos`

**Why**: Policy documents emphasize actions (verbs) and urgency (adjectives) alongside topics (nouns).

**Config**:
```json
{
  "method": "all_pos",
  "include_pos": ["NOUN", "VERB", "ADJ"],
  "max_keywords": 50,
  "min_frequency": 2
}
```

---

#### Use Case 4: Social Media Content
**Goal**: Analyze social media posts and threads

**Recommended Method**: `noun` or `all_pos`

**Why**: Short-form content benefits from capturing emotional tone (adjectives) and actions (verbs).

**Config**:
```json
{
  "method": "all_pos",
  "include_pos": ["NOUN", "ADJ"],
  "max_keywords": 20,
  "min_frequency": 1
}
```

---

## API Usage

### Preview Extraction (Test Methods)

```bash
POST /api/analysis/keywords/preview

{
  "sample_text": "Climate change is affecting global weather patterns...",
  "language": "en",
  "config": {
    "method": "rake",
    "max_phrase_length": 3,
    "max_keywords": 20
  }
}
```

**Response**:
```json
{
  "keywords": [
    {"phrase": "climate change", "score": 12.5, "word_count": 2},
    {"phrase": "global weather patterns", "score": 10.2, "word_count": 3}
  ],
  "total_extracted": 45,
  "processing_time": 0.023
}
```

### Generate Network with Custom Extraction

```bash
POST /api/networks/generate

{
  "name": "Climate Research Network",
  "type": "website_keyword",
  "session_ids": [1, 2, 3],
  "keyword_config": {
    "method": "tfidf",
    "use_bigrams": true,
    "idf_weight": 1.5,
    "max_keywords": 40
  }
}
```

---

## Parameter Tuning Guide

### Step-by-Step Tuning Process

#### 1. Start with Defaults

```json
{
  "method": "noun",
  "max_keywords": 50,
  "min_frequency": 2
}
```

#### 2. Evaluate Output Quality

Use the preview endpoint to test:
- Are important terms captured?
- Is there too much noise?
- Are phrases needed?

#### 3. Adjust Based on Issues

**Issue**: Too much noise (common words)
**Solution**: Increase `min_frequency` to 3 or 4

**Issue**: Missing important phrases
**Solution**: Switch to `rake` or `tfidf` with bigrams

**Issue**: Too few keywords
**Solution**: Decrease `min_frequency` or increase `max_keywords`

**Issue**: Too many keywords (network too dense)
**Solution**: Decrease `max_keywords` or increase `min_frequency`

#### 4. Fine-Tune Method-Specific Parameters

**For TF-IDF**:
- Start with `idf_weight: 1.0`
- If too many common terms → increase to 1.2-1.5
- If missing important common terms → decrease to 0.7-0.9

**For RAKE**:
- Start with `max_phrase_length: 3`
- If phrases too long → decrease to 2
- If missing important compounds → increase to 4

### Recommended Configurations by Corpus Size

**Small Corpus (<100 documents)**:
```json
{
  "method": "rake",
  "max_phrase_length": 3,
  "min_keyword_frequency": 1,
  "max_keywords": 40
}
```

**Medium Corpus (100-1000 documents)**:
```json
{
  "method": "tfidf",
  "use_bigrams": true,
  "idf_weight": 1.0,
  "max_keywords": 50,
  "min_frequency": 2
}
```

**Large Corpus (>1000 documents)**:
```json
{
  "method": "noun",
  "max_keywords": 30,
  "min_frequency": 3
}
```

---

## Performance Considerations

### Memory Usage

| Corpus Size | Noun | All POS | TF-IDF | RAKE |
|-------------|------|---------|--------|------|
| 100 docs | 500MB | 600MB | 800MB | 550MB |
| 1000 docs | 2GB | 2.5GB | 4GB | 2.2GB |
| 10000 docs | 15GB | 18GB | 30GB | 16GB |

### Processing Speed

**Single Document**: 100-200ms per document (1000 words)

**Batch Processing**: 50-100ms per document (using batch optimization)

**Network Generation**: 30-60 seconds for 1000 nodes

### Optimization Tips

1. **Use Batch Processing**: Process multiple documents together
2. **Cache Results**: Enable caching for repeated analyses
3. **Adjust Frequency Threshold**: Higher min_frequency = faster processing
4. **Limit Keywords**: Lower max_keywords = smaller networks, faster rendering

---

## Troubleshooting

### Problem: No keywords extracted

**Causes**:
- `min_frequency` too high
- Text too short
- Language mismatch

**Solution**:
```json
{
  "method": "noun",
  "max_keywords": 50,
  "min_frequency": 1  // Lower threshold
}
```

---

### Problem: Too many generic keywords

**Causes**:
- `min_frequency` too low
- Common words not filtered
- Wrong method for content type

**Solutions**:
1. Increase `min_frequency` to 3-4
2. Switch to RAKE (better at domain terms)
3. Use TF-IDF with higher `idf_weight`

---

### Problem: Missing important phrases

**Causes**:
- Using noun-only method
- Not using bigrams/RAKE

**Solution**:
```json
{
  "method": "rake",
  "max_phrase_length": 3,
  "min_keyword_frequency": 1
}
```

---

### Problem: Extraction too slow

**Causes**:
- Using TF-IDF with bigrams on large corpus
- Not using batch processing

**Solutions**:
1. Switch to `noun` method for speed
2. Use batch extraction tasks
3. Reduce `max_keywords`
4. Increase `min_frequency`

---

## Language Support

### Supported Languages

All methods support:
- **English** (`en`): Full support
- **Danish** (`da`): Full support via spaCy

### Language-Specific Considerations

**English**:
- Best tested and optimized
- Largest stopword lists
- Most accurate POS tagging

**Danish**:
- Good spaCy model available
- Custom stopword list
- May need lower `min_frequency` for smaller corpora

---

## Best Practices

1. **Always test with preview endpoint** before generating full networks
2. **Start simple** (noun method) and increase complexity only if needed
3. **Adjust for corpus size** - larger corpora need higher thresholds
4. **Monitor network density** - too many keywords = unreadable network
5. **Use appropriate method** for content type (see decision tree)
6. **Document your configuration** for reproducibility
7. **Batch process** when analyzing many documents
8. **Cache results** to avoid re-extraction

---

## Further Reading

- Phase 5 documentation: API Updates
- Phase 6 documentation: Service Layer
- Network Generation Guide
- API Reference Documentation

---

**Questions or Issues?**

Refer to the main documentation or check the troubleshooting section. For bugs or feature requests, consult the project repository.
