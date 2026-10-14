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

// Community colours: the backend numbers communities by size (0 = largest). Ranks
// beyond the palette, and nodes without a community, are drawn in the neutral colour.
const COMMUNITY_PALETTE = [
    '#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F',
    '#EDC948', '#B07AA1', '#FF9DA7', '#9C755F', '#17BECF'
];
const COMMUNITY_OTHER_COLOR = '#CBD5E1';

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

        // Configuration (similar to some2net)
        this.options = {
            fa2Settings: {
                adjustSizes: false,
                barnesHutOptimize: true,
                barnesHutTheta: 1.2,
                edgeWeightInfluence: 1.0,
                gravity: 1.0,
                scalingRatio: 10,
                slowDown: 1,
                linLogMode: false,
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
        this.sizeMetric = 'degree';  // 'pagerank' | 'eigenvector' | 'degree'
        this.baseSizes = new Map();
        this.communityData = false;  // any node with a numeric community

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
                    size: (this.baseSizes.get(node) || NODE_SIZE_MIN) * this.nodeSizeMultiplier,
                    color: this.colorMode === 'community'
                        ? this.getCommunityColor(data.community)
                        : data.color,
                    hidden: this.hiddenNodes.has(node)
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

        // Community colouring needs data; fall back to type colours if a reload lost it
        this.communityData = this.graph.someNode((node, attributes) => Number.isFinite(attributes.community));
        if (!this.communityData) {
            this.colorMode = 'type';
        }

        // Layout is not run on load - the user starts it with the Start Layout button
        // (matches some2net behaviour)

        // Re-apply current filters to the new graph and render
        this.applyFilters();

        // Fit to viewport
        setTimeout(() => this.fit(), 100);
    }

    /**
     * Derive every node's base size from centrality, over ALL nodes of the loaded
     * graph (never the filtered subset), so sizes stay stable while filtering.
     *
     * The metric is decided once per load: pagerank if any node has one, else
     * eigenvector, else full-graph degree. Scores are min-max scaled and mapped with
     * a square root to NODE_SIZE_MIN..NODE_SIZE_MAX so hubs stand out without
     * flattening everything else. The displayed size is base size * size multiplier.
     */
    computeNodeSizes() {
        this.baseSizes = new Map();
        if (this.graph.order === 0) {
            this.sizeMetric = 'degree';
            return;
        }

        const hasValue = key => this.graph.someNode((node, attributes) => Number.isFinite(attributes[key]));
        this.sizeMetric = hasValue('pagerank') ? 'pagerank' : hasValue('eigenvector') ? 'eigenvector' : 'degree';

        // Eigenvector values are L2-normalised within each connected component, so a
        // 2-node component scores 0.707 per node, which would outrank the hub of a
        // 1000-node giant component (typically ~0.1). Weighting by sqrt(n_c / N) gives
        // each component a share of the squared mass proportional to its node count.
        // Nodes without a `component` attribute share one group, so a file with none
        // is a single component and the weight is 1. pagerank and degree are not scaled.
        const componentCounts = new Map();
        const componentOf = attributes => (Number.isFinite(attributes.component) ? attributes.component : null);
        if (this.sizeMetric === 'eigenvector') {
            this.graph.forEachNode((node, attributes) => {
                const component = componentOf(attributes);
                componentCounts.set(component, (componentCounts.get(component) || 0) + 1);
            });
        }

        const scores = new Map();
        let min = Infinity;
        let max = -Infinity;
        this.graph.forEachNode((node, attributes) => {
            let score;
            if (this.sizeMetric === 'degree') {
                score = this.graph.degree(node);
            } else if (this.sizeMetric === 'pagerank') {
                score = Number.isFinite(attributes.pagerank) ? attributes.pagerank : 0;
            } else {
                const eigenvector = Number.isFinite(attributes.eigenvector) ? attributes.eigenvector : 0;
                score = eigenvector * Math.sqrt(componentCounts.get(componentOf(attributes)) / this.graph.order);
            }
            scores.set(node, score);
            min = Math.min(min, score);
            max = Math.max(max, score);
        });

        scores.forEach((score, node) => {
            const t = max > min ? (score - min) / (max - min) : 0;
            this.baseSizes.set(node, NODE_SIZE_MIN + (NODE_SIZE_MAX - NODE_SIZE_MIN) * Math.sqrt(t));
        });
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

        this.layoutIsRunning = true;
        this.onLayoutStateChange(true);
        this.layoutAnimationFrame = requestAnimationFrame(() => this.animateLayout());
    }

    /**
     * Animation loop for continuous layout using synchronous iterations
     */
    animateLayout() {
        if (!this.layoutIsRunning) return;

        try {
            // Run 1 iteration synchronously (settings are read fresh every iteration)
            graphologyLibrary.layoutForceAtlas2.assign(this.graph, {
                iterations: 1,
                settings: this.options.fa2Settings
            });

            // Refresh renderer
            this.renderer.refresh();

            // Schedule next frame
            this.layoutAnimationFrame = requestAnimationFrame(() => this.animateLayout());
        } catch (error) {
            console.error('Error in layout animation:', error);
            this.stopLayout();
        }
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
     * What drives node size in the loaded network: 'pagerank', 'eigenvector' or 'degree'
     */
    getSizeMetric() {
        return this.sizeMetric;
    }

    /**
     * Whether any node carries a numeric community (needed for community colouring)
     */
    hasCommunities() {
        return this.communityData;
    }

    getColorMode() {
        return this.colorMode;
    }

    /**
     * Colour nodes by 'type' (the implied bipartite node types) or 'community'.
     * Returns true if applied; 'community' without community data stays on 'type'
     * and returns false.
     */
    setColorMode(mode) {
        if (mode !== 'type' && mode !== 'community') return false;
        if (mode === 'community' && !this.communityData) {
            this.colorMode = 'type';
            return false;
        }

        this.colorMode = mode;
        this.renderer.refresh();
        return true;
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
     * Community legend data over all nodes (not the filtered subset): one entry per
     * coloured rank that occurs, plus an 'other' entry for the grayed-out rest
     * Returns [{ community, color, count }]; community is the rank or 'other'.
     */
    getCommunityLegend() {
        const counts = new Array(COMMUNITY_PALETTE.length).fill(0);
        let other = 0;
        this.graph.forEachNode((node, attributes) => {
            const community = attributes.community;
            if (Number.isInteger(community) && community >= 0 && community < COMMUNITY_PALETTE.length) {
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
        // when it stops itself after an error)
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
