# Issue Observatory Search - Graphology & Keyword Extraction Enhancement Implementation Plan

**Version:** 6.0.0
**Date:** December 9, 2025
**Status:** DRAFT - Pending Approval

---

## Executive Summary

This plan outlines the migration from Vis.js to Graphology/Sigma.js for network visualization and the enhancement of keyword extraction methods with additional options for TF-IDF, RAKE, and Named Entity Recognition (NER) based on implementations from [some2net](https://github.com/dimelab/some2net).

### Key Changes
1. **Network Visualization**: Replace Vis.js with Graphology + Sigma.js (ForceAtlas2 layout)
2. **Keyword Extraction**: Add TF-IDF and RAKE-based extraction with configurable parameters
3. **NER Networks**: Introduce Website → NER network type with multilingual support (English & Danish)

---

## 1. Project Context

### 1.1 Current State (v5.0.0)
- **Visualization**: Vis.js library with ForceAtlas2-based physics
- **Keyword Extraction**: spaCy-based noun extraction with TF-IDF ranking
- **Network Types**:
  - Search → Website (issue-website)
  - Website → Noun (bipartite)
  - Website → Concept (LLM-based, optional)
- **Languages**: English and Danish support via spaCy

### 1.2 Target State (v6.0.0)
- **Visualization**: Graphology + Sigma.js with ForceAtlas2 layout
- **Keyword Extraction**:
  - Current: Noun-only extraction
  - New: All keywords option (nouns, verbs, adjectives)
  - New: RAKE algorithm with n-gram configuration
  - Enhanced: TF-IDF with bigram support and IDF sensitivity tuning
- **Network Types**:
  - Search → Website (unchanged)
  - Website → Keywords (enhanced from Website → Noun)
  - Website → NER (new, multilingual)
  - Website → Concept (unchanged)

---

## 2. Architecture Overview

### 2.1 Technology Stack Changes

| Component | Current (v5.0.0) | Target (v6.0.0) | Source |
|-----------|------------------|-----------------|---------|
| Graph Visualization | Vis.js 9.x | Graphology + Sigma.js | some2net |
| Layout Algorithm | Vis.js ForceAtlas2 | Graphology ForceAtlas2 | some2net |
| Keyword Extraction | spaCy nouns only | spaCy + RAKE | some2net |
| TF-IDF | Basic implementation | Enhanced with bigrams | some2net |
| NER | spaCy (basic) | Transformer-based multilingual | some2net |

### 2.2 Dependencies to Add

```txt
# Frontend (via CDN or npm)
graphology==0.25.x
sigma==3.0.x
graphology-layout-forceatlas2==0.10.x

# Backend Python
rake-nltk==1.0.6              # RAKE keyword extraction
transformers==4.35.x           # For multilingual NER (Davlan/xlm-roberta-base-ner-hrl)
torch==2.1.x                   # Required for transformers
```

**Note**: Transformers and torch add ~2GB to deployment. Consider making them optional or using lighter alternatives.

---

## 3. Implementation Phases

### Phase 1: Backend - Enhanced Keyword Extraction (4-6 hours)

#### 3.1.1 Create RAKE Keyword Extractor
**File**: `backend/core/nlp/rake_extraction.py`

```python
"""RAKE-based keyword extraction with n-gram support."""
from rake_nltk import Rake
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class RAKEKeyword:
    phrase: str
    score: float
    word_count: int

class RAKEExtractor:
    """
    RAKE (Rapid Automatic Keyword Extraction) implementation.

    Based on some2net implementation.
    """

    def __init__(
        self,
        language: str = "english",
        max_phrase_length: int = 3,
        min_keyword_frequency: int = 1,
    ):
        """
        Initialize RAKE extractor.

        Args:
            language: Language for stopwords (english, danish)
            max_phrase_length: Maximum n-gram size (1-5)
            min_keyword_frequency: Minimum frequency threshold
        """
        pass

    async def extract_keywords(
        self,
        text: str,
        max_keywords: int = 50,
        min_score: float = 0.0,
    ) -> List[RAKEKeyword]:
        """Extract keywords using RAKE algorithm."""
        pass
```

**Implementation Details**:
- Support English and Danish stopwords
- Configurable n-gram length (1-5 words)
- Score normalization for consistency with TF-IDF
- Async wrapper for consistency with existing extractors

#### 3.1.2 Enhance TF-IDF Calculator
**File**: `backend/core/nlp/tfidf.py` (modify existing)

Add methods:
```python
class TFIDFCalculator:
    def __init__(
        self,
        use_bigrams: bool = False,
        idf_weight: float = 1.0,  # IDF sensitivity: 0.0 (pure TF) to 2.0 (IDF-heavy)
    ):
        """
        Initialize TF-IDF calculator with enhanced options.

        Args:
            use_bigrams: Include bigrams in addition to unigrams
            idf_weight: Weight for IDF component (0.0-2.0)
                       1.0 = standard TF-IDF
                       <1.0 = favor term frequency
                       >1.0 = favor document uniqueness
        """
        pass

    def _extract_ngrams(
        self,
        tokens: List[str],
        n: int = 2
    ) -> List[str]:
        """Extract n-grams from token list."""
        pass

    def calculate_tfidf_weighted(
        self,
        term: str,
        document: List[str],
        corpus: List[List[str]],
    ) -> float:
        """Calculate TF-IDF with weighted IDF component."""
        # TF-IDF = TF * (IDF ^ idf_weight)
        pass
```

#### 3.1.3 Create Universal Keyword Extractor
**File**: `backend/core/nlp/keyword_extraction.py` (new)

```python
"""Unified keyword extraction interface."""
from typing import Literal, List, Optional
from dataclasses import dataclass

KeywordMethod = Literal["noun", "all_pos", "tfidf", "rake"]

@dataclass
class KeywordConfig:
    """Configuration for keyword extraction."""
    method: KeywordMethod
    max_keywords: int = 50
    min_frequency: int = 2

    # TF-IDF specific
    use_bigrams: bool = False
    idf_weight: float = 1.0  # 0.0 (pure TF) to 2.0 (IDF-heavy)

    # RAKE specific
    max_phrase_length: int = 3  # n-gram size for RAKE

    # POS filter specific
    include_pos: List[str] = ["NOUN"]  # For "all_pos", include: NOUN, VERB, ADJ

class UniversalKeywordExtractor:
    """
    Unified interface for all keyword extraction methods.

    Supports:
    - noun: Original spaCy noun extraction (backward compatible)
    - all_pos: Extract nouns, verbs, adjectives (spaCy)
    - tfidf: TF-IDF with bigrams and IDF weighting
    - rake: RAKE algorithm with n-grams
    """

    async def extract_keywords(
        self,
        text: str,
        language: str,
        config: KeywordConfig,
    ) -> List[ExtractedKeyword]:
        """Extract keywords based on configuration."""
        pass
```

#### 3.1.4 Create Transformer-based NER Extractor
**File**: `backend/core/nlp/ner_transformer.py` (new)

```python
"""Transformer-based multilingual NER."""
from transformers import pipeline
from typing import List, Optional

class TransformerNERExtractor:
    """
    Multilingual NER using Davlan/xlm-roberta-base-ner-hrl.

    Based on some2net implementation.
    Supports 10+ languages including English and Danish.
    """

    def __init__(
        self,
        model_name: str = "Davlan/xlm-roberta-base-ner-hrl",
        confidence_threshold: float = 0.85,
        device: int = -1,  # -1 for CPU, 0+ for GPU
    ):
        """Initialize transformer-based NER."""
        pass

    async def extract_entities(
        self,
        text: str,
        language: str,
        entity_types: Optional[List[str]] = None,
    ) -> List[ExtractedEntity]:
        """
        Extract named entities using transformer model.

        Entity types: PER, ORG, LOC, MISC, etc.
        """
        pass
```

**Note**: This adds significant dependencies. Consider:
- Making transformers optional (feature flag)
- Using existing spaCy NER as fallback
- Caching model on first load

---

### Phase 2: Backend - Database Schema Updates (2-3 hours)

#### 3.2.1 Update ExtractedNoun Model
**File**: `backend/models/analysis.py` (modify)

Rename or extend `ExtractedNoun` to `ExtractedKeyword`:
```python
class ExtractedKeyword(Base):
    """Extracted keywords (formerly nouns) from website content."""
    __tablename__ = "extracted_keywords"

    # ... existing fields ...

    # New fields
    extraction_method: Mapped[str] = mapped_column(
        String(50),
        default="noun",  # backward compatible
        comment="Extraction method: noun, all_pos, tfidf, rake"
    )
    phrase_length: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of words in keyword phrase (for n-grams)"
    )
    pos_tag: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Part of speech tag: NOUN, VERB, ADJ, etc."
    )

# Keep ExtractedNoun as alias for backward compatibility
ExtractedNoun = ExtractedKeyword
```

#### 3.2.2 Create ExtractedNER Model
**File**: `backend/models/analysis.py` (add)

```python
class ExtractedNER(Base):
    """Named entities extracted from website content."""
    __tablename__ = "extracted_entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    website_content_id: Mapped[int] = mapped_column(
        ForeignKey("website_contents.id", ondelete="CASCADE"),
        index=True
    )

    entity_text: Mapped[str] = mapped_column(String(500))
    entity_type: Mapped[str] = mapped_column(String(50))  # PER, ORG, LOC, etc.
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    frequency: Mapped[int] = mapped_column(Integer, default=1)
    language: Mapped[str] = mapped_column(String(10))

    # Extraction metadata
    extraction_method: Mapped[str] = mapped_column(
        String(50),
        default="spacy",
        comment="spacy or transformer"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # Relationships
    website_content: Mapped["WebsiteContent"] = relationship(back_populates="entities")
```

#### 3.2.3 Update Network Schema
**File**: `backend/schemas/network.py` (modify)

```python
class NetworkGenerateRequest(BaseModel):
    """Request schema for generating a network."""

    type: Literal[
        "search_website",
        "website_keyword",  # renamed from website_noun
        "website_ner",      # NEW
        "website_concept"
    ] = Field(...)

    # Keyword extraction config (for website_keyword)
    keyword_config: Optional[KeywordExtractionConfig] = Field(
        default=None,
        description="Configuration for keyword extraction"
    )

    # NER config (for website_ner)
    ner_config: Optional[NERExtractionConfig] = Field(
        default=None,
        description="Configuration for NER extraction"
    )

class KeywordExtractionConfig(BaseModel):
    """Configuration for keyword extraction."""
    method: KeywordMethod = "noun"
    max_keywords: int = 50
    use_bigrams: bool = False
    idf_weight: float = 1.0
    max_phrase_length: int = 3
    include_pos: List[str] = ["NOUN"]

class NERExtractionConfig(BaseModel):
    """Configuration for NER extraction."""
    extraction_method: Literal["spacy", "transformer"] = "spacy"
    entity_types: List[str] = ["PERSON", "ORG", "GPE", "LOC"]
    confidence_threshold: float = 0.85
    max_entities_per_website: int = 100
```

#### 3.2.4 Database Migration
**File**: `migrations/versions/XXXX_add_keyword_and_ner_enhancements.py`

- Add new columns to `extracted_keywords` (formerly `extracted_nouns`)
- Create `extracted_entities` table
- Add indexes for performance
- Migrate existing noun data (set `extraction_method='noun'`)

---

### Phase 3: Backend - Network Builders (4-5 hours)

#### 3.3.1 Update Website-Keyword Network Builder
**File**: `backend/core/networks/website_keyword.py` (rename from website_noun.py)

```python
class WebsiteKeywordNetworkBuilder(NetworkBuilder):
    """
    Build bipartite network: websites → keywords.

    Enhanced from website_noun to support multiple extraction methods.
    """

    def __init__(
        self,
        name: str,
        session: AsyncSession,
        session_ids: List[int],
        keyword_config: KeywordConfig,
        aggregate_by_domain: bool = True,
    ):
        """Initialize website-keyword network builder."""
        pass

    async def build(self) -> nx.Graph:
        """Build network with keywords extracted using configured method."""
        pass
```

#### 3.3.2 Create Website-NER Network Builder
**File**: `backend/core/networks/website_ner.py` (new)

```python
class WebsiteNERNetworkBuilder(NetworkBuilder):
    """
    Build bipartite network: websites → named entities.

    Based on some2net NER network implementation.
    Supports multilingual entity extraction.
    """

    def __init__(
        self,
        name: str,
        session: AsyncSession,
        session_ids: List[int],
        ner_config: NERExtractionConfig,
        aggregate_by_domain: bool = True,
    ):
        """Initialize website-NER network builder."""
        pass

    async def build(self) -> nx.Graph:
        """
        Build the website-NER bipartite network.

        Node types:
        - website: Source websites
        - entity: Named entities (PERSON, ORG, LOC, etc.)

        Edge weights: Entity frequency or confidence scores
        """
        pass

    async def _load_entities(self) -> List[ExtractedNER]:
        """Load entities from database."""
        pass

    async def _aggregate_entities_by_domain(
        self,
        entities: List[ExtractedNER]
    ) -> Dict[str, List[Dict]]:
        """Aggregate entities by domain."""
        pass
```

#### 3.3.3 Update Network Service
**File**: `backend/services/network_service.py` (modify)

Update to handle new network types and configurations:
```python
async def generate_network(
    self,
    request: NetworkGenerateRequest,
    user_id: int,
) -> Network:
    """Generate network based on type and configuration."""

    if request.type == "website_keyword":
        builder = WebsiteKeywordNetworkBuilder(
            name=request.name,
            session=self.session,
            session_ids=request.session_ids,
            keyword_config=request.keyword_config or KeywordConfig(),
            aggregate_by_domain=request.aggregate_by_domain,
        )
    elif request.type == "website_ner":
        builder = WebsiteNERNetworkBuilder(
            name=request.name,
            session=self.session,
            session_ids=request.session_ids,
            ner_config=request.ner_config or NERExtractionConfig(),
            aggregate_by_domain=request.aggregate_by_domain,
        )
    # ... other types ...
```

---

### Phase 4: Frontend - Graphology Migration (6-8 hours)

#### 3.4.1 Add Graphology Dependencies
**File**: `frontend/templates/base.html` (modify)

```html
<!-- Replace Vis.js with Graphology + Sigma.js -->
<script src="https://cdn.jsdelivr.net/npm/graphology@0.25.4/dist/graphology.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/sigma@3.0.0-alpha1/dist/sigma.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/graphology-layout-forceatlas2@0.10.1/index.js"></script>
```

#### 3.4.2 Create New Network Visualizer
**File**: `frontend/static/js/network-viz-graphology.js` (new)

```javascript
/**
 * Network Visualization using Graphology + Sigma.js
 *
 * Based on some2net visualization implementation.
 *
 * Features:
 * - ForceAtlas2 layout via Graphology
 * - Interactive rendering via Sigma.js
 * - GEXF file support
 * - Node coloring by type
 * - Search and filtering
 */

class GraphologyNetworkVisualizer {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        this.graph = new graphology.Graph({ type: 'undirected' });
        this.renderer = null;

        // Configuration (similar to some2net)
        this.options = {
            layout: 'forceAtlas2',
            fa2Settings: {
                iterations: 500,
                settings: {
                    barnesHutOptimize: true,
                    barnesHutTheta: 0.5,
                    scalingRatio: 2,
                    gravity: 1,
                    slowDown: 10,
                    linLogMode: false,
                    outboundAttractionDistribution: false,
                    adjustSizes: false,
                    edgeWeightInfluence: 1
                }
            },
            ...options
        };

        this.init();
    }

    /**
     * Initialize Sigma.js renderer with Graphology graph
     */
    init() {
        // Create Sigma renderer
        this.renderer = new Sigma(this.graph, this.container, {
            renderEdgeLabels: false,
            defaultNodeColor: '#6B7280',
            defaultEdgeColor: '#E5E7EB',
            labelFont: 'Arial',
            labelSize: 14,
            labelWeight: 'normal',
        });

        this.setupEventListeners();
    }

    /**
     * Load and parse GEXF file
     */
    async loadFromGEXF(url) {
        try {
            const response = await fetch(url, {
                headers: {
                    'Authorization': 'Bearer ' + localStorage.getItem('token')
                }
            });

            const gexfText = await response.text();
            await this.parseGEXF(gexfText);

        } catch (error) {
            console.error('Error loading GEXF:', error);
            showToast('Failed to load network', 'error');
        }
    }

    /**
     * Parse GEXF and populate Graphology graph
     */
    async parseGEXF(gexfText) {
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(gexfText, 'text/xml');

        // Clear existing graph
        this.graph.clear();

        // Parse nodes
        const xmlNodes = xmlDoc.querySelectorAll('node');
        xmlNodes.forEach(xmlNode => {
            const id = xmlNode.getAttribute('id');
            const label = xmlNode.getAttribute('label') || id;

            // Parse attributes
            const attributes = this.parseNodeAttributes(xmlNode);
            const nodeType = attributes.type || 'default';

            this.graph.addNode(id, {
                label,
                size: 10,
                color: this.getNodeColor(nodeType),
                ...attributes
            });
        });

        // Parse edges
        const xmlEdges = xmlDoc.querySelectorAll('edge');
        xmlEdges.forEach(xmlEdge => {
            const source = xmlEdge.getAttribute('source');
            const target = xmlEdge.getAttribute('target');
            const weight = parseFloat(xmlEdge.getAttribute('weight')) || 1;

            if (this.graph.hasNode(source) && this.graph.hasNode(target)) {
                this.graph.addEdge(source, target, { weight });
            }
        });

        // Apply ForceAtlas2 layout
        await this.applyLayout();

        // Refresh renderer
        this.renderer.refresh();
    }

    /**
     * Apply ForceAtlas2 layout (based on some2net)
     */
    async applyLayout() {
        const { iterations, settings } = this.options.fa2Settings;

        // Run ForceAtlas2
        const positions = forceAtlas2.assign(this.graph, {
            iterations,
            settings
        });

        // Update node positions
        this.graph.updateEachNodeAttributes((node, attr) => {
            return {
                ...attr,
                x: positions[node].x,
                y: positions[node].y
            };
        });
    }

    /**
     * Get node color based on type (same as Vis.js version)
     */
    getNodeColor(nodeType) {
        const colorMap = {
            'search': '#3B82F6',      // Blue
            'website': '#10B981',     // Green
            'keyword': '#F59E0B',     // Amber (renamed from noun)
            'entity': '#8B5CF6',      // Purple (for NER)
            'topic': '#EC4899',       // Pink
            'default': '#6B7280'      // Gray
        };
        return colorMap[nodeType] || colorMap.default;
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Node click
        this.renderer.on('clickNode', ({ node }) => {
            const nodeData = this.graph.getNodeAttributes(node);
            this.onNodeSelect(nodeData);
        });

        // Background click (deselect)
        this.renderer.on('clickStage', () => {
            this.onNodeDeselect();
        });
    }

    /**
     * Filter nodes by type
     */
    filterByType(types) {
        this.graph.forEachNode((node) => {
            const nodeData = this.graph.getNodeAttributes(node);
            const visible = types.length === 0 || types.includes(nodeData.type);
            this.graph.setNodeAttribute(node, 'hidden', !visible);
        });
        this.renderer.refresh();
    }

    /**
     * Search nodes by label
     */
    searchNodes(query) {
        const lowerQuery = query.toLowerCase();

        this.graph.forEachNode((node) => {
            const nodeData = this.graph.getNodeAttributes(node);
            const matches = nodeData.label.toLowerCase().includes(lowerQuery);
            this.graph.setNodeAttribute(node, 'hidden', !matches && query !== '');
        });

        this.renderer.refresh();
    }

    /**
     * Export as PNG
     */
    exportAsPNG(filename = 'network.png') {
        const canvas = this.renderer.getCanvas();
        canvas.toBlob((blob) => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
        });
    }

    /**
     * Callbacks (override these)
     */
    onNodeSelect(node) {
        console.log('Node selected:', node);
    }

    onNodeDeselect() {
        console.log('Node deselected');
    }

    /**
     * Destroy renderer
     */
    destroy() {
        if (this.renderer) {
            this.renderer.kill();
            this.renderer = null;
        }
    }
}

// Export
window.GraphologyNetworkVisualizer = GraphologyNetworkVisualizer;
```

#### 3.4.3 Update Network Visualization Template
**File**: `frontend/templates/networks/visualize.html` (modify)

- Replace `NetworkVisualizer` instantiation with `GraphologyNetworkVisualizer`
- Keep same UI controls (filters, search, zoom)
- Update documentation to reference Graphology

#### 3.4.4 Update Network Creation UI
**File**: `frontend/templates/networks/create.html` (modify)

Add configuration options for keyword extraction:
```html
<!-- Keyword Extraction Method -->
<div class="form-group">
    <label>Keyword Extraction Method</label>
    <select name="keyword_method" id="keyword-method">
        <option value="noun">Nouns Only (Original)</option>
        <option value="all_pos">All Keywords (Nouns, Verbs, Adjectives)</option>
        <option value="tfidf">TF-IDF with Bigrams</option>
        <option value="rake">RAKE (Keyword Phrases)</option>
    </select>
</div>

<!-- TF-IDF Options (shown when tfidf selected) -->
<div id="tfidf-options" class="hidden">
    <label>
        <input type="checkbox" name="use_bigrams" />
        Include Bigrams
    </label>
    <label>
        IDF Weight: <input type="range" name="idf_weight" min="0" max="2" step="0.1" value="1.0" />
        <span id="idf-weight-value">1.0</span>
    </label>
</div>

<!-- RAKE Options (shown when rake selected) -->
<div id="rake-options" class="hidden">
    <label>
        Max Phrase Length:
        <select name="max_phrase_length">
            <option value="1">1 word</option>
            <option value="2">2 words</option>
            <option value="3" selected>3 words</option>
            <option value="4">4 words</option>
            <option value="5">5 words</option>
        </select>
    </label>
</div>

<!-- NER Options (for website_ner network type) -->
<div id="ner-options" class="hidden">
    <label>Entity Types:</label>
    <label><input type="checkbox" name="entity_types" value="PERSON" checked /> Persons</label>
    <label><input type="checkbox" name="entity_types" value="ORG" checked /> Organizations</label>
    <label><input type="checkbox" name="entity_types" value="GPE" checked /> Locations (GPE)</label>
    <label><input type="checkbox" name="entity_types" value="LOC" checked /> Locations</label>

    <label>
        Extraction Method:
        <select name="ner_method">
            <option value="spacy" selected>spaCy (Fast)</option>
            <option value="transformer">Transformer (Accurate, Slow)</option>
        </select>
    </label>
</div>
```

---

### Phase 5: API Updates (2-3 hours)

#### 3.5.1 Update Network Generation Endpoint
**File**: `backend/api/networks.py` (modify)

```python
@router.post("/generate", response_model=NetworkGenerationTaskResponse)
async def generate_network(
    request: NetworkGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a network from search sessions.

    Supported network types:
    - search_website: Search queries → Websites
    - website_keyword: Websites → Keywords (enhanced with multiple methods)
    - website_ner: Websites → Named Entities (NEW)
    - website_concept: Websites → LLM-extracted concepts

    Keyword extraction methods:
    - noun: Original noun-only extraction (backward compatible)
    - all_pos: Nouns, verbs, adjectives
    - tfidf: TF-IDF with bigrams and IDF weighting
    - rake: RAKE algorithm with n-gram phrases
    """
    # Validate configurations
    if request.type == "website_keyword":
        if not request.keyword_config:
            request.keyword_config = KeywordConfig()

    elif request.type == "website_ner":
        if not request.ner_config:
            request.ner_config = NERExtractionConfig()

    # Trigger async network generation
    task = generate_network_task.delay(
        request.dict(),
        current_user.id
    )

    return NetworkGenerationTaskResponse(
        task_id=task.id,
        status="pending",
        message=f"Network generation started for {request.type}"
    )
```

#### 3.5.2 Add Keyword Extraction Preview Endpoint
**File**: `backend/api/analysis.py` (add)

```python
@router.post("/keywords/preview", response_model=KeywordPreviewResponse)
async def preview_keyword_extraction(
    request: KeywordPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Preview keyword extraction results before generating network.

    Useful for testing different extraction methods and parameters.
    """
    # Extract keywords using specified configuration
    extractor = UniversalKeywordExtractor()
    keywords = await extractor.extract_keywords(
        text=request.sample_text,
        language=request.language,
        config=request.config
    )

    return KeywordPreviewResponse(
        keywords=[
            {"phrase": k.phrase, "score": k.score}
            for k in keywords[:20]
        ],
        config=request.config
    )
```

---

### Phase 6: Analysis Service Updates (3-4 hours)

#### 3.6.1 Update Analysis Service
**File**: `backend/services/analysis_service.py` (modify)

```python
class AnalysisService:
    """Service for content analysis operations."""

    async def extract_keywords(
        self,
        website_content_id: int,
        config: KeywordConfig,
    ) -> List[ExtractedKeyword]:
        """
        Extract keywords using configured method.

        Dispatches to appropriate extractor based on config.method.
        """
        content = await self._load_content(website_content_id)

        extractor = UniversalKeywordExtractor()
        keywords = await extractor.extract_keywords(
            text=content.text,
            language=content.language,
            config=config
        )

        # Save to database
        keyword_models = []
        for kw in keywords:
            keyword_model = ExtractedKeyword(
                website_content_id=website_content_id,
                word=kw.word,
                lemma=kw.lemma,
                frequency=kw.frequency,
                tfidf_score=kw.score,
                extraction_method=config.method,
                phrase_length=kw.word_count if hasattr(kw, 'word_count') else 1,
                pos_tag=kw.pos_tag if hasattr(kw, 'pos_tag') else None,
                language=content.language,
            )
            keyword_models.append(keyword_model)

        self.db.add_all(keyword_models)
        await self.db.commit()

        return keyword_models

    async def extract_entities(
        self,
        website_content_id: int,
        config: NERExtractionConfig,
    ) -> List[ExtractedNER]:
        """
        Extract named entities using configured method.
        """
        content = await self._load_content(website_content_id)

        if config.extraction_method == "transformer":
            extractor = TransformerNERExtractor()
        else:
            extractor = NamedEntityExtractor()

        entities = await extractor.extract_entities(
            text=content.text,
            language=content.language,
            entity_types=config.entity_types,
        )

        # Save to database (with deduplication)
        # ... implementation ...

        return entity_models
```

#### 3.6.2 Update Analysis Tasks
**File**: `backend/tasks/analysis_tasks.py` (modify)

Add new Celery tasks for batch keyword and NER extraction:
```python
@celery_app.task(name="analysis.extract_keywords_batch")
def extract_keywords_batch_task(
    website_content_ids: List[int],
    config: dict,
    user_id: int,
):
    """Extract keywords from multiple website contents in batch."""
    pass

@celery_app.task(name="analysis.extract_entities_batch")
def extract_entities_batch_task(
    website_content_ids: List[int],
    config: dict,
    user_id: int,
):
    """Extract named entities from multiple website contents in batch."""
    pass
```

---

### Phase 7: Testing & Documentation (4-5 hours)

#### 3.7.1 Unit Tests

**File**: `tests/test_keyword_extraction.py` (new)
- Test RAKE extraction with various n-gram lengths
- Test TF-IDF with bigrams and IDF weighting
- Test all_pos extraction
- Compare results with some2net reference implementation

**File**: `tests/test_ner_transformer.py` (new)
- Test transformer NER with English text
- Test transformer NER with Danish text
- Test entity type filtering
- Test confidence threshold

**File**: `tests/test_graphology_viz.py` (new)
- Test GEXF parsing with Graphology
- Test ForceAtlas2 layout application
- Test node filtering and search

#### 3.7.2 Integration Tests

**File**: `tests/integration/test_network_generation_v6.py` (new)
- Test website_keyword network with each extraction method
- Test website_ner network with both spaCy and transformer
- Verify network statistics and structure
- Test backward compatibility with website_noun networks

#### 3.7.3 Documentation Updates

**File**: `docs/KEYWORD_EXTRACTION_GUIDE.md` (new)
- Explain each extraction method
- Provide guidance on when to use each
- Include parameter tuning tips
- Show comparison examples

**File**: `docs/NER_NETWORKS_GUIDE.md` (new)
- Explain NER network type
- Document entity types
- Multilingual support details
- Performance considerations

**File**: `docs/GRAPHOLOGY_MIGRATION.md` (new)
- Document Vis.js → Graphology migration
- Breaking changes (if any)
- Performance comparison
- Troubleshooting guide

**File**: `docs/VERSION_6.0.0_SUMMARY.md` (new)
- Comprehensive release summary
- Feature comparison table
- Migration guide from v5.0.0

---

## 4. Backward Compatibility

### 4.1 Database Compatibility
- Existing `extracted_nouns` table renamed to `extracted_keywords` with migration
- `ExtractedNoun` kept as SQLAlchemy alias
- Default `extraction_method='noun'` for existing data

### 4.2 API Compatibility
- `website_noun` network type supported as alias for `website_keyword` with `method='noun'`
- Existing network generation requests work without changes
- Old network visualizations work with new Graphology renderer (GEXF format unchanged)

### 4.3 Frontend Compatibility
- Old `NetworkVisualizer` class kept for legacy support (optional)
- Feature flag to toggle between Vis.js and Graphology
- Graceful degradation if Graphology fails to load

---

## 5. Implementation Considerations

### 5.1 Performance Impact

| Component | Impact | Mitigation |
|-----------|--------|------------|
| Transformer NER | +2GB disk, +500MB RAM, 5-10x slower | Make optional, add feature flag, use GPU if available |
| RAKE extraction | +50ms per document | Cache results, batch processing |
| Bigram TF-IDF | +30% compute time | Optional feature, limit to top N bigrams |
| Graphology layout | Similar to Vis.js | Pre-compute layouts for large networks |

### 5.2 Deployment Considerations

**Docker Image Size**:
- Current: ~2.5GB
- With transformers: ~4.5GB
- Recommendation: Create separate `full` and `lite` images

**Environment Variables**:
```bash
# Feature flags
ENABLE_TRANSFORMER_NER=false  # Default: false to reduce dependencies
ENABLE_RAKE_EXTRACTION=true   # Default: true (lightweight)

# Performance tuning
NER_BATCH_SIZE=16             # Batch size for transformer NER
GRAPHOLOGY_LAYOUT_WORKERS=4   # Parallel layout workers
```

### 5.3 some2net Code Reuse

**Files to reference**:
1. `some2net/extraction.py` - RAKE and TF-IDF implementations
2. `some2net/ner_engine.py` - Transformer NER setup
3. `some2net/network_builder.py` - Network construction patterns
4. Visualization components - Graphology + Sigma.js integration

**Attribution**:
Add to all files that reuse some2net code:
```python
"""
Based on implementation from some2net (github.com/dimelab/some2net)
Copyright (c) [year] DIME Lab
Licensed under [license]
Adapted for Issue Observatory Search v6.0.0
"""
```

---

## 6. Success Criteria

### 6.1 Functional Requirements
- ✅ Graphology visualization renders all existing GEXF networks
- ✅ Four keyword extraction methods work correctly (noun, all_pos, tfidf, rake)
- ✅ NER extraction works for English and Danish
- ✅ Website → Keyword network generation with all methods
- ✅ Website → NER network generation
- ✅ UI provides configuration options for all methods
- ✅ Backward compatibility maintained for existing data and APIs

### 6.2 Performance Requirements
- Network visualization performance: similar or better than Vis.js
- Keyword extraction: <2s per document (excluding transformer NER)
- Transformer NER: <10s per document on CPU, <2s on GPU
- Network generation: <60s for 1000 nodes (with backboning)

### 6.3 Quality Requirements
- Test coverage: >80% for new modules
- Zero critical bugs in migration
- Documentation complete for all new features
- Code review passes from digital-methods-specialist

---

## 7. Timeline Estimate

| Phase | Description | Estimated Time | Dependencies |
|-------|-------------|----------------|--------------|
| 1 | Backend - Keyword Extraction | 4-6 hours | - |
| 2 | Backend - Database Schema | 2-3 hours | Phase 1 |
| 3 | Backend - Network Builders | 4-5 hours | Phase 1, 2 |
| 4 | Frontend - Graphology Migration | 6-8 hours | - |
| 5 | API Updates | 2-3 hours | Phase 1, 2, 3 |
| 6 | Analysis Service Updates | 3-4 hours | Phase 1, 2 |
| 7 | Testing & Documentation | 4-5 hours | All phases |
| **Total** | | **25-34 hours** | |

**Recommended Approach**: Implement in phases sequentially, with testing after each phase.

---

## 8. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Transformer dependencies bloat Docker image | High | High | Make optional, provide lite image |
| Graphology performance worse than Vis.js | Medium | Low | Benchmark early, fallback to Vis.js |
| some2net code incompatible with current architecture | Medium | Medium | Adapt patterns, don't copy verbatim |
| RAKE extraction too slow for large texts | Low | Medium | Add text truncation, caching |
| Breaking changes impact existing users | High | Low | Maintain backward compatibility, feature flags |

---

## 9. Open Questions

1. **Transformer NER**: Should this be mandatory or optional? Recommendation: Optional with feature flag.

2. **Graphology CDN**: Use CDN or bundle with application? Recommendation: CDN for faster loading.

3. **Backward compatibility**: Keep Vis.js as fallback or remove entirely? Recommendation: Remove after v6.1.0 stability confirmed.

4. **Migration path**: Auto-migrate existing networks or manual? Recommendation: Automatic on first load with user notification.

5. **some2net license**: Verify license compatibility. Check if attribution is required.

---

## 10. Next Steps

### Before Implementation
1. ✅ Review this plan with stakeholders
2. ⬜ Verify some2net license compatibility
3. ⬜ Set up development branch: `feature/v6.0.0-graphology-keywords`
4. ⬜ Create GitHub issues for each phase
5. ⬜ Benchmark current network generation performance (baseline)

### During Implementation
1. ⬜ Follow phases sequentially
2. ⬜ Commit after each major component
3. ⬜ Write tests alongside code
4. ⬜ Update documentation continuously
5. ⬜ Test with real data from v5.0.0

### After Implementation
1. ⬜ Full regression testing
2. ⬜ Performance benchmarking vs. v5.0.0
3. ⬜ User acceptance testing
4. ⬜ Deploy to staging environment
5. ⬜ Create migration guide for users
6. ⬜ Release v6.0.0

---

## 11. Conclusion

This implementation plan provides a comprehensive roadmap for migrating to Graphology/Sigma.js and enhancing keyword extraction capabilities based on the some2net library. The phased approach ensures:

- **Minimal disruption**: Backward compatibility maintained
- **Progressive enhancement**: New features optional
- **Quality assurance**: Testing integrated throughout
- **Clear documentation**: Users can leverage new capabilities

**Estimated Timeline**: 25-34 hours of development work

**Recommended Start**: After stakeholder approval and license verification

---

**Document Version**: 1.0
**Last Updated**: December 9, 2025
**Status**: DRAFT - Awaiting Approval
