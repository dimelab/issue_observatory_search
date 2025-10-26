/**
 * Network Visualization using Vis.js
 *
 * Handles interactive network graph visualization with GEXF support
 *
 * Features:
 * - Load and parse GEXF files
 * - Interactive pan and zoom
 * - Node selection and details
 * - Search nodes by label
 * - Filter by node type
 * - Physics simulation toggle
 * - Multiple layout options
 * - Export as PNG
 */

class NetworkVisualizer {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        this.network = null;
        this.nodes = new vis.DataSet();
        this.edges = new vis.DataSet();
        this.rawData = null;

        // Configuration
        this.options = {
            physics: options.physics !== undefined ? options.physics : true,
            layout: options.layout || 'forceAtlas2',
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
     * Initialize the network visualization
     */
    init() {
        if (!this.container) {
            console.error('Container not found:', this.containerId);
            return;
        }

        // Vis.js options
        const visOptions = {
            nodes: {
                shape: 'dot',
                size: 16,
                font: {
                    size: 14,
                    face: 'Arial'
                },
                borderWidth: 2,
                shadow: true
            },
            edges: {
                width: 1,
                color: { inherit: 'from' },
                smooth: {
                    type: 'continuous'
                },
                arrows: {
                    to: { enabled: false }
                }
            },
            physics: {
                enabled: this.options.physics,
                forceAtlas2Based: {
                    gravitationalConstant: -26,
                    centralGravity: 0.005,
                    springLength: 230,
                    springConstant: 0.18
                },
                maxVelocity: 146,
                solver: 'forceAtlas2Based',
                timestep: 0.35,
                stabilization: { iterations: 150 }
            },
            interaction: {
                hover: true,
                tooltipDelay: 200,
                zoomView: true,
                dragView: true
            }
        };

        // Create network
        const data = {
            nodes: this.nodes,
            edges: this.edges
        };

        this.network = new vis.Network(this.container, data, visOptions);

        // Event listeners
        this.setupEventListeners();
    }

    /**
     * Setup event listeners for network interactions
     */
    setupEventListeners() {
        // Node selection
        this.network.on('selectNode', (params) => {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                this.selectedNode = this.nodes.get(nodeId);
                this.onNodeSelect(this.selectedNode);
            }
        });

        // Node deselection
        this.network.on('deselectNode', () => {
            this.selectedNode = null;
            this.onNodeDeselect();
        });

        // Double click to focus
        this.network.on('doubleClick', (params) => {
            if (params.nodes.length > 0) {
                this.focusNode(params.nodes[0]);
            }
        });

        // Stabilization progress
        this.network.on('stabilizationProgress', (params) => {
            const progress = Math.round((params.iterations / params.total) * 100);
            this.onStabilizationProgress(progress);
        });

        this.network.on('stabilizationIterationsDone', () => {
            this.onStabilizationComplete();
        });
    }

    /**
     * Load network from GEXF file URL
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
            this.parseGEXF(gexfText);

        } catch (error) {
            console.error('Error loading GEXF:', error);
            showToast('Failed to load network visualization', 'error');
        }
    }

    /**
     * Parse GEXF XML and convert to Vis.js format
     */
    parseGEXF(gexfText) {
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(gexfText, 'text/xml');

        // Check for parsing errors
        const parserError = xmlDoc.querySelector('parsererror');
        if (parserError) {
            throw new Error('Invalid GEXF format');
        }

        // Parse nodes
        const nodesData = [];
        const xmlNodes = xmlDoc.querySelectorAll('node');

        xmlNodes.forEach(xmlNode => {
            const id = xmlNode.getAttribute('id');
            const label = xmlNode.getAttribute('label') || id;

            // Parse attributes
            const attributes = {};
            xmlNode.querySelectorAll('attvalue').forEach(attr => {
                const key = attr.getAttribute('for');
                const value = attr.getAttribute('value');
                attributes[key] = value;
            });

            // Parse position if available
            let x, y;
            const vizPosition = xmlNode.querySelector('viz\\:position, position');
            if (vizPosition) {
                x = parseFloat(vizPosition.getAttribute('x')) || undefined;
                y = parseFloat(vizPosition.getAttribute('y')) || undefined;
            }

            // Determine node color based on type
            const nodeType = attributes.type || 'default';
            const color = this.getNodeColor(nodeType);

            nodesData.push({
                id,
                label,
                title: this.createNodeTooltip(label, attributes),
                color,
                x,
                y,
                ...attributes
            });
        });

        // Parse edges
        const edgesData = [];
        const xmlEdges = xmlDoc.querySelectorAll('edge');

        xmlEdges.forEach(xmlEdge => {
            const id = xmlEdge.getAttribute('id');
            const source = xmlEdge.getAttribute('source');
            const target = xmlEdge.getAttribute('target');
            const weight = parseFloat(xmlEdge.getAttribute('weight')) || 1;

            edgesData.push({
                id,
                from: source,
                to: target,
                value: weight,
                title: `Weight: ${weight}`
            });
        });

        // Store raw data
        this.rawData = { nodes: nodesData, edges: edgesData };

        // Load into network
        this.nodes.clear();
        this.edges.clear();
        this.nodes.add(nodesData);
        this.edges.add(edgesData);

        // Fit to viewport
        setTimeout(() => {
            this.network.fit({
                animation: {
                    duration: 1000,
                    easingFunction: 'easeInOutQuad'
                }
            });
        }, 500);
    }

    /**
     * Get node color based on type
     */
    getNodeColor(nodeType) {
        const colorMap = {
            'search': '#3B82F6',      // Blue
            'website': '#10B981',      // Green
            'noun': '#F59E0B',         // Amber
            'entity': '#8B5CF6',       // Purple
            'topic': '#EC4899',        // Pink
            'default': '#6B7280'       // Gray
        };

        return colorMap[nodeType] || colorMap.default;
    }

    /**
     * Create tooltip for node
     */
    createNodeTooltip(label, attributes) {
        let tooltip = `<strong>${label}</strong>`;

        if (attributes.type) {
            tooltip += `<br>Type: ${attributes.type}`;
        }

        if (attributes.weight) {
            tooltip += `<br>Weight: ${attributes.weight}`;
        }

        return tooltip;
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

        let filteredNodes = this.rawData.nodes;

        // Filter by type
        if (this.filters.nodeTypes.length > 0) {
            filteredNodes = filteredNodes.filter(node =>
                this.filters.nodeTypes.includes(node.type || 'default')
            );
        }

        // Filter by search query
        if (this.filters.search) {
            filteredNodes = filteredNodes.filter(node =>
                node.label.toLowerCase().includes(this.filters.search)
            );
        }

        // Get node IDs
        const nodeIds = filteredNodes.map(n => n.id);

        // Filter edges to only include edges between visible nodes
        const filteredEdges = this.rawData.edges.filter(edge =>
            nodeIds.includes(edge.from) && nodeIds.includes(edge.to)
        );

        // Update network
        this.nodes.clear();
        this.edges.clear();
        this.nodes.add(filteredNodes);
        this.edges.add(filteredEdges);
    }

    /**
     * Clear all filters
     */
    clearFilters() {
        this.filters.nodeTypes = [];
        this.filters.search = '';

        if (this.rawData) {
            this.nodes.clear();
            this.edges.clear();
            this.nodes.add(this.rawData.nodes);
            this.edges.add(this.rawData.edges);
        }
    }

    /**
     * Toggle physics simulation
     */
    togglePhysics() {
        const enabled = !this.network.physics.options.enabled;
        this.network.setOptions({ physics: { enabled } });
        return enabled;
    }

    /**
     * Focus on a specific node
     */
    focusNode(nodeId) {
        this.network.focus(nodeId, {
            scale: 1.5,
            animation: {
                duration: 1000,
                easingFunction: 'easeInOutQuad'
            }
        });
    }

    /**
     * Fit network to viewport
     */
    fit() {
        this.network.fit({
            animation: {
                duration: 1000,
                easingFunction: 'easeInOutQuad'
            }
        });
    }

    /**
     * Zoom in
     */
    zoomIn() {
        const scale = this.network.getScale();
        this.network.moveTo({
            scale: scale * 1.2,
            animation: { duration: 300 }
        });
    }

    /**
     * Zoom out
     */
    zoomOut() {
        const scale = this.network.getScale();
        this.network.moveTo({
            scale: scale / 1.2,
            animation: { duration: 300 }
        });
    }

    /**
     * Export network as PNG
     */
    exportAsPNG(filename = 'network.png') {
        const canvas = this.container.querySelector('canvas');
        if (!canvas) {
            showToast('Unable to export visualization', 'error');
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
            showToast('Network exported successfully', 'success');
        });
    }

    /**
     * Get network statistics
     */
    getStatistics() {
        return {
            nodes: this.nodes.length,
            edges: this.edges.length,
            density: this.calculateDensity(),
            avgDegree: this.calculateAverageDegree()
        };
    }

    /**
     * Calculate network density
     */
    calculateDensity() {
        const n = this.nodes.length;
        const m = this.edges.length;
        if (n <= 1) return 0;
        return (2 * m) / (n * (n - 1));
    }

    /**
     * Calculate average degree
     */
    calculateAverageDegree() {
        const n = this.nodes.length;
        const m = this.edges.length;
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

    onStabilizationProgress(progress) {
        // Override this method to show stabilization progress
        console.log('Stabilization progress:', progress);
    }

    onStabilizationComplete() {
        // Override this method when stabilization completes
        console.log('Stabilization complete');
    }

    /**
     * Destroy network instance
     */
    destroy() {
        if (this.network) {
            this.network.destroy();
            this.network = null;
        }
    }
}

// Export for use in templates
window.NetworkVisualizer = NetworkVisualizer;
