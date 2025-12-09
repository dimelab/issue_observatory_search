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
 */

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
        this.rawData = null;
        this.fa2Layout = null;

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
                linLogMode: false
            },
            sigma: {
                renderEdgeLabels: false,
                defaultNodeColor: '#999',
                defaultEdgeColor: '#ccc',
                labelSize: 14,
                labelWeight: 'bold',
                labelColor: { color: '#000' }
            },
            ...options
        };

        // State
        this.selectedNode = null;
        this.filters = {
            nodeTypes: [],
            search: ''
        };

        // Initialize
        this.init();
    }

    /**
     * Initialize Sigma.js renderer with Graphology graph
     */
    init() {
        try {
            // Create Sigma renderer
            this.renderer = new Sigma(this.graph, this.container, this.options.sigma);

            // Setup event listeners
            this.setupEventListeners();

            console.log('GraphologyNetworkVisualizer initialized');
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
                const nodeData = this.graph.getNodeAttributes(node);
                this.selectedNode = { id: node, ...nodeData };
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
     * Load and parse GEXF file
     */
    async loadFromGEXF(url) {
        try {
            const response = await fetch(url, {
                headers: {
                    'Authorization': 'Bearer ' + localStorage.getItem('token')
                }
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
     * Parse GEXF and populate Graphology graph
     */
    async parseGEXF(gexfText) {
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(gexfText, 'text/xml');

        // Check for parsing errors
        const parserError = xmlDoc.querySelector('parsererror');
        if (parserError) {
            throw new Error('Invalid GEXF format');
        }

        // Clear existing graph
        this.graph.clear();

        const nodesData = [];
        const edgesData = [];

        // Parse nodes
        const xmlNodes = xmlDoc.querySelectorAll('node');
        xmlNodes.forEach(xmlNode => {
            const id = xmlNode.getAttribute('id');
            const label = xmlNode.getAttribute('label') || id;

            // Parse attributes
            const attributes = this.parseNodeAttributes(xmlNode);
            const nodeType = attributes.node_type || attributes.type || 'default';

            // Parse position if available (from GEXF viz namespace)
            let x, y;
            const vizPosition = xmlNode.querySelector('viz\\:position, position');
            if (vizPosition) {
                x = parseFloat(vizPosition.getAttribute('x'));
                y = parseFloat(vizPosition.getAttribute('y'));
            }

            nodesData.push({
                id,
                label,
                nodeType,
                attributes,
                x,
                y
            });
        });

        // Parse edges
        const xmlEdges = xmlDoc.querySelectorAll('edge');
        xmlEdges.forEach(xmlEdge => {
            const source = xmlEdge.getAttribute('source');
            const target = xmlEdge.getAttribute('target');
            const weight = parseFloat(xmlEdge.getAttribute('weight')) || 1;

            edgesData.push({
                source,
                target,
                weight
            });
        });

        // Store raw data for filtering
        this.rawData = { nodes: nodesData, edges: edgesData };

        // Apply initial circular layout if no positions
        const hasPositions = nodesData.some(n => n.x !== undefined && n.y !== undefined);
        if (!hasPositions) {
            this.applyCircularLayout(nodesData);
        }

        // Add nodes to graph
        nodesData.forEach(({ id, label, nodeType, attributes, x, y }) => {
            this.graph.addNode(id, {
                label,
                size: 10,
                color: this.getNodeColor(nodeType),
                node_type: nodeType,
                x: x !== undefined ? x : 0,
                y: y !== undefined ? y : 0,
                ...attributes
            });
        });

        // Add edges to graph
        edgesData.forEach(({ source, target, weight }) => {
            if (this.graph.hasNode(source) && this.graph.hasNode(target)) {
                try {
                    this.graph.addEdge(source, target, { weight });
                } catch (error) {
                    // Skip duplicate edges
                    console.warn('Skipping duplicate edge:', source, '->', target);
                }
            }
        });

        console.log(`Loaded ${nodesData.length} nodes, ${edgesData.length} edges`);

        // Apply ForceAtlas2 layout if no positions
        if (!hasPositions) {
            await this.applyForceAtlas2Layout();
        }

        // Refresh renderer
        this.renderer.refresh();

        // Fit to viewport
        setTimeout(() => this.fit(), 100);
    }

    /**
     * Apply circular layout to nodes (initial layout before ForceAtlas2)
     */
    applyCircularLayout(nodesData) {
        const n = nodesData.length;
        const radius = 100;

        nodesData.forEach((node, i) => {
            const angle = (2 * Math.PI * i) / n;
            node.x = Math.cos(angle) * radius;
            node.y = Math.sin(angle) * radius;
        });

        console.log('Applied circular layout');
    }

    /**
     * Apply ForceAtlas2 layout using graphology-library
     */
    async applyForceAtlas2Layout() {
        // Check if graphology-library is available
        if (typeof graphologyLibrary === 'undefined' || !graphologyLibrary.FA2Layout) {
            console.warn('ForceAtlas2 layout not available (graphology-library missing)');
            return;
        }

        try {
            console.log('Starting ForceAtlas2 layout...');

            // Create FA2Layout instance
            const FA2Layout = graphologyLibrary.FA2Layout;
            this.fa2Layout = new FA2Layout(this.graph, {
                settings: this.options.fa2Settings
            });

            // Run layout for a fixed number of iterations
            const iterations = 500;

            // Start the layout
            this.fa2Layout.start();

            // Run iterations
            for (let i = 0; i < iterations; i++) {
                // The layout runs automatically, just need to wait
                if (i % 100 === 0) {
                    console.log(`ForceAtlas2 iteration ${i}/${iterations}`);
                    // Refresh renderer periodically to show progress
                    this.renderer.refresh();
                    await new Promise(resolve => setTimeout(resolve, 10));
                }
            }

            // Stop the layout
            this.fa2Layout.stop();

            console.log('ForceAtlas2 layout complete');

        } catch (error) {
            console.error('Error applying ForceAtlas2 layout:', error);
        }
    }

    /**
     * Parse node attributes from GEXF XML
     */
    parseNodeAttributes(xmlNode) {
        const attributes = {};
        xmlNode.querySelectorAll('attvalue').forEach(attr => {
            const key = attr.getAttribute('for');
            const value = attr.getAttribute('value');
            attributes[key] = value;
        });
        return attributes;
    }

    /**
     * Get node color based on type (same as Vis.js version for consistency)
     */
    getNodeColor(nodeType) {
        const colorMap = {
            'search': '#3B82F6',      // Blue
            'website': '#10B981',     // Green
            'keyword': '#F59E0B',     // Amber (v6.0.0: renamed from noun)
            'noun': '#F59E0B',        // Amber (backward compat)
            'entity': '#8B5CF6',      // Purple (v6.0.0: for NER)
            'topic': '#EC4899',       // Pink
            'concept': '#EC4899',     // Pink
            'default': '#6B7280'      // Gray
        };
        return colorMap[nodeType] || colorMap.default;
    }

    /**
     * Filter nodes by type
     */
    filterByType(types) {
        this.filters.nodeTypes = types;
        this.applyFilters();
    }

    /**
     * Search nodes by label
     */
    searchNodes(query) {
        this.filters.search = query.toLowerCase();
        this.applyFilters();
    }

    /**
     * Apply all active filters
     */
    applyFilters() {
        if (!this.rawData) return;

        // Clear and rebuild graph with filtered data
        this.graph.clear();

        let filteredNodes = this.rawData.nodes;

        // Filter by type
        if (this.filters.nodeTypes.length > 0) {
            filteredNodes = filteredNodes.filter(node =>
                this.filters.nodeTypes.includes(node.nodeType)
            );
        }

        // Filter by search query
        if (this.filters.search) {
            filteredNodes = filteredNodes.filter(node =>
                node.label.toLowerCase().includes(this.filters.search)
            );
        }

        // Get filtered node IDs
        const nodeIds = new Set(filteredNodes.map(n => n.id));

        // Filter edges
        const filteredEdges = this.rawData.edges.filter(edge =>
            nodeIds.has(edge.source) && nodeIds.has(edge.target)
        );

        // Rebuild graph
        filteredNodes.forEach(({ id, label, nodeType, attributes, x, y }) => {
            this.graph.addNode(id, {
                label,
                size: 10,
                color: this.getNodeColor(nodeType),
                node_type: nodeType,
                x: x !== undefined ? x : 0,
                y: y !== undefined ? y : 0,
                ...attributes
            });
        });

        filteredEdges.forEach(({ source, target, weight }) => {
            if (this.graph.hasNode(source) && this.graph.hasNode(target)) {
                try {
                    this.graph.addEdge(source, target, { weight });
                } catch (error) {
                    // Skip duplicates
                }
            }
        });

        this.renderer.refresh();
    }

    /**
     * Clear all filters
     */
    clearFilters() {
        this.filters.nodeTypes = [];
        this.filters.search = '';

        if (this.rawData) {
            // Rebuild full graph
            this.graph.clear();

            this.rawData.nodes.forEach(({ id, label, nodeType, attributes, x, y }) => {
                this.graph.addNode(id, {
                    label,
                    size: 10,
                    color: this.getNodeColor(nodeType),
                    node_type: nodeType,
                    x: x !== undefined ? x : 0,
                    y: y !== undefined ? y : 0,
                    ...attributes
                });
            });

            this.rawData.edges.forEach(({ source, target, weight }) => {
                if (this.graph.hasNode(source) && this.graph.hasNode(target)) {
                    try {
                        this.graph.addEdge(source, target, { weight });
                    } catch (error) {
                        // Skip duplicates
                    }
                }
            });

            this.renderer.refresh();
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
     * Export as PNG
     */
    exportAsPNG(filename = 'network.png') {
        try {
            const canvas = this.container.querySelector('canvas');
            if (!canvas) {
                if (typeof showToast === 'function') {
                    showToast('Unable to export visualization', 'error');
                }
                return;
            }

            canvas.toBlob((blob) => {
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
            });
        } catch (error) {
            console.error('Error exporting PNG:', error);
            if (typeof showToast === 'function') {
                showToast('Failed to export network', 'error');
            }
        }
    }

    /**
     * Get network statistics
     */
    getStatistics() {
        return {
            nodes: this.graph.order,
            edges: this.graph.size,
            density: this.calculateDensity(),
            avgDegree: this.calculateAverageDegree()
        };
    }

    /**
     * Calculate network density
     */
    calculateDensity() {
        const n = this.graph.order;
        const m = this.graph.size;
        if (n <= 1) return 0;
        return (2 * m) / (n * (n - 1));
    }

    /**
     * Calculate average degree
     */
    calculateAverageDegree() {
        const n = this.graph.order;
        const m = this.graph.size;
        if (n === 0) return 0;
        return (2 * m) / n;
    }

    /**
     * Callbacks (override these)
     */
    onNodeSelect(node) {
        // Override this method to handle node selection
        console.log('Node selected:', node);
    }

    onNodeDeselect() {
        // Override this method to handle node deselection
        console.log('Node deselected');
    }

    /**
     * Destroy renderer
     */
    destroy() {
        // Stop ForceAtlas2 if running
        if (this.fa2Layout) {
            this.fa2Layout.kill();
            this.fa2Layout = null;
        }

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
