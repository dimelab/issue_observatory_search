# Query Formulation Strategies for Digital Methods

## Introduction

This document provides methodological guidance for query formulation in digital methods research, with specific focus on issue mapping and discourse analysis. It explains the theoretical foundations and practical applications of the query formulation features in the Issue Observatory Search platform.

## Theoretical Foundations

### Issue Mapping

Issue mapping is the practice of tracing how issues are framed, discussed, and contested across different online spaces. Effective issue mapping requires:

1. **Multi-perspectival approach**: Capture different stakeholder viewpoints
2. **Iterative refinement**: Snowballing from initial results
3. **Temporal sensitivity**: Account for how issues evolve
4. **Sphere awareness**: Understand institutional contexts

### Query as Method

In digital methods, the query is not just a technical operation but a methodological choice that shapes results. Different query formulations can:

- Reveal different discourse communities
- Highlight specific framings of an issue
- Expose temporal dynamics
- Uncover geographic variations

### Framing Theory

Framing refers to how issues are presented and understood. Our built-in framings operationalize common frames:

- **Neutral**: Attempts at objective description
- **Activist**: Emphasis on urgency and action
- **Skeptic**: Focus on uncertainty and debate
- **Scientific**: Research and evidence-based
- **Policy**: Governance and regulation
- **Industry**: Economic and business perspectives

## Snowballing Methodology

### Concept

Snowballing (also called "query expansion" or "issue crawling") is the iterative process of expanding search queries based on results. It helps:

1. Discover related terminology you didn't anticipate
2. Map discourse boundaries
3. Find communities discussing the issue
4. Understand issue evolution

### Implementation Strategy

**Step 1: Seed Queries**
- Start with 2-5 well-known terms
- Use neutral, widely-accepted terminology
- Example: "climate change", "global warming"

**Step 2: First Expansion**
- Analyze top 50-100 results
- Extract candidate terms from:
  - Page titles (highest weight)
  - Meta descriptions
  - H1/H2 headings
  - High TF-IDF nouns from content
  - Named entities (organizations, locations, events)

**Step 3: Candidate Review**
- Review candidates by score
- Approve terms that:
  - Relate directly to the issue
  - Represent distinct perspectives or sub-topics
  - Appear in credible sources
- Reject terms that:
  - Are too generic
  - Are technical jargon unrelated to the issue
  - Represent spam or low-quality content

**Step 4: Execute Expansion**
- Search with approved terms
- Compare results to seed queries
- Note new domains/sources appearing

**Step 5: Iterate**
- Generation 2: Expand from generation 1 results
- Generation 3: Expand from generation 2 results
- Continue until saturation (no relevant new terms)

### Stopping Criteria

Stop snowballing when:
- New candidates are mostly irrelevant (score < 0.2)
- New results overlap >80% with previous generations
- You've reached a predefined generation limit (typically 3-5)
- The issue scope is well-defined

## Multi-Perspective Query Formulation

### Rationale

Different actors frame issues differently. Capturing multiple framings:

1. Reveals discourse conflicts
2. Identifies stakeholder positions
3. Maps the "issue landscape"
4. Enables comparative analysis

### Framing Catalog

#### 1. Neutral Framing

**Purpose**: Baseline, descriptive terminology

**Characteristics**:
- Widely accepted terms
- Minimal evaluative language
- Scientific/technical terminology

**Example queries**:
- "climate change"
- "global warming"
- "sea level rise"

**Use when**: Establishing baseline, comparing against other framings

#### 2. Activist Framing

**Purpose**: Capture urgency-oriented discourse

**Characteristics**:
- Emergency language
- Action-oriented verbs
- Moral framing

**Example queries**:
- "climate crisis"
- "climate emergency"
- "climate breakdown"
- "fight climate change"
- "climate action now"

**Use when**: Analyzing advocacy groups, social movements, activist media

#### 3. Skeptic Framing

**Purpose**: Capture questioning/contrarian perspectives

**Characteristics**:
- Uncertainty language
- Debate framing
- Questioning assumptions

**Example queries**:
- "climate skepticism"
- "climate debate"
- "climate controversy"
- "question climate change"
- "climate uncertainty"

**Use when**: Analyzing contrarian discourse, understanding opposition

#### 4. Scientific Framing

**Purpose**: Academic and research perspective

**Characteristics**:
- Research terminology
- Evidence language
- Methodological focus

**Example queries**:
- "climate research"
- "climate science"
- "climate evidence"
- "peer review climate"
- "climate study"

**Use when**: Analyzing scientific discourse, expert communities

#### 5. Policy Framing

**Purpose**: Governance and regulation perspective

**Characteristics**:
- Regulatory language
- Institutional terms
- Policy mechanisms

**Example queries**:
- "climate policy"
- "climate regulation"
- "climate legislation"
- "climate governance"
- "Paris Agreement"

**Use when**: Analyzing government sources, policy documents

#### 6. Industry Framing

**Purpose**: Business and economic perspective

**Characteristics**:
- Market terminology
- Economic framing
- Business opportunities

**Example queries**:
- "green economy"
- "climate business"
- "carbon market"
- "ESG climate"
- "climate investment"

**Use when**: Analyzing corporate discourse, business media

#### 7. Media Framing

**Purpose**: News coverage perspective

**Characteristics**:
- News terminology
- Coverage framing
- Current events

**Example queries**:
- "climate news"
- "climate coverage"
- "climate report"
- "climate headlines"

**Use when**: Analyzing news media, journalism

#### 8. Local Framing

**Purpose**: Geographic specificity

**Characteristics**:
- Location names
- Regional impacts
- Local contexts

**Example queries**:
- "climate change in Denmark"
- "Denmark climate impact"
- "Nordic climate policy"

**Use when**: Geographic issue mapping, comparative regional analysis

**Variables**: `{issue}`, `{location}`

#### 9. Temporal Framing

**Purpose**: Time-specific analysis

**Characteristics**:
- Year specifications
- Historical framing
- Future projections

**Example queries**:
- "climate change 2024"
- "climate history"
- "future of climate"

**Use when**: Temporal analysis, trend detection

**Variables**: `{issue}`, `{year}`

## Comparative Framing Analysis

### Methodology

1. **Execute Multi-Perspective Search**
   - Run same issue with all framings
   - Use identical parameters (max_results, search_engine)
   - Same time period

2. **Compare Results**
   ```
   POST /api/advanced-search/sessions/compare
   {
     "session_ids": [neutral_id, activist_id, skeptic_id],
     "comparison_type": "full"
   }
   ```

3. **Analyze Differences**
   - **URL Overlap**: How much do different framings share?
     - Low overlap (<0.3): Distinct discourse communities
     - High overlap (>0.7): Similar sources, different emphasis

   - **Domain Differences**: Which spheres dominate each framing?
     - Activist: NGOs, advocacy groups
     - Scientific: Academic institutions
     - Skeptic: Alternative media, blogs

   - **Discourse Differences**: What terms are unique to each?
     - Compare top nouns and entities
     - Identify framing-specific vocabulary

4. **Interpret Findings**
   - Map discourse landscape
   - Identify filter bubbles
   - Understand framing contests

### Example Analysis

**Issue**: Climate Change
**Framings**: Neutral, Activist, Skeptic

**Hypothetical Results**:

| Metric | Neutral | Activist | Skeptic |
|--------|---------|----------|---------|
| Top Sphere | News (40%) | Activist (50%) | General (35%) |
| Academia % | 25% | 10% | 5% |
| Unique Terms | "warming", "data" | "emergency", "action" | "debate", "uncertainty" |
| Jaccard (vs Neutral) | 1.0 | 0.35 | 0.20 |

**Interpretation**:
- Activist framing yields distinct discourse community (low overlap)
- Skeptic framing largely separate from neutral/activist
- Academic sources more present in neutral framing
- Clear vocabulary differences indicate framing success

## Temporal Query Strategies

### Rationale

Issues evolve over time. Temporal analysis reveals:
- Emerging issues and terms
- Declining attention
- Event impacts
- Discourse shifts

### Approaches

#### 1. Snapshot Comparison

**Method**: Same query, different time periods

**Example**:
```
Period 1: 2019-01-01 to 2019-12-31
Period 2: 2023-01-01 to 2023-12-31
Query: "climate policy"
```

**Analysis**:
- URL overlap (what's stable vs. changing)
- Domain changes (new actors, disappeared actors)
- Terminology shifts (noun/entity differences)

**Use when**: Understanding long-term evolution

#### 2. Event Analysis

**Method**: Before/after comparison

**Example**:
```
Before: 2015-01-01 to 2015-11-30 (before Paris Agreement)
After: 2015-12-01 to 2016-06-30 (after Paris Agreement)
Query: "climate agreement"
```

**Analysis**:
- Attention spikes
- New actors entering discourse
- Framing changes

**Use when**: Analyzing specific events' impact

#### 3. Trend Detection

**Method**: Multiple consecutive periods

**Example**:
```
Period 1: 2020-Q1
Period 2: 2020-Q2
Period 3: 2020-Q3
Period 4: 2020-Q4
Query: "climate change"
```

**Analysis**:
- Emerging domains (first appearance)
- Declining domains (disappearance)
- Stable domains (consistent presence)

**Use when**: Identifying trends, tracking discourse evolution

## Domain Filtering Strategies

### Sphere-Based Analysis

#### Rationale
Different institutional spheres produce different types of knowledge and discourse.

#### Sphere Characteristics

**Academia**:
- Slow-moving
- Peer-reviewed
- Evidence-based
- Technical terminology

**Government**:
- Policy-focused
- Authoritative
- Regulatory language
- Official positions

**News**:
- Event-driven
- Accessible language
- Current focus
- Multiple perspectives

**Activist**:
- Advocacy-oriented
- Moral framing
- Action emphasis
- Grassroots perspectives

#### Comparative Sphere Analysis

**Methodology**:
1. Execute same query with sphere filters
2. Compare discourse across spheres
3. Analyze sphere-specific framing

**Example**:
```json
Query: "climate change"

Filter 1: sphere_filter=["academia"]
Filter 2: sphere_filter=["activist"]
Filter 3: sphere_filter=["news"]
```

**Expected Differences**:
- Academia: "anthropogenic", "carbon cycle", "climate model"
- Activist: "crisis", "emergency", "action"
- News: "report", "scientists say", "impact"

### Geographic Filtering

#### Rationale
Issues are locally situated. Geographic filtering enables:
- Cross-national comparison
- Local issue manifestations
- Cultural variations

#### Approaches

**1. TLD Filtering**
```json
{
  "tld_filter": [".dk", ".se", ".no"]
}
```

**Use when**: Analyzing Nordic countries

**2. Local Framing + TLD**
```json
{
  "queries": [
    "climate change in Denmark",
    "klimaændringer i Danmark"
  ],
  "tld_filter": [".dk"]
}
```

**Use when**: Deep local analysis

**3. Cross-National Comparison**
```
Session 1: TLD=.dk, Language=da
Session 2: TLD=.se, Language=sv
Session 3: TLD=.no, Language=no

Compare sessions to identify national differences
```

## Bulk Search Strategies

### Use Cases

1. **Systematic Framing Analysis**: All framings × multiple issues
2. **Longitudinal Study**: Same queries × multiple time periods
3. **Cross-National**: Same queries × multiple countries
4. **Comprehensive Mapping**: Many related queries simultaneously

### CSV Design Patterns

#### Pattern 1: Framing Matrix

```csv
query,framing,language,max_results
"climate change",neutral,en,50
"climate crisis",activist,en,50
"climate skepticism",skeptic,en,50
"climate science",scientific,en,50
"climate policy",policy,en,50
```

#### Pattern 2: Temporal Series

```csv
query,date_from,date_to,temporal_snapshot
"climate policy",2019-01-01,2019-12-31,true
"climate policy",2020-01-01,2020-12-31,true
"climate policy",2021-01-01,2021-12-31,true
"climate policy",2022-01-01,2022-12-31,true
"climate policy",2023-01-01,2023-12-31,true
```

#### Pattern 3: Geographic Matrix

```csv
query,language,tld_filter
"climate change",en,.us
"climate change",en,.uk
"klimaændringer",da,.dk
"klimatförändring",sv,.se
"klimaendringer",no,.no
```

## Advanced Techniques

### Discourse Network Analysis

**Concept**: Combine query formulation with network analysis

**Method**:
1. Execute multi-perspective search
2. Scrape and analyze content (Phase 4)
3. Generate noun co-occurrence networks (Phase 5)
4. Compare networks across framings

**Reveals**:
- Framing-specific discourse structures
- Conceptual associations per perspective
- Boundary objects (shared terms)

### Semantic Snowballing

**Concept**: Use NLP to guide expansion

**Method**:
1. Initial search
2. Extract and analyze content
3. Use high TF-IDF nouns as expansion candidates
4. Filter by semantic similarity to seed queries
5. Execute expansion

**Advantages**:
- Content-driven rather than metadata-driven
- Captures actual discourse, not just titles
- Better for finding sub-topics

### Cross-Language Analysis

**Concept**: Compare issue framing across languages

**Method**:
1. Formulate parallel queries in multiple languages
2. Execute with appropriate TLD filters
3. Analyze and translate results
4. Compare discourse patterns

**Example**:
```
English: "climate change" (TLD: .us, .uk)
Danish: "klimaændringer" (TLD: .dk)
Swedish: "klimatförändring" (TLD: .se)
```

**Challenges**:
- Translation accuracy
- Cultural framing differences
- Search engine localization

## Methodological Considerations

### Validity

**Threats**:
- Search engine bias (algorithmic)
- Personalization effects
- Temporal volatility
- Platform-specific results

**Mitigation**:
- Use multiple search engines
- Document search parameters
- Temporal snapshots
- Triangulate with other methods

### Reliability

**Threats**:
- Inconsistent query formulation
- Subjective candidate approval
- Platform changes

**Mitigation**:
- Systematic query templates
- Inter-coder reliability for approvals
- Version control for queries
- Regular replication

### Transparency

**Best Practices**:
- Document all query decisions
- Export query lists
- Archive snapshots
- Report parameters (engine, date, max_results)
- Explain framing choices

### Ethics

**Considerations**:
- Respect robots.txt
- Rate limiting
- Attribution of sources
- Privacy of scraped content
- Potential for misuse (manipulation)

## References

### Digital Methods

- Rogers, R. (2019). *Doing Digital Methods*. SAGE.
- Marres, N. (2015). "Why Map Issues? On Controversy Analysis as a Digital Method." *Science, Technology, & Human Values*.
- Venturini, T., & Munk, A. K. (2021). *Controversy Mapping: A Field Guide*. Polity.

### Query Formulation

- Borra, E., & Rieder, B. (2014). "Programmed method: Developing a toolset for capturing and analyzing tweets." *Aslib Journal of Information Management*.
- Marres, N., & Weltevrede, E. (2013). "Scraping the Social? Issues in live social research." *Journal of Cultural Economy*.

### Framing Theory

- Entman, R. M. (1993). "Framing: Toward clarification of a fractured paradigm." *Journal of Communication*.
- Chong, D., & Druckman, J. N. (2007). "Framing Theory." *Annual Review of Political Science*.

## Conclusion

Effective query formulation is both art and science. The features in this platform provide:

1. **Systematic approaches**: Templates and framings
2. **Iterative refinement**: Snowballing
3. **Comparative analysis**: Multi-perspective and temporal
4. **Methodological transparency**: Documentation and replication

Use these tools thoughtfully, document your choices, and always interpret results within their methodological context.
