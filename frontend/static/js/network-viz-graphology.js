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
 * - v6.0.0.2: Node size control and giant component filter (default size 0.5x)
 */
console.log('Loading network-viz-graphology.js v6.0.0.2');

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
        this.nodeSizeMultiplier = 0.5; // Node size control (0.1-3.0, default 0.5x)
        this.filters = {
            nodeTypes: [],
            search: '',
            giantComponentOnly: false
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
            // Only include serializable primitive attributes
            const baseSize = 10;
            const nodeAttrs = {
                label: String(label),
                size: baseSize * this.nodeSizeMultiplier,
                baseSize: baseSize, // Store base size for later adjustments
                color: this.getNodeColor(nodeType),
                node_type: String(nodeType),
                x: Number(x !== undefined ? x : 0),
                y: Number(y !== undefined ? y : 0)
            };

            // Add only string/number attributes from GEXF
            if (attributes) {
                Object.keys(attributes).forEach(key => {
                    const value = attributes[key];
                    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
                        nodeAttrs[key] = value;
                    }
                });
            }

            this.graph.addNode(id, nodeAttrs);
        });

        // Add edges to graph
        edgesData.forEach(({ source, target, weight }) => {
            if (this.graph.hasNode(source) && this.graph.hasNode(target)) {
                try {
                    this.graph.addEdge(source, target, {
                        weight: Number(weight) || 1
                    });
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
     * Apply ForceAtlas2 layout using graphology-library (initial layout only)
     * Note: Skipped on load - user must manually start layout with button
     */
    async applyForceAtlas2Layout() {
        // Don't auto-apply layout on load - let user control it with buttons
        // This matches some2net behavior
        console.log('Initial layout skipped - use Start Layout button to begin');
    }

    /**
     * Start ForceAtlas2 layout (continuous)
     * Uses synchronous layoutForceAtlas2 to avoid Web Worker issues
     */
    startLayout() {
        if (typeof graphologyLibrary === 'undefined') {
            console.warn('ForceAtlas2 layout not available');
            return;
        }

        try {
            console.log('Starting ForceAtlas2 layout...');

            // Use synchronous layoutForceAtlas2 instead of FA2Layout (which uses Web Workers)
            const layoutForceAtlas2 = graphologyLibrary.layoutForceAtlas2;

            if (!layoutForceAtlas2 || !layoutForceAtlas2.assign) {
                console.error('layoutForceAtlas2.assign not available');
                return;
            }

            // Mark as running
            this.layoutIsRunning = true;

            // Start animation loop for continuous layout
            this.animateLayout();

            console.log('ForceAtlas2 layout started');
        } catch (error) {
            console.error('Error starting layout:', error);
            this.layoutIsRunning = false;
        }
    }

    /**
     * Animation loop for continuous layout using synchronous iterations
     */
    animateLayout() {
        if (!this.layoutIsRunning || !graphologyLibrary || !graphologyLibrary.layoutForceAtlas2) {
            return;
        }

        try {
            const layoutForceAtlas2 = graphologyLibrary.layoutForceAtlas2;

            // Run 1 iteration synchronously
            layoutForceAtlas2.assign(this.graph, {
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
        if (this.layoutIsRunning) {
            console.log('Stopping ForceAtlas2 layout...');
            this.layoutIsRunning = false;

            // Cancel animation frame
            if (this.layoutAnimationFrame) {
                cancelAnimationFrame(this.layoutAnimationFrame);
                this.layoutAnimationFrame = null;
            }
        }
    }

    /**
     * Update layout settings
     * Settings are applied on next iteration since we're using synchronous mode
     */
    updateLayoutSettings(newSettings) {
        // Update stored settings
        this.options.fa2Settings = {
            ...this.options.fa2Settings,
            ...newSettings
        };

        // Settings will be applied on next animation frame
        // No need to restart - synchronous mode uses settings directly

        console.log('Layout settings updated:', this.options.fa2Settings);
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
     * Toggle giant component filter
     */
    setGiantComponentFilter(enabled) {
        console.log(`Giant component filter: ${enabled ? 'ON' : 'OFF'}`);
        this.filters.giantComponentOnly = enabled;
        this.applyFilters();
    }

    /**
     * Set node size multiplier (0.1-3.0)
     * Based on some2net implementation
     */
    setNodeSizeMultiplier(multiplier) {
        this.nodeSizeMultiplier = Math.max(0.1, Math.min(3.0, multiplier));

        // Update all node sizes
        this.graph.forEachNode((node, attributes) => {
            const baseSize = attributes.baseSize || 10;
            this.graph.setNodeAttribute(node, 'size', baseSize * this.nodeSizeMultiplier);
        });

        this.renderer.refresh();
    }

    /**
     * Extract connected components using BFS
     * Returns array of arrays, each containing node IDs in a component
     */
    getConnectedComponents(nodes, edges) {
        const nodeIds = new Set(nodes.map(n => n.id));
        const adjacencyList = new Map();

        // Build adjacency list
        nodeIds.forEach(id => adjacencyList.set(id, []));
        edges.forEach(({ source, target }) => {
            if (nodeIds.has(source) && nodeIds.has(target)) {
                adjacencyList.get(source).push(target);
                adjacencyList.get(target).push(source);
            }
        });

        const visited = new Set();
        const components = [];

        // BFS to find components
        for (const startNode of nodeIds) {
            if (visited.has(startNode)) continue;

            const component = [];
            const queue = [startNode];
            visited.add(startNode);

            while (queue.length > 0) {
                const node = queue.shift();
                component.push(node);

                const neighbors = adjacencyList.get(node) || [];
                for (const neighbor of neighbors) {
                    if (!visited.has(neighbor)) {
                        visited.add(neighbor);
                        queue.push(neighbor);
                    }
                }
            }

            components.push(component);
        }

        // Sort by size (largest first)
        components.sort((a, b) => b.length - a.length);
        return components;
    }

    /**
     * Apply all active filters
     */
    applyFilters() {
        if (!this.rawData) {
            console.warn('No rawData available for filtering');
            return;
        }

        console.log('Applying filters:', {
            nodeTypes: this.filters.nodeTypes,
            search: this.filters.search,
            giantComponentOnly: this.filters.giantComponentOnly
        });

        // Clear and rebuild graph with filtered data
        this.graph.clear();

        let filteredNodes = this.rawData.nodes;
        console.log(`Starting with ${filteredNodes.length} nodes`);

        // Filter by type
        if (this.filters.nodeTypes.length > 0) {
            filteredNodes = filteredNodes.filter(node =>
                this.filters.nodeTypes.includes(node.nodeType)
            );
            console.log(`After type filter: ${filteredNodes.length} nodes`);
        }

        // Filter by search query
        if (this.filters.search) {
            filteredNodes = filteredNodes.filter(node =>
                node.label.toLowerCase().includes(this.filters.search)
            );
            console.log(`After search filter: ${filteredNodes.length} nodes`);
        }

        // Get filtered node IDs
        let nodeIds = new Set(filteredNodes.map(n => n.id));

        // Filter edges
        let filteredEdges = this.rawData.edges.filter(edge =>
            nodeIds.has(edge.source) && nodeIds.has(edge.target)
        );
        console.log(`Filtered edges: ${filteredEdges.length}`);

        // Apply giant component filter
        if (this.filters.giantComponentOnly) {
            console.log('Extracting giant component...');
            const components = this.getConnectedComponents(filteredNodes, filteredEdges);
            console.log(`Found ${components.length} connected component(s)`);

            if (components.length > 0) {
                const giantComponent = new Set(components[0]);
                const componentSize = giantComponent.size;
                const totalSize = filteredNodes.length;

                console.log(`Giant component: ${componentSize} nodes (${(componentSize/totalSize*100).toFixed(1)}% of network)`);

                if (components.length > 1) {
                    console.log(`Other components: ${components.slice(1).map(c => c.length).join(', ')} nodes`);
                }

                // Filter to only giant component nodes
                filteredNodes = filteredNodes.filter(node => giantComponent.has(node.id));
                nodeIds = giantComponent;

                // Filter edges again
                filteredEdges = filteredEdges.filter(edge =>
                    giantComponent.has(edge.source) && giantComponent.has(edge.target)
                );

                console.log(`After giant component: ${filteredNodes.length} nodes, ${filteredEdges.length} edges`);
            }
        }

        // Rebuild graph
        filteredNodes.forEach(({ id, label, nodeType, attributes, x, y }) => {
            const baseSize = 10;
            this.graph.addNode(id, {
                label,
                size: baseSize * this.nodeSizeMultiplier,
                baseSize: baseSize,
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

        console.log(`Final graph: ${this.graph.order} nodes, ${this.graph.size} edges`);
        this.renderer.refresh();
    }

    /**
     * Clear all filters
     */
    clearFilters() {
        this.filters.nodeTypes = [];
        this.filters.search = '';
        this.filters.giantComponentOnly = false;

        if (this.rawData) {
            // Rebuild full graph
            this.graph.clear();

            this.rawData.nodes.forEach(({ id, label, nodeType, attributes, x, y }) => {
                const baseSize = 10;
                this.graph.addNode(id, {
                    label,
                    size: baseSize * this.nodeSizeMultiplier,
                    baseSize: baseSize,
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
