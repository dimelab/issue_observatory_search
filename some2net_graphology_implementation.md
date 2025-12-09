# some2net Graphology + Sigma.js Implementation

## Overview
The some2net repository contains a working implementation of graphology + Sigma.js for network visualization. The implementation is found in two key files:

1. **test_visualization.html** - Standalone test file
2. **src/cli/templates/sigma_viewer.html** - Template for production use

## Key Implementation Details

### 1. Library Dependencies (CDN)

```html
<script src="https://unpkg.com/graphology@0.25.4/dist/graphology.umd.min.js"></script>
<script src="https://unpkg.com/sigma@2.4.0/build/sigma.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/graphology-library@0.8.0/dist/graphology-library.min.js"></script>
```

**Critical**: The `graphology-library` package contains the ForceAtlas2 implementation.

### 2. Creating the Graphology Graph

```javascript
// Create a directed graph
const graph = new graphology.DirectedGraph();

// Add nodes with initial circular layout
const nodeCount = graphData.nodes.length;
graphData.nodes.forEach((node, index) => {
    // Circular layout for initial positions
    const angle = (2 * Math.PI * index) / nodeCount;
    const radius = 0.5;

    graph.addNode(node.key, {
        label: node.label,
        size: node.size,
        color: node.color,
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius
    });
});

// Add edges with weights
graphData.edges.forEach(edge => {
    try {
        graph.addEdge(edge.source, edge.target, {
            weight: edge.weight,
            size: Math.min(edge.weight * 0.5, 5)
        });
    } catch (e) {
        // Skip duplicate edges
        console.warn('Skipping edge:', edge, e.message);
    }
});
```

### 3. Data Format

The graph data uses this JSON structure:

```javascript
const graphData = {
    "nodes": [
        {
            "key": "1",
            "label": "Node 1",
            "size": 5,
            "color": "#1f77b4"
        }
    ],
    "edges": [
        {
            "key": "edge_0",
            "source": "1",
            "target": "2",
            "weight": 5
        }
    ]
};
```

### 4. Sigma.js Renderer Initialization

```javascript
const container = document.getElementById('container');
const renderer = new Sigma(graph, container, {
    renderEdgeLabels: false,
    defaultNodeColor: '#999',
    defaultEdgeColor: '#ccc',
    labelSize: 14,
    labelWeight: 'bold',
    labelColor: { color: '#000' },
    minCameraRatio: 0.1,
    maxCameraRatio: 10
});
```

### 5. ForceAtlas2 Layout Configuration

```javascript
// Access ForceAtlas2 from graphology-library
const forceatlas2 = graphologyLibrary.layoutForceAtlas2;
const FA2Layout = graphologyLibrary.FA2Layout;

let fa2Layout = null;
let layoutRunning = false;

// Configure ForceAtlas2 settings
const fa2Settings = {
    adjustSizes: false,
    barnesHutOptimize: true,
    barnesHutTheta: 1.2,
    edgeWeightInfluence: 1.0,
    gravity: 1.0,
    linLogMode: false,
    outboundAttractionDistribution: true,
    scalingRatio: 10,
    slowDown: 1,
    strongGravityMode: false
};
```

### 6. Starting/Stopping the Layout

```javascript
// Start layout
document.getElementById('start-layout').addEventListener('click', () => {
    if (!layoutRunning) {
        console.log('Starting Force Atlas 2 layout...');

        if (!fa2Layout) {
            fa2Layout = new FA2Layout(graph, {
                settings: fa2Settings
            });
        }

        fa2Layout.start();
        layoutRunning = true;
    }
});

// Stop layout
document.getElementById('stop-layout').addEventListener('click', () => {
    if (layoutRunning && fa2Layout) {
        console.log('Stopping Force Atlas 2 layout...');
        fa2Layout.stop();
        layoutRunning = false;
    }
});
```

### 7. Dynamic Settings Updates

When updating settings, you need to kill the old layout and create a new one:

```javascript
document.getElementById('gravity').addEventListener('input', (e) => {
    fa2Settings.gravity = parseFloat(e.target.value);
    document.getElementById('gravity-value').textContent = e.target.value;

    if (fa2Layout) {
        fa2Layout.kill();  // Important: kill the old layout
        fa2Layout = new FA2Layout(graph, { settings: fa2Settings });
        if (layoutRunning) fa2Layout.start();
    }
});
```

### 8. Node Size Scaling

```javascript
// Store original node sizes
const originalNodeSizes = {};
graphData.nodes.forEach((node) => {
    originalNodeSizes[node.key] = node.size;
});

// Scale node sizes
document.getElementById('node-size').addEventListener('input', (e) => {
    const sizeMultiplier = parseFloat(e.target.value);

    graph.forEachNode((node) => {
        const originalSize = originalNodeSizes[node];
        graph.setNodeAttribute(node, 'size', originalSize * sizeMultiplier);
    });
    renderer.refresh();
});
```

### 9. Node Hover Events

```javascript
renderer.on('enterNode', ({ node }) => {
    renderer.getGraph().setNodeAttribute(node, 'highlighted', true);
});

renderer.on('leaveNode', ({ node }) => {
    renderer.getGraph().setNodeAttribute(node, 'highlighted', false);
});
```

## Python Backend Integration

The repository includes a NetworkVisualizer class (`src/utils/visualizer.py`) that exports NetworkX graphs to the Sigma.js format:

```python
def export_for_sigma(self, graph: nx.DiGraph, strip_metadata: bool = True) -> Dict:
    """Export graph data in Sigma.js format for front-end visualization."""
    nodes = []
    edges = []

    # Export nodes with logarithmic size scaling
    for node_id, data in graph.nodes(data=True):
        node_type = data.get('node_type', 'unknown')
        mention_count = data.get('mention_count', 0)

        # Logarithmic scaling for node size
        node_size = 3 + math.log1p(mention_count) * 1.5

        node_data = {
            'key': str(node_id),
            'label': data.get('label', str(node_id)),
            'size': node_size,
            'color': self._get_node_color(node_type),
            'type': node_type,
            'mention_count': mention_count,
            'post_count': data.get('post_count', 0)
        }
        nodes.append(node_data)

    # Export edges
    for i, (u, v, data) in enumerate(graph.edges(data=True)):
        edge_data = {
            'key': f'edge_{i}',
            'source': str(u),
            'target': str(v),
            'weight': data.get('weight', 1),
            'type': data.get('entity_type', 'default')
        }
        edges.append(edge_data)

    return {'nodes': nodes, 'edges': edges}
```

## Key Insights

1. **No GEXF Loading**: This implementation doesn't use GEXF files. Instead, it uses a JSON format with nodes and edges arrays.

2. **ForceAtlas2 Access**: The critical piece is accessing ForceAtlas2 through `graphologyLibrary.FA2Layout` from the `graphology-library` package.

3. **Initial Layout**: Nodes are given an initial circular layout with x/y coordinates before ForceAtlas2 starts.

4. **Layout Management**: ForceAtlas2 runs continuously when started and must be explicitly stopped. Settings changes require killing and recreating the layout.

5. **Node Size Scaling**: Uses logarithmic scaling to prevent extreme size differences: `3 + math.log1p(mention_count) * 1.5`

## ForceAtlas2 Settings Explained

- **adjustSizes**: Whether to consider node sizes in the layout (set to false)
- **barnesHutOptimize**: Use Barnes-Hut approximation for faster computation (enabled)
- **barnesHutTheta**: Precision of Barnes-Hut (higher = faster but less accurate)
- **edgeWeightInfluence**: How much edge weights affect the layout (0-2)
- **gravity**: Attraction toward the center (prevents disconnected nodes from floating away)
- **linLogMode**: Use logarithmic attraction (for hub-focused networks)
- **outboundAttractionDistribution**: Distribute attraction by degree
- **scalingRatio**: Overall scaling of the layout
- **slowDown**: Slow down factor for stability
- **strongGravityMode**: Use strong gravity model

## File Paths in Repository

- Main visualization: `test_visualization.html`
- Template: `src/cli/templates/sigma_viewer.html`
- Python exporter: `src/utils/visualizer.py`
