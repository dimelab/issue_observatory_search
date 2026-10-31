/**
 * Network Visualization using Graphology + Sigma.js
 *
 * New in v6.0.0: Modern network visualization replacing Vis.js
 * Based on some2net visualization implementation.
 *
 * Features:
 * - ForceAtlas2 layout via Graphology Library
 * - Interactive rendering via Sigma.js
 * - GEXF file support
 * - Node coloring by type
 * - Search and filtering
 * - Performance optimized for large networks
 * - v6.0.0.3: Node size, giant component, and minimum degree filters (default size 0.5x)
 * - v6.0.0.4: GEXF attribute table parsing (typed values keyed by title), node types
 *   taken from the data, filters applied through Sigma reducers (the graph is built
 *   once, so layout positions survive filtering), idempotent layout loop
 * - v6.0.0.5: Node size from centrality (pagerank / eigenvector / degree), type or
 *   community colouring, labels toggle, PNG export that composites Sigma's layers
 */

// Attribute names the renderer owns; a GEXF attribute with one of these names is
// stored as attr_<name> instead so it can never override the rendering fields
// ('type' would select a Sigma node/edge program and break rendering).
const RESERVED_NODE_KEYS = new Set([
    'x', 'y', 'z', 'size', 'color', 'label', 'hidden', 'highlighted', 'forceLabel',
    'type', 'image', 'zIndex', 'baseSize', 'node_type'
]);
const RESERVED_EDGE_KEYS = new Set([
    'size', 'color', 'label', 'hidden', 'forceLabel', 'type', 'zIndex', 'weight'
]);

const NODE_TYPE_COLORS = {
    'search': '#3B82F6',      // Blue
    'query': '#3B82F6',       // Blue (search-website networks emit 'query')
    'website': '#10B981',     // Green
    'keyword': '#F59E0B',     // Amber (v6.0.0: renamed from noun)
    'noun': '#F59E0B',        // Amber (backward compat)
    'entity': '#8B5CF6',      // Purple (v6.0.0: for NER)
    'topic': '#EC4899',       // Pink
    'concept': '#EC4899',     // Pink
    'default': '#6B7280'      // Gray
};

// Base node size range (px before the user's size multiplier); sizes are derived
// from centrality in computeNodeSizes()
const NODE_SIZE_MIN = 5;
const NODE_SIZE_MAX = 30;

// What node size can be based on, in the order the UI lists them. Degree and
// betweenness are computed here from the graph; eigenvector and pagerank are read
// from the file (see "Node Metrics" in the network generation guide) and are only
// available when some node carries a value. pagerank is only offered when the file
// has it, which today means never: no builder makes directed graphs.
const SIZE_METRICS = [
    { id: 'degree', label: 'Degree', description: 'Number of connections' },
    { id: 'eigenvector', label: 'Eigenvector', description: 'Linked to well-connected nodes (scaled per component)' },
    { id: 'betweenness', label: 'Betweenness', description: 'Sits on many shortest paths between other nodes (unweighted)' },
    { id: 'pagerank', label: 'PageRank', description: 'Share of random-walk visits' }
];

// Betweenness runs on the main thread and grows with the square of the node count:
// about 0.1 s at 800 nodes, 1 s at 3,400 and 3.4 s at 6,000. Past this size the UI
// asks before computing it.
const BETWEENNESS_SLOW_NODES = 8000;

// Community colours: the backend numbers communities by size (0 = largest). Ranks
// beyond the palette, and nodes without a community, are drawn in the neutral colour.
const COMMUNITY_PALETTE = [
    '#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F',
    '#EDC948', '#B07AA1', '#FF9DA7', '#9C755F', '#17BECF'
];
const COMMUNITY_OTHER_COLOR = '#CBD5E1';

// Layout loop (animateLayout). Each animation frame refreshes Sigma once and runs as many
// ForceAtlas2 iterations as fit in the budget (an iteration costs about 1 ms at 800 nodes
// and 4 ms at 2,600), instead of one per frame. The budget is at least
// LAYOUT_FRAME_BUDGET_MS and follows the redraw time, so a slow renderer is not asked to
// redraw after every iteration. The layout converges: it stops by itself when two things
// hold. (1) Over LAYOUT_SETTLE_WINDOW iterations, the nodes of the main component moved on
// average less than LAYOUT_SETTLE_MOVE of the core's size per iteration (and at least
// LAYOUT_MIN_ITERATIONS have run). The core's size is the 5th-95th percentile range of the
// positions, not the bounding box: outliers keep drifting and inflate the box, which would
// make a layout that is still collapsing look settled. (2) The drawing's overall shape is
// steady: its two principal axes changed by less than LAYOUT_SHAPE_TOLERANCE over the last
// LAYOUT_SHAPE_SPAN iterations. Without (2) a chain or strip, which stretches slowly, would
// be stopped part way: its nodes move little per iteration, but the movement adds up.
const LAYOUT_FRAME_BUDGET_MS = 10;
const LAYOUT_MAX_FRAME_BUDGET_MS = 40;  // the budget grows with the time a redraw takes, up to this
const LAYOUT_MAX_ITERATIONS_PER_FRAME = 40;
const LAYOUT_SETTLE_WINDOW = 50;
const LAYOUT_SETTLE_MOVE = 0.0005;
const LAYOUT_MIN_ITERATIONS = 100;
const LAYOUT_SHAPE_SPAN = 200;
const LAYOUT_SHAPE_TOLERANCE = 0.05;

// Small connected components (say a few sites that share one keyword) feel only the big
// core's repulsion and ForceAtlas2's constant gravity, so they drift far out and, because the
// view fits the whole drawing, shrink the core on screen. Gephi has the same behaviour. With
// keepComponentsNear (on in the organic style) every layout frame moves a component back, as a whole,
// when its edge would lie further than LAYOUT_COMPONENT_REACH x the main component's radius
// (95th percentile of the distance from its centre) from the main component's centre.
// This only applies when the main component holds at least LAYOUT_MAIN_SHARE of the nodes;
// in a network of many similar-sized pieces there is no main one to gather them around.
const LAYOUT_COMPONENT_REACH = 1.3;
const LAYOUT_MAIN_SHARE = 0.5;

// The two layout styles the Layout switch chooses between (each is a function of the node
// count). Compact, the default, uses strong gravity: gravity that grows with the distance from
// the centre keeps every network close, settled and filling the view, but makes it round
// whatever its structure. Organic is Gephi's ForceAtlas2 defaults (plain gravity, scaling 2
// from 100 nodes, 10 below): the shape follows the data. Small components are held near the
// main cluster there, because plain gravity lets them drift far out.
const LAYOUT_STYLES = {
    compact: () => ({ strongGravityMode: true, gravity: 1.0, scalingRatio: 10, keepComponentsNear: false }),
    organic: (nodes) => ({
        strongGravityMode: false,
        gravity: 1.0,
        scalingRatio: nodes >= 100 ? 2 : 10,
        keepComponentsNear: true
    })
};

// Label spreading (setAllLabels). Sigma's default label renderer draws the text
// LABEL_GAP px right of the node's edge with its baseline labelSize / 3 below the
// centre; LABEL_PADDING is the space kept between two label boxes.
const LABEL_GAP = 3;
const LABEL_PADDING = 3;
// Boxes are compared with LABEL_PADDING / 2 added on every side; an overlap of this many
// px or less in that padded space still leaves a gap on screen, so it is not pushed
// apart (this is what lets the relaxation finish instead of creeping towards 0)
const LABEL_OVERLAP_TOLERANCE = 1;
const LABEL_SPREAD_MAX_ITERATIONS = 2000;
const LABEL_SPREAD_TIME_BUDGET_MS = 2500;
// Stage 1 of the spread inflates the whole layout about its centre until at most this
// many overlapping pairs per node remain (never beyond LABEL_SPREAD_MAX_INFLATION times
// the current size); stage 2 pushes the remaining overlaps apart locally.
const LABEL_SPREAD_TARGET_OVERLAPS_PER_NODE = 1.5;
const LABEL_SPREAD_MAX_INFLATION = 12;
// Moves in stage 2 are multiplied by this (successive over-relaxation). On a dense
// 835-node layout it needs about 340 passes at 1.9, 670 at 1.6 and 1,450 at 1.3; it must
// stay below 2, where a push would overshoot as far as it corrects.
const LABEL_SPREAD_RELAXATION = 1.8;

// Louvain community detection in the browser (see detectCommunities). Same seed as the
// backend (backend/core/networks/metrics.py), so a given network gives a stable result.
const COMMUNITY_SEED = 42;

/**
 * Small seeded random number generator (mulberry32) for repeatable Louvain runs
 */
function seededRandom(seed) {
    let state = seed >>> 0;
    return () => {
        state = (state + 0x6D2B79F5) | 0;
        let t = Math.imul(state ^ (state >>> 15), 1 | state);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

// Sigma canvas layers composited by exportAsPNG, bottom to top (hover/mouse layers
// are interaction overlays and stay out of the export)
const EXPORT_CANVAS_LAYERS = ['edges', 'edgeLabels', 'nodes', 'labels'];

// Unknown types get a stable colour from this palette (hash of the type name)
const FALLBACK_TYPE_PALETTE = [
    '#06B6D4', '#F97316', '#84CC16', '#EF4444', '#A16207', '#0D9488', '#0EA5E9', '#D946EF'
];

const NODE_TYPE_LABELS = {
    'search': 'Searches',
    'query': 'Queries',
    'website': 'Websites',
    'keyword': 'Keywords',
    'noun': 'Nouns',
    'entity': 'Entities',
    'topic': 'Topics',
    'concept': 'Concepts',
    'default': 'Other'
};

class GraphologyNetworkVisualizer {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);

        if (!this.container) {
            console.error('Container not found:', containerId);
            return;
        }

        // Create Graphology graph
        this.graph = new graphology.Graph({ type: 'undirected' });
        this.renderer = null;
        this.layoutIsRunning = false;
        this.layoutAnimationFrame = null;
        this.autoStopLayout = true;       // stop by itself once the layout settled (see LAYOUT_SETTLE_MOVE)
        this.keepComponentsNear = false;  // pull small components back towards the main one (see LAYOUT_COMPONENT_REACH); on in the organic style
        this.layoutComponents = [];       // node ids per connected component, largest first
        this.componentIndex = new Map();  // node id -> index in layoutComponents
        this.layoutIterations = 0;        // iterations run since the layout was last started
        this.layoutItersPerFrame = 1;     // adapts to what fits in the frame budget
        this.layoutRenderMs = 0;          // recent redraw time (moving average)
        this.layoutStartedAt = 0;
        this.settleWindow = null;         // positions at the start of the current settle window
        this.axisHistory = [];            // principal axis lengths at the end of each settle window

        // Configuration (similar to some2net)
        this.options = {
            fa2Settings: {
                adjustSizes: false,
                barnesHutOptimize: true,
                barnesHutTheta: 1.2,
                edgeWeightInfluence: 1.0,
                gravity: 1.0,
                scalingRatio: 10,
                slowDown: 1,  // replaced by 1 + ln(nodes) when a graph is loaded (tuneLayoutForGraph)
                linLogMode: false,
                // The compact style (see LAYOUT_STYLES): strong gravity grows with the distance from
                // the centre, so small subgraphs stay near, the layout settles and fills the view;
                // the price is a round shape whatever the structure. Off is classic ForceAtlas2 (organic).
                strongGravityMode: true,
                ...(options.fa2Settings || {})
            },
            sigma: {
                renderEdgeLabels: false,
                defaultNodeColor: '#999',
                defaultEdgeColor: '#ccc',
                labelSize: 14,
                labelWeight: 'bold',
                labelColor: { color: '#000' },
                ...(options.sigma || {})
            }
        };

        // State
        this.selectedNode = null;
        this.nodeSizeMultiplier = 0.5; // Node size control (0.1-3.0, default 0.5x)
        this.colorMode = 'type';       // 'type' | 'community'
        this.labelsVisible = true;
        this.allLabels = false;        // label every visible node, whatever the zoom
        this.labelSpreadInfo = null;   // result of the spread done when allLabels was switched on
        this.spreadSnapshot = null;    // { positions: Map(node -> { x, y }), sizeCorrection } from before the spread, for undo
        this.viewSizeCorrection = 1;   // keeps node circles the same size on screen after a spread zoomed the camera in
        this.filters = {
            nodeTypes: [],
            search: '',
            giantComponentOnly: false,
            minDegree: 0  // Minimum node degree filter
        };

        // Filtering never touches the graph: applyFilters() recomputes these and the
        // Sigma reducers hide whatever is in hiddenNodes.
        this.hiddenNodes = new Set();
        this.visibleStats = { nodes: 0, edges: 0 };
        this.typeCounts = [];  // [{ type, count }] for the types present in the loaded file
        this.typeColorCache = new Map();

        // Node sizes are derived, never written to the graph: computeNodeSizes() fills
        // baseSizes over ALL nodes at load (so sizes are stable under filters) and the
        // node reducer multiplies by the size slider.
        this.sizeMetric = 'degree';  // an id from SIZE_METRICS
        this.baseSizes = new Map();
        this.metricData = { eigenvector: false, pagerank: false };  // which file metrics exist
        this.betweennessScores = null;  // Map(node -> raw score), computed on first use
        this.communityData = false;  // any node with a numeric community in the file
        // `community` on the nodes is what is drawn. It starts as the file's communities
        // (kept in fileCommunities) and is replaced by a browser Louvain run on the visible
        // nodes when the colours are asked for after the filters changed.
        this.fileCommunities = new Map();   // node -> community rank from the file
        this.communityHidden = new Set();   // hidden nodes when `community` was last assigned
        this.communityInfo = null;          // { source: 'file' | 'browser', nodes, communities, ms }

        // Initialize
        this.init();
    }

    /**
     * Initialize Sigma.js renderer with Graphology graph
     */
    init() {
        try {
            // Create Sigma renderer. The reducers are the single place where
            // per-node / per-edge display data is derived from graph state.
            this.renderer = new Sigma(this.graph, this.container, {
                ...this.options.sigma,
                renderLabels: this.labelsVisible,
                nodeReducer: (node, data) => ({
                    ...data,
                    size: (this.baseSizes.get(node) || NODE_SIZE_MIN) * this.nodeSizeMultiplier * this.viewSizeCorrection,
                    color: this.colorMode === 'community'
                        ? this.getCommunityColor(data.community)
                        : data.color,
                    hidden: this.hiddenNodes.has(node),
                    forceLabel: this.allLabels
                }),
                edgeReducer: (edge, data) => {
                    const [source, target] = this.graph.extremities(edge);
                    return this.hiddenNodes.has(source) || this.hiddenNodes.has(target)
                        ? { ...data, hidden: true }
                        : data;
                }
            });

            // Setup event listeners
            this.setupEventListeners();
        } catch (error) {
            console.error('Error initializing Sigma renderer:', error);
        }
    }

    /**
     * Setup event listeners for network interactions
     */
    setupEventListeners() {
        if (!this.renderer) return;

        // Node click
        this.renderer.on('clickNode', ({ node }) => {
            try {
                this.selectedNode = this.buildSelectedNode(node);
                this.onNodeSelect(this.selectedNode);
            } catch (error) {
                console.error('Error handling node click:', error);
            }
        });

        // Background click (deselect)
        this.renderer.on('clickStage', () => {
            this.selectedNode = null;
            this.onNodeDeselect();
        });

        // Double click to focus
        this.renderer.on('doubleClickNode', ({ node }) => {
            this.focusNode(node);
        });
    }

    /**
     * Request headers for the GEXF fetch. The access_token cookie authenticates page
     * sessions; a Bearer header is only added when a token exists, because a header
     * (even an invalid one) takes precedence over the cookie on the server.
     */
    getAuthHeaders() {
        const headers = {};
        try {
            const token = localStorage.getItem('token');
            if (token) {
                headers['Authorization'] = 'Bearer ' + token;
            }
        } catch (error) {
            // localStorage unavailable (private mode etc.) - rely on the cookie
        }
        return headers;
    }

    /**
     * Load and parse GEXF file
     */
    async loadFromGEXF(url) {
        try {
            const response = await fetch(url, {
                headers: this.getAuthHeaders(),
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error('Failed to load network file');
            }

            const gexfText = await response.text();
            await this.parseGEXF(gexfText);

        } catch (error) {
            console.error('Error loading GEXF:', error);
            if (typeof showToast === 'function') {
                showToast('Failed to load network', 'error');
            }
        }
    }

    /**
     * Parse GEXF and populate Graphology graph (built once; filters work on top of it)
     */
    async parseGEXF(gexfText) {
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(gexfText, 'text/xml');

        // Check for parsing errors
        const parserError = xmlDoc.querySelector('parsererror');
        if (parserError) {
            throw new Error('Invalid GEXF format');
        }

        // Reset state from any previous load
        this.stopLayout();
        this.graph.clear();
        this.selectedNode = null;

        // <attributes class="node|edge"> tables map attvalue ids to titles and types
        const nodeAttrDefs = this.parseAttributeDefinitions(xmlDoc, 'node');
        const edgeAttrDefs = this.parseAttributeDefinitions(xmlDoc, 'edge');

        const radius = 100;
        const typeCounts = new Map();
        let skippedNodes = 0;
        let skippedEdges = 0;

        // Parse nodes
        const xmlNodes = xmlDoc.querySelectorAll('node');
        xmlNodes.forEach((xmlNode, index) => {
            const id = xmlNode.getAttribute('id');
            if (id === null || this.graph.hasNode(id)) {
                skippedNodes++;
                return;
            }
            const label = xmlNode.getAttribute('label') || id;

            // Parse attributes (keyed by title, cast to their declared type)
            const attributes = this.parseAttributes(xmlNode, nodeAttrDefs);
            const nodeType = String(attributes.node_type || attributes.type || 'default');
            typeCounts.set(nodeType, (typeCounts.get(nodeType) || 0) + 1);

            // Use the position from the GEXF viz namespace if present, otherwise place
            // the node on a circle (initial layout before ForceAtlas2)
            let x, y;
            const vizPosition = xmlNode.querySelector('viz\\:position, position');
            if (vizPosition) {
                x = parseFloat(vizPosition.getAttribute('x'));
                y = parseFloat(vizPosition.getAttribute('y'));
            }
            if (!Number.isFinite(x) || !Number.isFinite(y)) {
                const angle = (2 * Math.PI * index) / xmlNodes.length;
                x = Math.cos(angle) * radius;
                y = Math.sin(angle) * radius;
            }

            const nodeAttrs = {
                label: String(label),
                color: this.getNodeColor(nodeType),
                node_type: nodeType,
                x,
                y
            };

            // Keep the remaining GEXF attributes (community, eigenvector, weight, ...)
            // without letting them override the rendering fields above
            Object.keys(attributes).forEach(key => {
                if (key === 'node_type') return;
                nodeAttrs[RESERVED_NODE_KEYS.has(key) ? `attr_${key}` : key] = attributes[key];
            });

            this.graph.addNode(id, nodeAttrs);
        });

        // Parse edges
        xmlDoc.querySelectorAll('edge').forEach(xmlEdge => {
            const source = xmlEdge.getAttribute('source');
            const target = xmlEdge.getAttribute('target');

            if (!this.graph.hasNode(source) || !this.graph.hasNode(target)) {
                skippedEdges++;
                return;
            }

            const attributes = this.parseAttributes(xmlEdge, edgeAttrDefs);
            const edgeAttrs = {
                weight: Number(xmlEdge.getAttribute('weight')) || Number(attributes.weight) || 1
            };
            Object.keys(attributes).forEach(key => {
                if (key === 'weight') return;
                edgeAttrs[RESERVED_EDGE_KEYS.has(key) ? `attr_${key}` : key] = attributes[key];
            });

            try {
                this.graph.addEdge(source, target, edgeAttrs);
            } catch (error) {
                // Duplicate edge in an undirected, non-multi graph
                skippedEdges++;
            }
        });

        if (skippedNodes > 0 || skippedEdges > 0) {
            console.warn(`GEXF: skipped ${skippedNodes} nodes and ${skippedEdges} edges (duplicates or dangling)`);
        }

        this.typeCounts = [...typeCounts.entries()]
            .map(([type, count]) => ({ type, count }))
            .sort((a, b) => b.count - a.count);

        this.computeNodeSizes();

        this.tuneLayoutForGraph();

        // A new graph has no label spread to undo
        this.allLabels = false;
        this.labelSpreadInfo = null;
        this.spreadSnapshot = null;
        this.viewSizeCorrection = 1;

        // Communities from the file cover the whole graph; remember them so clearing the
        // filters can bring them back after a browser run on a filtered view
        this.fileCommunities = new Map();
        this.graph.forEachNode((node, attributes) => {
            if (Number.isFinite(attributes.community)) this.fileCommunities.set(node, attributes.community);
        });
        this.communityData = this.fileCommunities.size > 0;
        this.communityHidden = new Set();
        this.communityInfo = this.communityData ? this.describeFileCommunities() : null;

        // Layout is not run on load - the user starts it with the Start Layout button
        // (matches some2net behaviour)

        // Re-apply current filters to the new graph and render
        this.applyFilters();

        // Colouring by community needs communities for the current view
        if (this.colorMode === 'community' && !(this.hasCommunities() && this.ensureCommunities())) {
            this.colorMode = 'type';
        }

        // Fit to viewport
        setTimeout(() => this.fit(), 100);
    }

    /**
     * Pick the starting size metric for a freshly loaded graph and derive base sizes.
     * pagerank if any node has one, else eigenvector, else full-graph degree; the user
     * can change it afterwards with setSizeMetric().
     */
    computeNodeSizes() {
        this.baseSizes = new Map();
        this.betweennessScores = null;
        this.metricData = {
            eigenvector: this.graph.someNode((node, attributes) => Number.isFinite(attributes.eigenvector)),
            pagerank: this.graph.someNode((node, attributes) => Number.isFinite(attributes.pagerank))
        };
        this.sizeMetric = this.metricData.pagerank ? 'pagerank'
            : this.metricData.eigenvector ? 'eigenvector'
            : 'degree';
        this.applySizeMetric();
    }

    /**
     * Derive every node's base size from the current metric, over ALL nodes of the
     * loaded graph (never the filtered subset), so sizes stay stable while filtering.
     *
     * Scores are min-max scaled and mapped with a square root to
     * NODE_SIZE_MIN..NODE_SIZE_MAX so hubs stand out without flattening everything
     * else. The displayed size is base size * size multiplier.
     */
    applySizeMetric() {
        this.baseSizes = new Map();
        if (this.graph.order === 0) return;

        const scores = this.scoreNodes(this.sizeMetric);
        let min = Infinity;
        let max = -Infinity;
        scores.forEach(score => {
            min = Math.min(min, score);
            max = Math.max(max, score);
        });

        scores.forEach((score, node) => {
            const t = max > min ? (score - min) / (max - min) : 0;
            this.baseSizes.set(node, NODE_SIZE_MIN + (NODE_SIZE_MAX - NODE_SIZE_MIN) * Math.sqrt(t));
        });
    }

    /**
     * Raw centrality score of every node for one metric: Map(node -> number)
     */
    scoreNodes(metric) {
        const scores = new Map();

        if (metric === 'betweenness') {
            return this.getBetweennessScores();
        }

        if (metric === 'eigenvector') {
            // Eigenvector values are L2-normalised within each connected component, so a
            // 2-node component scores 0.707 per node, which would outrank the hub of a
            // 1000-node giant component (typically ~0.1). Weighting by sqrt(n_c / N)
            // gives each component a share of the squared mass proportional to its node
            // count. Nodes without a `component` attribute share one group, so a file
            // with none is a single component and the weight is 1.
            const componentOf = attributes => (Number.isFinite(attributes.component) ? attributes.component : null);
            const componentCounts = new Map();
            this.graph.forEachNode((node, attributes) => {
                const component = componentOf(attributes);
                componentCounts.set(component, (componentCounts.get(component) || 0) + 1);
            });
            this.graph.forEachNode((node, attributes) => {
                const eigenvector = Number.isFinite(attributes.eigenvector) ? attributes.eigenvector : 0;
                scores.set(node, eigenvector * Math.sqrt(componentCounts.get(componentOf(attributes)) / this.graph.order));
            });
            return scores;
        }

        // pagerank and degree are comparable across the whole graph and are not scaled
        this.graph.forEachNode((node, attributes) => {
            if (metric === 'pagerank') {
                scores.set(node, Number.isFinite(attributes.pagerank) ? attributes.pagerank : 0);
            } else {
                scores.set(node, this.graph.degree(node));
            }
        });
        return scores;
    }

    /**
     * Betweenness centrality of every node, computed once per loaded graph. Unweighted
     * on purpose: edge weights here are association strengths (higher = closer), while
     * shortest-path code reads weights as distances.
     */
    getBetweennessScores() {
        if (!this.betweennessScores) {
            const betweenness = this.getBetweennessFunction();
            if (!betweenness) throw new Error('Betweenness centrality is not available');
            const raw = betweenness(this.graph, { getEdgeWeight: null, normalized: false });
            this.betweennessScores = new Map(Object.entries(raw));
        }
        return this.betweennessScores;
    }

    /**
     * graphology-metrics' betweenness function, or null if the library is missing it
     */
    getBetweennessFunction() {
        if (typeof graphologyLibrary === 'undefined') return null;
        const metrics = graphologyLibrary.metrics;
        return (metrics && metrics.centrality && metrics.centrality.betweenness) || null;
    }

    /**
     * Read the <attributes class="..."> tables of a GEXF document.
     * Returns Map(attribute id -> { title, type }).
     */
    parseAttributeDefinitions(xmlDoc, attrClass) {
        const definitions = new Map();
        xmlDoc.querySelectorAll('attributes').forEach(table => {
            if (table.getAttribute('class') !== attrClass) return;
            table.querySelectorAll('attribute').forEach(attr => {
                const id = attr.getAttribute('id');
                if (id === null) return;
                definitions.set(id, {
                    title: attr.getAttribute('title') || id,
                    type: (attr.getAttribute('type') || 'string').toLowerCase()
                });
            });
        });
        return definitions;
    }

    /**
     * Parse <attvalue> children of a GEXF node/edge element.
     * Values are keyed by attribute title and cast to the declared type; without an
     * attribute table the raw `for` key and string value are used.
     */
    parseAttributes(xmlElement, definitions) {
        const attributes = Object.create(null);
        xmlElement.querySelectorAll('attvalue').forEach(attr => {
            const ref = attr.getAttribute('for') ?? attr.getAttribute('id');
            if (ref === null) return;

            const definition = definitions.get(ref);
            const value = definition
                ? this.castAttributeValue(attr.getAttribute('value'), definition.type)
                : attr.getAttribute('value');
            if (value !== null) {
                attributes[definition ? definition.title : ref] = value;
            }
        });
        return attributes;
    }

    /**
     * Cast a GEXF attvalue string to its declared type (null = unusable value)
     */
    castAttributeValue(raw, type) {
        switch (type) {
            case 'integer':
            case 'int':
            case 'long':
            case 'float':
            case 'double': {
                if (raw === null || raw === '') return null;
                const number = Number(raw);
                return Number.isFinite(number) ? number : null;
            }
            case 'boolean':
                return raw === 'true' || raw === '1';
            default:
                return raw;
        }
    }

    /**
     * Run ForceAtlas2 layout using graphology-library (continuous)
     * Uses synchronous layoutForceAtlas2 to avoid Web Worker issues.
     * Safe to call repeatedly: only one animation loop ever exists.
     *
     * The layout always runs on the full graph, including nodes hidden by filters, so
     * positions stay consistent when filters change or are cleared.
     */
    startLayout() {
        if (this.layoutIsRunning) return;

        if (typeof graphologyLibrary === 'undefined' ||
            !graphologyLibrary.layoutForceAtlas2 ||
            !graphologyLibrary.layoutForceAtlas2.assign) {
            console.warn('ForceAtlas2 layout not available');
            return;
        }

        // The layout moves every node, so the positions saved by the label spread are stale
        this.spreadSnapshot = null;
        this.layoutIterations = 0;
        this.layoutItersPerFrame = 1;
        this.layoutRenderMs = 0;
        this.layoutStartedAt = performance.now();
        this.settleWindow = null;
        this.axisHistory = [];
        this.layoutIsRunning = true;
        this.onLayoutStateChange(true);
        this.layoutAnimationFrame = requestAnimationFrame(() => this.animateLayout());
    }

    /**
     * Animation loop for the layout: runs as many synchronous ForceAtlas2 iterations as fit
     * in LAYOUT_FRAME_BUDGET_MS, refreshes Sigma once, and stops by itself when the layout
     * has settled (see LAYOUT_SETTLE_MOVE).
     */
    animateLayout() {
        if (!this.layoutIsRunning) return;

        try {
            // Settings are read fresh on every call, so slider changes apply on the next frame
            const iterations = this.layoutItersPerFrame;
            const started = performance.now();
            graphologyLibrary.layoutForceAtlas2.assign(this.graph, {
                iterations,
                settings: this.options.fa2Settings
            });
            if (this.keepComponentsNear) this.pullInSmallComponents();
            const layoutMs = performance.now() - started;
            this.layoutIterations += iterations;

            // Refresh renderer
            const drawStarted = performance.now();
            this.renderer.refresh();
            const drawMs = performance.now() - drawStarted;
            this.layoutRenderMs = this.layoutRenderMs ? 0.7 * this.layoutRenderMs + 0.3 * drawMs : drawMs;

            // Next frame's iteration count. Every assign call has a fixed set-up cost, so the
            // cost of one iteration cannot be read from a one-iteration call: grow while
            // there is room in the budget, shrink in proportion when over it.
            const budget = Math.min(LAYOUT_MAX_FRAME_BUDGET_MS, Math.max(LAYOUT_FRAME_BUDGET_MS, this.layoutRenderMs));
            if (layoutMs < budget * 0.7) {
                this.layoutItersPerFrame = Math.min(
                    LAYOUT_MAX_ITERATIONS_PER_FRAME,
                    Math.max(iterations + 1, Math.ceil(iterations * 1.5))
                );
            } else if (layoutMs > budget * 1.2) {
                this.layoutItersPerFrame = Math.max(1, Math.floor(iterations * budget / layoutMs));
            }

            if (this.autoStopLayout && this.layoutHasSettled(iterations)) {
                const result = {
                    iterations: this.layoutIterations,
                    ms: Math.round(performance.now() - this.layoutStartedAt)
                };
                this.stopLayout();
                this.onLayoutSettled(result);
                return;
            }

            // Schedule next frame
            this.layoutAnimationFrame = requestAnimationFrame(() => this.animateLayout());
        } catch (error) {
            console.error('Error in layout animation:', error);
            this.stopLayout();
        }
    }

    /**
     * Whether the layout has stopped changing: compares node positions at the start and
     * end of each window of LAYOUT_SETTLE_WINDOW iterations. Called once per frame with
     * the number of iterations that frame ran. Only the main component is judged: small
     * components held at the edge of their allowed zone keep sliding along it, which is
     * not a layout that is still changing.
     */
    layoutHasSettled(iterations) {
        const nodes = this.mainComponent() || this.graph.nodes();
        const capture = () => {
            const x = new Float64Array(nodes.length);
            const y = new Float64Array(nodes.length);
            nodes.forEach((node, index) => {
                x[index] = this.graph.getNodeAttribute(node, 'x');
                y[index] = this.graph.getNodeAttribute(node, 'y');
            });
            return { x, y, iterations: 0 };
        };

        if (!this.settleWindow) {
            this.settleWindow = capture();
            return false;
        }
        this.settleWindow.iterations += iterations;
        if (this.settleWindow.iterations < LAYOUT_SETTLE_WINDOW) return false;

        const { x, y, iterations: windowIterations } = this.settleWindow;
        let moved = 0;
        const xs = [];
        const ys = [];
        nodes.forEach((node, index) => {
            const nodeX = this.graph.getNodeAttribute(node, 'x');
            const nodeY = this.graph.getNodeAttribute(node, 'y');
            moved += Math.hypot(nodeX - x[index], nodeY - y[index]);
            xs.push(nodeX);
            ys.push(nodeY);
        });

        // Shape: compare the principal axes with those LAYOUT_SHAPE_SPAN iterations ago
        const axes = this.principalAxes(xs, ys);
        this.axisHistory.push({ iterations: this.layoutIterations, ...axes });
        const reference = [...this.axisHistory].reverse()
            .find((entry) => entry.iterations <= this.layoutIterations - LAYOUT_SHAPE_SPAN);
        const change = (now, before) => Math.abs(now - before) / (before || 1);
        const shapeSteady = Boolean(reference) &&
            change(axes.major, reference.major) < LAYOUT_SHAPE_TOLERANCE &&
            change(axes.minor, reference.minor) < LAYOUT_SHAPE_TOLERANCE;

        xs.sort((a, b) => a - b);
        ys.sort((a, b) => a - b);
        const low = Math.floor((xs.length - 1) * 0.05);
        const high = Math.floor((xs.length - 1) * 0.95);
        const coreSize = Math.max(xs[high] - xs[low], ys[high] - ys[low]) || 1;
        const perIteration = moved / nodes.length / windowIterations / coreSize;

        this.settleWindow = capture();
        return this.layoutIterations >= LAYOUT_MIN_ITERATIONS && perIteration < LAYOUT_SETTLE_MOVE && shapeSteady;
    }

    /**
     * Lengths of the two principal axes of a point cloud (standard deviation along the
     * longest direction and along the one at right angles to it)
     */
    principalAxes(xs, ys) {
        const count = xs.length;
        const meanX = xs.reduce((sum, value) => sum + value, 0) / count;
        const meanY = ys.reduce((sum, value) => sum + value, 0) / count;
        let varianceX = 0;
        let varianceY = 0;
        let covariance = 0;
        for (let i = 0; i < count; i++) {
            const dx = xs[i] - meanX;
            const dy = ys[i] - meanY;
            varianceX += dx * dx;
            varianceY += dy * dy;
            covariance += dx * dy;
        }
        const half = (varianceX + varianceY) / 2;
        const spread = Math.sqrt(Math.max(0, ((varianceX - varianceY) / 2) ** 2 + covariance * covariance));
        return {
            major: Math.sqrt((half + spread) / count),
            minor: Math.sqrt(Math.max(0, half - spread) / count)
        };
    }

    /**
     * Stop ForceAtlas2 layout
     */
    stopLayout() {
        if (this.layoutAnimationFrame) {
            cancelAnimationFrame(this.layoutAnimationFrame);
            this.layoutAnimationFrame = null;
        }
        if (this.layoutIsRunning) {
            this.layoutIsRunning = false;
            this.onLayoutStateChange(false);
        }
    }

    /**
     * Whether the layout stops by itself once it has settled. Off: it runs until stopped.
     */
    setAutoStopLayout(enabled) {
        this.autoStopLayout = Boolean(enabled);
        this.settleWindow = null;  // start measuring afresh
        this.axisHistory = [];
    }

    getAutoStopLayout() {
        return this.autoStopLayout;
    }

    /**
     * Whether small components are pulled back towards the main one while the layout runs
     * (see LAYOUT_COMPONENT_REACH). Off: they drift as far as ForceAtlas2 pushes them.
     */
    setKeepComponentsNear(enabled) {
        this.keepComponentsNear = Boolean(enabled);
    }

    getKeepComponentsNear() {
        return this.keepComponentsNear;
    }

    /**
     * The ForceAtlas2 settings in use (the slow-down is set per graph on load)
     */
    getLayoutSettings() {
        return { ...this.options.fa2Settings };
    }

    /**
     * The layout style the current settings amount to: a key of LAYOUT_STYLES, or 'custom'
     * when a setting was changed by hand. Edge weight and Barnes-Hut do not count.
     */
    getLayoutStyle() {
        const settings = this.options.fa2Settings;
        for (const [name, preset] of Object.entries(LAYOUT_STYLES)) {
            const wanted = preset(this.graph.order);
            if (settings.strongGravityMode === wanted.strongGravityMode &&
                settings.gravity === wanted.gravity &&
                settings.scalingRatio === wanted.scalingRatio &&
                this.keepComponentsNear === wanted.keepComponentsNear) {
                return name;
            }
        }
        return 'custom';
    }

    /**
     * Switch to a layout style ('compact' or 'organic'; see LAYOUT_STYLES). Takes effect on
     * the next layout frame; the caller starts the layout if it is stopped.
     */
    setLayoutStyle(name) {
        if (!LAYOUT_STYLES[name]) return;
        const { keepComponentsNear, ...settings } = LAYOUT_STYLES[name](this.graph.order);
        this.options.fa2Settings = { ...this.options.fa2Settings, ...settings };
        this.keepComponentsNear = keepComponentsNear;
        this.settleWindow = null;  // start measuring afresh
        this.axisHistory = [];
    }

    /**
     * Set what depends on the loaded graph:
     * - the ForceAtlas2 slow-down, 1 + ln(nodes): ForceAtlas2's own recommendation, which
     *   gives smoother convergence on larger graphs
     * - the settings of the current layout style (the organic one scales by node count)
     * - the connected components, used by keepComponentsNear and the settle check
     */
    tuneLayoutForGraph() {
        const nodes = Math.max(this.graph.order, 1);
        this.options.fa2Settings.slowDown = 1 + Math.log(nodes);
        const style = this.getLayoutStyle();
        if (style !== 'custom') this.setLayoutStyle(style);
        this.layoutComponents = this.findComponents();
    }

    /**
     * The node ids of the main component, or null when there is no single main one: the
     * graph is connected (nothing to gather), or its largest component holds less than
     * LAYOUT_MAIN_SHARE of the nodes
     */
    mainComponent() {
        const components = this.layoutComponents;
        if (components.length < 2) return null;
        return components[0].length >= LAYOUT_MAIN_SHARE * this.graph.order ? components[0] : null;
    }

    /**
     * Connected components of the full graph as arrays of node ids, largest first
     */
    findComponents() {
        const seen = new Set();
        const components = [];
        this.graph.forEachNode((start) => {
            if (seen.has(start)) return;
            const members = [start];
            seen.add(start);
            for (let head = 0; head < members.length; head++) {
                this.graph.forEachNeighbor(members[head], (neighbor) => {
                    if (!seen.has(neighbor)) {
                        seen.add(neighbor);
                        members.push(neighbor);
                    }
                });
            }
            components.push(members);
        });
        components.sort((a, b) => b.length - a.length);
        this.componentIndex = new Map();
        components.forEach((members, index) => members.forEach((node) => this.componentIndex.set(node, index)));
        return components;
    }

    /**
     * Move every component other than the main one back, as a whole, when it lies further
     * from the main component than LAYOUT_COMPONENT_REACH x the main component's radius
     * (measured to the component's near edge, so two components of similar size do not
     * overlap). Then put the main component's centre on the origin: the small components
     * crowd one side of it and push it away, and without this the whole drawing would
     * keep drifting in that direction. Called after each batch of layout iterations; one
     * batched update of the positions.
     */
    pullInSmallComponents() {
        const components = this.layoutComponents;
        if (!this.mainComponent()) return;

        const centreOf = (nodes) => {
            let sumX = 0;
            let sumY = 0;
            nodes.forEach((node) => {
                sumX += this.graph.getNodeAttribute(node, 'x');
                sumY += this.graph.getNodeAttribute(node, 'y');
            });
            return { x: sumX / nodes.length, y: sumY / nodes.length };
        };
        // 95th percentile of the distance from the centre
        const radiusAround = (nodes, centre) => {
            const distances = nodes.map((node) => Math.hypot(
                this.graph.getNodeAttribute(node, 'x') - centre.x,
                this.graph.getNodeAttribute(node, 'y') - centre.y
            ));
            distances.sort((a, b) => a - b);
            return distances[Math.floor((distances.length - 1) * 0.95)];
        };

        const mainCentre = centreOf(components[0]);
        const limit = LAYOUT_COMPONENT_REACH * radiusAround(components[0], mainCentre);

        // Per component: how far it moves (null = stays where it is)
        const shifts = new Array(components.length).fill(null);
        for (let i = 1; i < components.length; i++) {
            const centre = centreOf(components[i]);
            const dx = centre.x - mainCentre.x;
            const dy = centre.y - mainCentre.y;
            const distance = Math.hypot(dx, dy);
            const reach = limit + radiusAround(components[i], centre);
            if (distance > reach) {
                const shift = reach / distance - 1;  // negative: towards the main component
                shifts[i] = [dx * shift, dy * shift];
            }
        }

        this.graph.updateEachNodeAttributes((node, attributes) => {
            const shift = shifts[this.componentIndex.get(node)];
            attributes.x += (shift ? shift[0] : 0) - mainCentre.x;
            attributes.y += (shift ? shift[1] : 0) - mainCentre.y;
            return attributes;
        }, { attributes: ['x', 'y'] });
    }

    /**
     * Update layout settings
     * Settings are applied on next iteration since we're using synchronous mode
     */
    updateLayoutSettings(newSettings) {
        this.options.fa2Settings = {
            ...this.options.fa2Settings,
            ...newSettings
        };
    }

    /**
     * Get node color based on type; unknown types get a stable fallback colour
     */
    getNodeColor(nodeType) {
        if (NODE_TYPE_COLORS[nodeType]) {
            return NODE_TYPE_COLORS[nodeType];
        }

        let color = this.typeColorCache.get(nodeType);
        if (!color) {
            let hash = 5381;
            for (let i = 0; i < nodeType.length; i++) {
                hash = ((hash << 5) + hash + nodeType.charCodeAt(i)) >>> 0;
            }
            color = FALLBACK_TYPE_PALETTE[hash % FALLBACK_TYPE_PALETTE.length];
            this.typeColorCache.set(nodeType, color);
        }
        return color;
    }

    /**
     * Node types present in the loaded file, most frequent first
     * Returns [{ type, label, color, count }] for building the type filter
     */
    getNodeTypes() {
        return this.typeCounts.map(({ type, count }) => ({
            type,
            label: NODE_TYPE_LABELS[type] || (type.charAt(0).toUpperCase() + type.slice(1)),
            color: this.getNodeColor(type),
            count
        }));
    }

    /**
     * Filter nodes by type
     */
    filterByType(types) {
        this.filters.nodeTypes = Array.from(types);
        this.applyFilters();
    }

    /**
     * Search nodes by label
     */
    searchNodes(query) {
        this.filters.search = query.trim().toLowerCase();
        this.applyFilters();
    }

    /**
     * Toggle giant component filter
     */
    setGiantComponentFilter(enabled) {
        this.filters.giantComponentOnly = enabled;
        this.applyFilters();
    }

    /**
     * Set minimum degree filter
     * Only show nodes with degree >= minDegree
     */
    setMinDegreeFilter(minDegree) {
        this.filters.minDegree = Math.max(0, Math.floor(minDegree));
        this.applyFilters();
    }

    /**
     * Set node size multiplier (0.1-3.0)
     * Based on some2net implementation
     */
    setNodeSizeMultiplier(multiplier) {
        // Only the multiplier is stored; the node reducer applies it to the base sizes
        this.nodeSizeMultiplier = Math.max(0.1, Math.min(3.0, multiplier));
        this.renderer.refresh();
    }

    /**
     * What drives node size right now: an id from SIZE_METRICS
     */
    getSizeMetric() {
        return this.sizeMetric;
    }

    /**
     * Whether a size metric can be used on the loaded network
     */
    isSizeMetricAvailable(id) {
        switch (id) {
            case 'degree':
                return true;
            case 'eigenvector':
            case 'pagerank':
                return this.metricData[id];
            case 'betweenness':
                return this.graph.order > 0 && this.getBetweennessFunction() !== null;
            default:
                return false;
        }
    }

    /**
     * The size metrics to offer for the loaded network: [{ id, label, description,
     * available }] in display order. pagerank is left out unless the file has it;
     * eigenvector is listed but unavailable when the file was never annotated.
     */
    getAvailableSizeMetrics() {
        return SIZE_METRICS
            .filter(metric => metric.id !== 'pagerank' || this.metricData.pagerank)
            .map(metric => ({ ...metric, available: this.isSizeMetricAvailable(metric.id) }));
    }

    /**
     * Whether switching to betweenness would block the page noticeably: a big graph
     * whose scores are not computed yet
     */
    isBetweennessSlow() {
        return !this.betweennessScores && this.graph.order > BETWEENNESS_SLOW_NODES;
    }

    /**
     * Size nodes by another centrality. Returns true if applied; an unavailable metric
     * (or a computation that fails) leaves the current one in place and returns false.
     */
    setSizeMetric(id) {
        if (!this.isSizeMetricAvailable(id)) return false;

        const previous = this.sizeMetric;
        try {
            this.sizeMetric = id;
            this.applySizeMetric();
        } catch (error) {
            console.error(`Could not size nodes by ${id}:`, error);
            this.sizeMetric = previous;
            this.applySizeMetric();
            return false;
        }

        this.renderer.refresh();
        return true;
    }

    /**
     * Whether community colouring is available: the file carries communities, or the
     * graphology library can detect them
     */
    hasCommunities() {
        return this.graph.order > 0 && (this.communityData || this.getLouvainFunction() !== null);
    }

    getColorMode() {
        return this.colorMode;
    }

    /**
     * Colour nodes by 'type' (the implied bipartite node types) or 'community'.
     * Switching to 'community' first makes sure the communities fit the nodes that are
     * visible now (ensureCommunities), which may run Louvain on them.
     * Returns true if applied; 'community' without any way to get communities stays on
     * 'type' and returns false.
     */
    setColorMode(mode) {
        if (mode !== 'type' && mode !== 'community') return false;
        if (mode === 'community' && !(this.hasCommunities() && this.ensureCommunities())) {
            this.colorMode = 'type';
            return false;
        }

        this.colorMode = mode;
        this.renderer.refresh();
        return true;
    }

    /**
     * Where the drawn communities came from and what they cover:
     * { source: 'file' | 'browser', nodes, communities, ms }, or null if none yet.
     * `communities` is 0 when the visible nodes have no edges between them.
     */
    getCommunityInfo() {
        return this.communityInfo;
    }

    /**
     * Whether the drawn communities no longer match the visible nodes, because filters
     * changed after they were assigned (or none were assigned yet)
     */
    communitiesStale() {
        if (!this.communityInfo) return true;
        if (this.hiddenNodes.size !== this.communityHidden.size) return true;
        for (const node of this.hiddenNodes) {
            if (!this.communityHidden.has(node)) return true;
        }
        return false;
    }

    /**
     * Make the drawn communities fit the visible nodes. Does nothing if they already do
     * (so switching colours back and forth is free). With no filters active the file's
     * communities are restored when it has them; otherwise Louvain runs on the visible
     * nodes. Returns false if no communities could be produced.
     */
    ensureCommunities() {
        if (!this.communitiesStale()) return true;
        if (this.communityData && this.hiddenNodes.size === 0) {
            this.restoreFileCommunities();
            return true;
        }
        return this.detectCommunities();
    }

    /**
     * louvain function of graphology-library, or null if the library is missing it
     */
    getLouvainFunction() {
        return (typeof graphologyLibrary !== 'undefined' && graphologyLibrary.communitiesLouvain) || null;
    }

    /**
     * Run Louvain on the visible nodes and draw the result. The graph is the subgraph of
     * the visible nodes; an edge counts with its weight, and one with a weight of 0 or
     * less is ignored, as in the backend. Communities are ranked by size (0 = largest,
     * ties broken by the smallest node id) so the palette applies as usual, and nodes
     * that are hidden keep no community. About 10 ms at 1,000 nodes, 120 ms at 30,000.
     * Visible nodes with no edges between them have no communities at all (Louvain would
     * only return one per node). Returns false, leaving everything as it was, on failure.
     */
    detectCommunities() {
        const louvain = this.getLouvainFunction();
        if (!louvain) return false;

        try {
            const started = performance.now();
            const subgraph = new graphology.Graph({ type: 'undirected' });
            this.graph.forEachNode(node => {
                if (!this.hiddenNodes.has(node)) subgraph.addNode(node);
            });
            this.graph.forEachEdge((edge, attributes, source, target) => {
                if (!subgraph.hasNode(source) || !subgraph.hasNode(target)) return;
                const weight = Number.isFinite(attributes.weight) ? attributes.weight : 1;
                if (weight > 0) subgraph.mergeEdge(source, target, { weight });
            });

            const rankOf = new Map();
            let communityCount = 0;
            if (subgraph.size > 0) {
                const partition = louvain(subgraph, {
                    getEdgeWeight: 'weight',
                    rng: seededRandom(COMMUNITY_SEED)
                });
                const groups = new Map();
                subgraph.forEachNode(node => {
                    if (!groups.has(partition[node])) groups.set(partition[node], []);
                    groups.get(partition[node]).push(node);
                });
                const smallest = group => group.reduce((min, node) => (node < min ? node : min));
                const ordered = [...groups.values()].sort((a, b) =>
                    b.length - a.length || (smallest(a) < smallest(b) ? -1 : 1));
                ordered.forEach((group, rank) => group.forEach(node => rankOf.set(node, rank)));
                communityCount = ordered.length;
            }

            this.assignCommunities(node => rankOf.get(node));
            this.communityHidden = new Set(this.hiddenNodes);
            this.communityInfo = {
                source: 'browser',
                nodes: subgraph.order,
                communities: communityCount,
                ms: Math.round(performance.now() - started)
            };
            this.refreshSelection();
            return true;
        } catch (error) {
            console.error('Could not detect communities:', error);
            return false;
        }
    }

    /**
     * Put the communities from the file back on the nodes (no filters active)
     */
    restoreFileCommunities() {
        this.assignCommunities(node => this.fileCommunities.get(node));
        this.communityHidden = new Set();
        this.communityInfo = this.describeFileCommunities();
        this.refreshSelection();
    }

    /**
     * Write `community` on every node from rankFor(node); undefined removes it
     */
    assignCommunities(rankFor) {
        this.graph.forEachNode(node => {
            const rank = rankFor(node);
            if (rank === undefined) {
                if (this.graph.hasNodeAttribute(node, 'community')) {
                    this.graph.removeNodeAttribute(node, 'community');
                }
            } else {
                this.graph.setNodeAttribute(node, 'community', rank);
            }
        });
    }

    describeFileCommunities() {
        return {
            source: 'file',
            nodes: this.fileCommunities.size,
            communities: new Set(this.fileCommunities.values()).size,
            ms: 0
        };
    }

    /**
     * Palette colour for a community rank (0 = largest); the neutral colour for
     * ranks beyond the palette or a missing community
     */
    getCommunityColor(community) {
        return Number.isInteger(community) && community >= 0 && community < COMMUNITY_PALETTE.length
            ? COMMUNITY_PALETTE[community]
            : COMMUNITY_OTHER_COLOR;
    }

    /**
     * Community legend data over the nodes that have a community (all of them for the
     * file's communities, the visible ones after a browser run): one entry per coloured
     * rank that occurs, plus an 'other' entry for ranks beyond the palette.
     * Returns [{ community, color, count }]; community is the rank or 'other'.
     */
    getCommunityLegend() {
        const counts = new Array(COMMUNITY_PALETTE.length).fill(0);
        let other = 0;
        this.graph.forEachNode((node, attributes) => {
            const community = attributes.community;
            if (!Number.isInteger(community)) return;
            if (community >= 0 && community < COMMUNITY_PALETTE.length) {
                counts[community]++;
            } else {
                other++;
            }
        });

        const legend = [];
        counts.forEach((count, community) => {
            if (count > 0) legend.push({ community, color: COMMUNITY_PALETTE[community], count });
        });
        if (other > 0) legend.push({ community: 'other', color: COMMUNITY_OTHER_COLOR, count: other });
        return legend;
    }

    /**
     * Show or hide node labels
     */
    setLabelsVisible(visible) {
        this.labelsVisible = Boolean(visible);
        this.renderer.setSetting('renderLabels', this.labelsVisible);
        // setSetting only schedules a render; refresh() renders now (which also clears
        // the labels canvas when labels are off)
        this.renderer.refresh();
    }

    getLabelsVisible() {
        return this.labelsVisible;
    }

    getAllLabels() {
        return this.allLabels;
    }

    /**
     * The result of the last spread (see spreadLabels), or null when all-labels is off
     * or nothing had to move
     */
    getLabelSpreadInfo() {
        return this.labelSpreadInfo;
    }

    /**
     * Label every visible node regardless of zoom, and move nodes apart so the labels
     * do not overlap at the current zoom. Switching it off again puts the nodes back
     * (unless a layout has run since).
     *
     * Sigma normally draws one label per grid cell and only for nodes above a size
     * threshold; `forceLabel` bypasses both. Labels have a fixed pixel size, so no
     * placement can keep them apart at every zoom: zooming out brings overlaps back.
     * Returns the spread info (null when switching off).
     */
    setAllLabels(enabled) {
        enabled = Boolean(enabled);
        if (enabled === this.allLabels) return this.labelSpreadInfo;

        this.allLabels = enabled;
        if (enabled) {
            try {
                this.labelSpreadInfo = this.spreadLabels();
            } catch (error) {
                // Labels stay on; the nodes just are not moved
                console.error('Could not spread labels:', error);
                this.labelSpreadInfo = null;
            }
        } else {
            if (this.spreadSnapshot) {
                this.setPositionsKeepingView(this.spreadSnapshot.positions, this.spreadSnapshot.sizeCorrection);
                this.spreadSnapshot = null;
            }
            this.labelSpreadInfo = null;
        }

        this.renderer.refresh();
        return this.labelSpreadInfo;
    }

    /**
     * Push visible nodes apart until their label boxes stop overlapping, as seen at the
     * current zoom. Works in screen pixels on one box per node (the node circle plus
     * its label), in two stages:
     *   1. inflate the whole layout about its centre by the smallest factor that leaves
     *      only a few overlaps per node (inflateLabelBoxes). A dense core needs this:
     *      wide, short boxes pushed pairwise would just stack into one tall column.
     *   2. push the remaining overlapping pairs apart along the axis they overlap least
     *      on, large nodes moving less than small ones (relaxLabelBoxes).
     * Hidden nodes neither move nor count.
     *
     * Sigma scales every position to the graph's bounding box, so growing the layout
     * would shrink it back on screen. After moving the nodes the camera is therefore set
     * to the same centre and pixel scale as before (setPositionsKeepingView). Sigma also
     * draws node circles at size / sqrt(camera ratio), so that zoom-in would balloon
     * them; viewSizeCorrection cancels it and the boxes computed here stay valid.
     */
    spreadLabels() {
        const started = performance.now();
        const info = {
            nodes: 0, moved: 0, overlapsBefore: 0, overlapsAfter: 0,
            iterations: 0, converged: true, inflation: 1, widenedBy: 1, ms: 0
        };

        const nodes = [];
        this.graph.forEachNode(node => {
            if (!this.hiddenNodes.has(node)) nodes.push(node);
        });
        info.nodes = nodes.length;
        if (nodes.length < 2) return info;

        // Nothing is written to the graph until the end
        const items = this.labelFootprints(nodes, this.createLabelMeasurer());
        info.overlapsBefore = this.countLabelOverlaps(items);
        info.inflation = this.inflateLabelBoxes(items);
        const run = this.relaxLabelBoxes(items, started + LABEL_SPREAD_TIME_BUDGET_MS);
        info.iterations = run.iterations;
        info.converged = run.converged;
        info.overlapsAfter = this.countLabelOverlaps(items);

        // Write back only the nodes that actually moved
        const moved = new Map();
        const previous = new Map();
        items.forEach(item => {
            if (Math.hypot(item.x - item.x0, item.y - item.y0) < 0.5) return;
            moved.set(item.node, this.renderer.viewportToGraph({ x: item.x, y: item.y }));
            const { x, y } = this.graph.getNodeAttributes(item.node);
            previous.set(item.node, { x, y });
        });
        info.moved = moved.size;

        if (moved.size > 0) {
            const startRatio = this.renderer.getCamera().getState().ratio;
            const startBounds = this.graphBounds();
            const newRatio = this.keepScaleRatio(startRatio, startBounds, this.graphBounds(moved));
            const correction = this.viewSizeCorrection * Math.sqrt(newRatio / startRatio);

            this.spreadSnapshot = { positions: previous, sizeCorrection: this.viewSizeCorrection };
            const view = this.setPositionsKeepingView(moved, correction);
            info.widenedBy = view.after.span / view.before.span;
        }

        info.ms = Math.round(performance.now() - started);
        return info;
    }

    /**
     * Stage 1 of the spread: scale the boxes' positions about their centroid, in place,
     * by the smallest factor in [1, LABEL_SPREAD_MAX_INFLATION] that leaves at most
     * LABEL_SPREAD_TARGET_OVERLAPS_PER_NODE overlapping pairs per node (binary search;
     * the overlap count only falls as the factor grows). Returns the factor.
     */
    inflateLabelBoxes(items) {
        const target = LABEL_SPREAD_TARGET_OVERLAPS_PER_NODE * items.length;
        let centerX = 0;
        let centerY = 0;
        items.forEach(item => {
            centerX += item.x0;
            centerY += item.y0;
        });
        centerX /= items.length;
        centerY /= items.length;

        const overlapsAt = factor => {
            items.forEach(item => {
                item.x = centerX + (item.x0 - centerX) * factor;
                item.y = centerY + (item.y0 - centerY) * factor;
            });
            return this.countLabelOverlaps(items);
        };

        if (overlapsAt(1) <= target) return 1;
        let low = 1;
        let high = LABEL_SPREAD_MAX_INFLATION;
        if (overlapsAt(high) > target) return high;  // too dense for scaling alone; stage 2 does the rest
        for (let step = 0; step < 12; step++) {
            const middle = (low + high) / 2;
            if (overlapsAt(middle) <= target) high = middle; else low = middle;
        }
        overlapsAt(high);
        return high;
    }

    /**
     * Canvas-based text width measurer using the font Sigma draws labels with
     */
    createLabelMeasurer() {
        const context = document.createElement('canvas').getContext('2d');
        const weight = this.renderer.getSetting('labelWeight');
        const size = this.renderer.getSetting('labelSize');
        const font = this.renderer.getSetting('labelFont');
        context.font = `${weight} ${size}px ${font}`;

        const widths = new Map();
        return text => {
            let width = widths.get(text);
            if (width === undefined) {
                width = context.measureText(text).width;
                widths.set(text, width);
            }
            return width;
        };
    }

    /**
     * One box per node in viewport pixels at the current camera: x, y is the node
     * centre (x0, y0 keep the starting point) and left/right/top/bottom are offsets of
     * the box that covers the node circle plus its label.
     */
    labelFootprints(nodes, measure) {
        const labelSize = this.renderer.getSetting('labelSize');
        return nodes.map(node => {
            const { x: graphX, y: graphY } = this.graph.getNodeAttributes(node);
            const point = this.renderer.graphToViewport({ x: graphX, y: graphY });
            const display = this.renderer.getNodeDisplayData(node);
            const radius = this.renderer.scaleSize(display.size);
            const labelWidth = display.label ? measure(display.label) : 0;
            return {
                node,
                x: point.x, y: point.y, x0: point.x, y0: point.y,
                left: -radius,
                right: radius + (labelWidth > 0 ? LABEL_GAP + labelWidth : 0),
                top: Math.min(-radius, labelSize / 3 - 0.75 * labelSize),
                bottom: Math.max(radius, labelSize / 3 + 0.25 * labelSize),
                mass: radius * radius + 1
            };
        });
    }

    /**
     * Move overlapping boxes apart, in place, until none overlap or the iteration or
     * time limit is hit. Boxes are bucketed in a grid sized to a typical box, so only
     * boxes sharing a cell are compared. Returns { iterations, converged }.
     */
    relaxLabelBoxes(items, deadline) {
        const count = items.length;
        const pad = LABEL_PADDING / 2;
        const percentile = values => values.sort((a, b) => a - b)[Math.floor(values.length * 0.75)];
        const cellWidth = Math.max(20, percentile(items.map(item => item.right - item.left)) + LABEL_PADDING);
        const cellHeight = Math.max(10, percentile(items.map(item => item.bottom - item.top)) + LABEL_PADDING);

        let iterations = 0;
        while (iterations < LABEL_SPREAD_MAX_ITERATIONS) {
            const grid = new Map();
            for (let i = 0; i < count; i++) {
                const item = items[i];
                const x0 = Math.floor((item.x + item.left - pad) / cellWidth);
                const x1 = Math.floor((item.x + item.right + pad) / cellWidth);
                const y0 = Math.floor((item.y + item.top - pad) / cellHeight);
                const y1 = Math.floor((item.y + item.bottom + pad) / cellHeight);
                for (let cx = x0; cx <= x1; cx++) {
                    for (let cy = y0; cy <= y1; cy++) {
                        // A hash collision only makes two boxes share a bucket, which
                        // costs a comparison; the overlap test itself is exact
                        const key = ((cx * 73856093) ^ (cy * 19349663)) | 0;
                        const bucket = grid.get(key);
                        if (bucket) bucket.push(i); else grid.set(key, [i]);
                    }
                }
            }

            let overlapping = 0;
            grid.forEach(bucket => {
                for (let a = 0; a < bucket.length; a++) {
                    for (let b = a + 1; b < bucket.length; b++) {
                        if (this.separateBoxes(items[bucket[a]], items[bucket[b]], pad)) overlapping++;
                    }
                }
            });

            if (overlapping === 0) return { iterations, converged: true };
            iterations++;
            if (performance.now() > deadline) return { iterations, converged: false };
        }
        return { iterations, converged: false };
    }

    /**
     * If two boxes (each grown by `pad`) overlap, move them apart along the axis with
     * the smaller overlap, splitting the move by mass so heavier nodes move less.
     * Returns whether they overlapped.
     */
    separateBoxes(a, b, pad) {
        const aLeft = a.x + a.left - pad, aRight = a.x + a.right + pad;
        const aTop = a.y + a.top - pad, aBottom = a.y + a.bottom + pad;
        const bLeft = b.x + b.left - pad, bRight = b.x + b.right + pad;
        const bTop = b.y + b.top - pad, bBottom = b.y + b.bottom + pad;

        const overlapX = Math.min(aRight, bRight) - Math.max(aLeft, bLeft);
        const overlapY = Math.min(aBottom, bBottom) - Math.max(aTop, bTop);
        if (overlapX <= LABEL_OVERLAP_TOLERANCE || overlapY <= LABEL_OVERLAP_TOLERANCE) return false;

        const total = a.mass + b.mass;
        const aShare = b.mass / total;
        const bShare = a.mass / total;
        if (overlapX <= overlapY) {
            const direction = aLeft + aRight <= bLeft + bRight ? -1 : 1;  // a moves away from b
            const distance = overlapX * LABEL_SPREAD_RELAXATION + 0.01;
            a.x += direction * distance * aShare;
            b.x -= direction * distance * bShare;
        } else {
            const direction = aTop + aBottom <= bTop + bBottom ? -1 : 1;
            const distance = overlapY * LABEL_SPREAD_RELAXATION + 0.01;
            a.y += direction * distance * aShare;
            b.y -= direction * distance * bShare;
        }
        return true;
    }

    /**
     * Number of overlapping box pairs (same padding rule as separateBoxes). Boxes are
     * sorted by left edge so each one is only compared with those starting before its
     * right edge.
     */
    countLabelOverlaps(items) {
        const pad = LABEL_PADDING / 2;
        const left = item => item.x + item.left - pad;
        const right = item => item.x + item.right + pad;
        const top = item => item.y + item.top - pad;
        const bottom = item => item.y + item.bottom + pad;

        const sorted = [...items].sort((a, b) => left(a) - left(b));
        let overlaps = 0;
        for (let i = 0; i < sorted.length; i++) {
            for (let j = i + 1; j < sorted.length && left(sorted[j]) < right(sorted[i]) - LABEL_OVERLAP_TOLERANCE; j++) {
                const overlapX = Math.min(right(sorted[i]), right(sorted[j])) - left(sorted[j]);
                const overlapY = Math.min(bottom(sorted[i]), bottom(sorted[j]))
                    - Math.max(top(sorted[i]), top(sorted[j]));
                if (overlapX > LABEL_OVERLAP_TOLERANCE && overlapY > LABEL_OVERLAP_TOLERANCE) overlaps++;
            }
        }
        return overlaps;
    }

    /**
     * Bounding box of ALL nodes (the box Sigma scales to the screen): { minX, minY,
     * width, height, span } where span is the longer side. `overrides` (Map node ->
     * { x, y }) substitutes positions without touching the graph.
     */
    graphBounds(overrides = null) {
        let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
        this.graph.forEachNode((node, attributes) => {
            const point = (overrides && overrides.get(node)) || attributes;
            minX = Math.min(minX, point.x);
            maxX = Math.max(maxX, point.x);
            minY = Math.min(minY, point.y);
            maxY = Math.max(maxY, point.y);
        });
        const width = maxX - minX || 1;
        const height = maxY - minY || 1;
        return { minX, minY, width, height, span: Math.max(width, height) };
    }

    /**
     * Camera ratio that keeps the pixels-per-graph-unit of `from` bounds when the graph's
     * bounds become `to`. Sigma draws one graph unit as
     *     min(viewport width, height) * correction / (ratio * span)
     * pixels (minus padding), where `correction` is getCorrectionRatio: 1 when the
     * viewport and the graph are oriented differently, otherwise the smaller of the two
     * aspect factors. The correction depends on the graph's aspect, so it has to be
     * included when the bounding box changes shape.
     */
    keepScaleRatio(ratio, from, to) {
        const { width, height } = this.renderer.getDimensions();
        const correction = bounds => {
            const viewportAspect = height / width;
            const graphAspect = bounds.height / bounds.width;
            if ((viewportAspect < 1 && graphAspect > 1) || (viewportAspect > 1 && graphAspect < 1)) return 1;
            return Math.min(Math.max(graphAspect, 1 / graphAspect), Math.max(1 / viewportAspect, viewportAspect));
        };
        return ratio * (correction(to) / correction(from)) * (from.span / to.span);
    }

    /**
     * Move nodes to new graph coordinates without changing what the user sees of the
     * rest: Sigma rescales everything to the new bounding box, so the camera is
     * adjusted to keep the same point at the centre of the viewport and the same
     * pixels per graph unit. `sizeCorrection`, if given, replaces viewSizeCorrection in
     * the same refresh. Returns the bounds before and after.
     */
    setPositionsKeepingView(positions, sizeCorrection = null) {
        const camera = this.renderer.getCamera();
        const { width, height } = this.renderer.getDimensions();
        const center = this.renderer.viewportToGraph({ x: width / 2, y: height / 2 });
        const ratio = camera.getState().ratio;
        const before = this.graphBounds();

        positions.forEach((point, node) => {
            this.graph.mergeNodeAttributes(node, { x: point.x, y: point.y });
        });
        if (sizeCorrection !== null) this.viewSizeCorrection = sizeCorrection;
        this.renderer.refresh();

        const after = this.graphBounds();
        camera.setState({
            x: 0.5 + (center.x - (after.minX + after.width / 2)) / after.span,
            y: 0.5 + (center.y - (after.minY + after.height / 2)) / after.span,
            ratio: this.keepScaleRatio(ratio, before, after)
        });
        return { before, after };
    }

    /**
     * Largest connected component among `candidates` (a Set of node ids), considering
     * only edges between candidates. BFS with an index pointer instead of shift().
     */
    findGiantComponent(candidates) {
        const visited = new Set();
        let giant = [];

        for (const start of candidates) {
            if (visited.has(start)) continue;

            const component = [start];
            visited.add(start);

            for (let i = 0; i < component.length; i++) {
                this.graph.forEachNeighbor(component[i], neighbor => {
                    if (candidates.has(neighbor) && !visited.has(neighbor)) {
                        visited.add(neighbor);
                        component.push(neighbor);
                    }
                });
            }

            if (component.length > giant.length) {
                giant = component;
            }
        }

        return new Set(giant);
    }

    /**
     * Recompute which nodes are hidden from the active filters and refresh the renderer.
     * The graph itself is never modified, so layout positions survive any filter change.
     *
     * Filters are applied in this order:
     *   1. node type + label search
     *   2. giant component, over the nodes that passed step 1
     *   3. minimum degree, counting only neighbours that passed steps 1-2. Nodes are
     *      dropped in a single pass (not iteratively), as in the previous
     *      rebuild-then-drop implementation.
     */
    applyFilters() {
        const { nodeTypes, search, giantComponentOnly, minDegree } = this.filters;

        // 1. Type and search
        let visible = new Set();
        this.graph.forEachNode((node, attributes) => {
            if (nodeTypes.length > 0 && !nodeTypes.includes(attributes.node_type)) return;
            if (search && !attributes.label.toLowerCase().includes(search)) return;
            visible.add(node);
        });

        // 2. Giant component
        if (giantComponentOnly && visible.size > 0) {
            visible = this.findGiantComponent(visible);
        }

        // 3. Minimum degree
        if (minDegree > 0) {
            const kept = new Set();
            visible.forEach(node => {
                let degree = 0;
                this.graph.forEachNeighbor(node, neighbor => {
                    if (visible.has(neighbor)) degree++;
                });
                if (degree >= minDegree) kept.add(node);
            });
            visible = kept;
        }

        // Everything not visible is hidden; count the edges between visible nodes
        this.hiddenNodes = new Set();
        this.graph.forEachNode(node => {
            if (!visible.has(node)) this.hiddenNodes.add(node);
        });

        let visibleEdges = 0;
        this.graph.forEachEdge((edge, attributes, source, target) => {
            if (visible.has(source) && visible.has(target)) visibleEdges++;
        });
        this.visibleStats = { nodes: visible.size, edges: visibleEdges };

        this.refreshSelection();
        this.renderer.refresh();
    }

    /**
     * Clear all filters
     */
    clearFilters() {
        this.filters.nodeTypes = [];
        this.filters.search = '';
        this.filters.giantComponentOnly = false;
        this.filters.minDegree = 0;
        this.applyFilters();
    }

    /**
     * Selected-node payload for the UI: node attributes plus its degree among
     * visible nodes (the degree the filters and statistics work with)
     */
    buildSelectedNode(node) {
        let degree = 0;
        this.graph.forEachNeighbor(node, neighbor => {
            if (!this.hiddenNodes.has(neighbor)) degree++;
        });
        return { id: node, ...this.graph.getNodeAttributes(node), degree };
    }

    /**
     * After a filter change: drop the selection if its node is now hidden,
     * otherwise refresh its (visible) degree
     */
    refreshSelection() {
        if (!this.selectedNode) return;

        if (this.hiddenNodes.has(this.selectedNode.id)) {
            this.selectedNode = null;
            this.onNodeDeselect();
        } else {
            this.selectedNode = this.buildSelectedNode(this.selectedNode.id);
            this.onNodeSelect(this.selectedNode);
        }
    }

    /**
     * Focus on a specific node
     */
    focusNode(nodeId) {
        try {
            const nodePosition = this.renderer.getNodeDisplayData(nodeId);
            if (nodePosition) {
                this.renderer.getCamera().animate(
                    { x: nodePosition.x, y: nodePosition.y, ratio: 0.5 },
                    { duration: 600 }
                );
            }
        } catch (error) {
            console.error('Error focusing node:', error);
        }
    }

    /**
     * Fit network to viewport
     */
    fit() {
        if (this.renderer) {
            const camera = this.renderer.getCamera();
            camera.animatedReset({ duration: 600 });
        }
    }

    /**
     * Zoom in
     */
    zoomIn() {
        const camera = this.renderer.getCamera();
        const currentRatio = camera.getState().ratio;
        camera.animate({ ratio: currentRatio * 0.7 }, { duration: 300 });
    }

    /**
     * Zoom out
     */
    zoomOut() {
        const camera = this.renderer.getCamera();
        const currentRatio = camera.getState().ratio;
        camera.animate({ ratio: currentRatio * 1.5 }, { duration: 300 });
    }

    /**
     * Export the current view as a PNG: Sigma's canvas layers composited onto a
     * white background at the backing-store resolution. Reflects the active
     * filters, colour mode and labels toggle.
     * Resolves to the PNG Blob, or null if the export failed.
     */
    exportAsPNG(filename = 'network.png') {
        const fail = (error) => {
            console.error('Error exporting PNG:', error);
            if (typeof showToast === 'function') {
                showToast('Failed to export network', 'error');
            }
            return null;
        };

        return new Promise((resolve) => {
            try {
                const canvases = this.renderer.getCanvases();
                const { width, height } = canvases.edges;

                // Render now and copy within this same task: Sigma only preserves the
                // drawing buffer of the edges layer, so the WebGL nodes layer reads
                // back blank once the browser has presented the frame.
                this.renderer.refresh();

                const output = document.createElement('canvas');
                output.width = width;
                output.height = height;
                const context = output.getContext('2d');
                context.fillStyle = '#ffffff';
                context.fillRect(0, 0, width, height);
                EXPORT_CANVAS_LAYERS.forEach(layer => {
                    context.drawImage(canvases[layer], 0, 0, width, height);
                });

                output.toBlob((blob) => {
                    if (!blob) {
                        resolve(fail(new Error('PNG encoding failed')));
                        return;
                    }

                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);

                    if (typeof showToast === 'function') {
                        showToast('Network exported successfully', 'success');
                    }
                    resolve(blob);
                }, 'image/png');
            } catch (error) {
                resolve(fail(error));
            }
        });
    }

    /**
     * Get statistics for the visible (filtered) network
     */
    getStatistics() {
        const { nodes, edges } = this.visibleStats;
        return {
            nodes,
            edges,
            density: nodes > 1 ? (2 * edges) / (nodes * (nodes - 1)) : 0,
            avgDegree: nodes > 0 ? (2 * edges) / nodes : 0
        };
    }

    /**
     * Callbacks (override these)
     */
    onNodeSelect(node) {
        // Override this method to handle node selection
    }

    onNodeDeselect() {
        // Override this method to handle node deselection
    }

    onLayoutStateChange(running) {
        // Override this method to follow the layout starting/stopping (including
        // when it stops itself after an error or because it settled)
    }

    onLayoutSettled(result) {
        // Override this method to be told when the layout stopped itself because the
        // nodes stopped moving; result = { iterations, ms }
    }

    /**
     * Destroy renderer
     */
    destroy() {
        // Stop layout if running
        this.stopLayout();

        if (this.renderer) {
            this.renderer.kill();
            this.renderer = null;
        }
        if (this.graph) {
            this.graph.clear();
        }
    }
}

// Export for use in templates
window.GraphologyNetworkVisualizer = GraphologyNetworkVisualizer;
