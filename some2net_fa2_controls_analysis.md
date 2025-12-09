# some2net ForceAtlas2 Controls Analysis

## Overview
The some2net repository uses Sigma.js with graphology's FA2Layout for interactive network visualization. The implementation provides real-time layout controls embedded in a standalone HTML template.

## 1. HTML Structure for Layout Control Buttons

### Control Panel Container
```html
<div id="controls">
    <h3>Layout Controls</h3>
    <button id="start-layout">▶️ Start Layout</button>
    <button id="stop-layout">⏸️ Stop Layout</button>
    <!-- Settings sliders follow -->
</div>
```

### CSS Styling
```css
#controls {
    position: absolute;
    top: 10px;
    right: 10px;
    background: white;
    padding: 15px;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    z-index: 1000;
    max-width: 250px;
}

#controls button {
    display: block;
    width: 100%;
    margin: 5px 0;
    padding: 8px 12px;
    border: 1px solid #ddd;
    border-radius: 4px;
    background: white;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s;
}

#controls button:hover {
    background: #f0f0f0;
    border-color: #999;
}

#controls button:active {
    background: #e0e0e0;
}
```

## 2. ForceAtlas2 Settings Sliders/Controls

### All Exposed Controls:

1. **Gravity Slider**
```html
<label>
    Gravity: <span id="gravity-value" class="control-value">1.0</span>
    <input type="range" id="gravity" min="0" max="5" step="0.1" value="1.0">
</label>
```

2. **Scaling Slider**
```html
<label>
    Scaling: <span id="scaling-value" class="control-value">10</span>
    <input type="range" id="scaling" min="1" max="50" step="1" value="10">
</label>
```

3. **Edge Weight Slider**
```html
<label>
    Edge Weight: <span id="edge-weight-value" class="control-value">1.0</span>
    <input type="range" id="edge-weight" min="0" max="2" step="0.1" value="1.0">
</label>
```

4. **Node Size Slider**
```html
<label>
    Node Size: <span id="node-size-value" class="control-value">1.0</span>
    <input type="range" id="node-size" min="0.1" max="3.0" step="0.1" value="1.0">
</label>
```

5. **Barnes-Hut Optimization Checkbox**
```html
<div class="checkbox-label">
    <input type="checkbox" id="barnes-hut" checked>
    <span>Barnes-Hut Optimization</span>
</div>
```

### Control Label Styling
```css
#controls label {
    display: block;
    margin-top: 12px;
    margin-bottom: 5px;
    font-size: 12px;
    color: #666;
    font-weight: 500;
}

#controls input[type="range"] {
    width: 100%;
    margin: 5px 0;
}

#controls input[type="checkbox"] {
    margin-right: 5px;
}

.control-value {
    font-weight: bold;
    color: #333;
}

.checkbox-label {
    display: flex;
    align-items: center;
    margin-top: 10px;
    font-size: 12px;
}
```

## 3. Complete Settings Panel Structure

```html
<div id="controls">
    <h3>Layout Controls</h3>

    <!-- Action Buttons -->
    <button id="start-layout">▶️ Start Layout</button>
    <button id="stop-layout">⏸️ Stop Layout</button>

    <!-- Gravity Control -->
    <label>
        Gravity: <span id="gravity-value" class="control-value">1.0</span>
        <input type="range" id="gravity" min="0" max="5" step="0.1" value="1.0">
    </label>

    <!-- Scaling Control -->
    <label>
        Scaling: <span id="scaling-value" class="control-value">10</span>
        <input type="range" id="scaling" min="1" max="50" step="1" value="10">
    </label>

    <!-- Edge Weight Control -->
    <label>
        Edge Weight: <span id="edge-weight-value" class="control-value">1.0</span>
        <input type="range" id="edge-weight" min="0" max="2" step="0.1" value="1.0">
    </label>

    <!-- Node Size Control -->
    <label>
        Node Size: <span id="node-size-value" class="control-value">1.0</span>
        <input type="range" id="node-size" min="0.1" max="3.0" step="0.1" value="1.0">
    </label>

    <!-- Barnes-Hut Optimization -->
    <div class="checkbox-label">
        <input type="checkbox" id="barnes-hut" checked>
        <span>Barnes-Hut Optimization</span>
    </div>
</div>

<!-- Stats Display -->
<div id="stats">
    <div class="stat-item">Nodes: <span id="node-count" class="stat-value">0</span></div>
    <div class="stat-item">Edges: <span id="edge-count" class="stat-value">0</span></div>
</div>
```

## 4. Wiring Controls to FA2Layout Instance

### Dependencies
```html
<script src="https://unpkg.com/graphology@0.25.4/dist/graphology.umd.min.js"></script>
<script src="https://unpkg.com/sigma@2.4.0/build/sigma.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/graphology-library@0.8.0/dist/graphology-library.min.js"></script>
```

### FA2Layout Initialization
```javascript
// Access Force Atlas 2 from graphologyLibrary
const forceatlas2 = graphologyLibrary.layoutForceAtlas2;
const FA2Layout = graphologyLibrary.FA2Layout;

let fa2Layout = null;
let layoutRunning = false;

// FA2 Settings object
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

### Start/Stop Button Event Handlers
```javascript
// Start Layout
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

// Stop Layout
document.getElementById('stop-layout').addEventListener('click', () => {
    if (layoutRunning && fa2Layout) {
        console.log('Stopping Force Atlas 2 layout...');
        fa2Layout.stop();
        layoutRunning = false;
    }
});
```

### Settings Control Event Handlers

**Pattern:** When a setting changes, they kill the old layout instance, create a new one with updated settings, and restart if it was running.

#### Gravity Control
```javascript
document.getElementById('gravity').addEventListener('input', (e) => {
    fa2Settings.gravity = parseFloat(e.target.value);
    document.getElementById('gravity-value').textContent = e.target.value;
    if (fa2Layout) {
        fa2Layout.kill();
        fa2Layout = new FA2Layout(graph, { settings: fa2Settings });
        if (layoutRunning) fa2Layout.start();
    }
});
```

#### Scaling Control
```javascript
document.getElementById('scaling').addEventListener('input', (e) => {
    fa2Settings.scalingRatio = parseFloat(e.target.value);
    document.getElementById('scaling-value').textContent = e.target.value;
    if (fa2Layout) {
        fa2Layout.kill();
        fa2Layout = new FA2Layout(graph, { settings: fa2Settings });
        if (layoutRunning) fa2Layout.start();
    }
});
```

#### Edge Weight Control
```javascript
document.getElementById('edge-weight').addEventListener('input', (e) => {
    fa2Settings.edgeWeightInfluence = parseFloat(e.target.value);
    document.getElementById('edge-weight-value').textContent = e.target.value;
    if (fa2Layout) {
        fa2Layout.kill();
        fa2Layout = new FA2Layout(graph, { settings: fa2Settings });
        if (layoutRunning) fa2Layout.start();
    }
});
```

#### Barnes-Hut Checkbox
```javascript
document.getElementById('barnes-hut').addEventListener('change', (e) => {
    fa2Settings.barnesHutOptimize = e.target.checked;
    if (fa2Layout) {
        fa2Layout.kill();
        fa2Layout = new FA2Layout(graph, { settings: fa2Settings });
        if (layoutRunning) fa2Layout.start();
    }
});
```

#### Node Size Control (Visual Only)
```javascript
document.getElementById('node-size').addEventListener('input', (e) => {
    const sizeMultiplier = parseFloat(e.target.value);
    document.getElementById('node-size-value').textContent = e.target.value;

    // Update all node sizes
    graph.forEachNode((node) => {
        const originalSize = originalNodeSizes[node];
        graph.setNodeAttribute(node, 'size', originalSize * sizeMultiplier);
    });
    renderer.refresh();
});
```

## 5. Tooltips and Help Text

### No Built-in Tooltips in HTML
The HTML template itself does not include tooltips on the controls. However, they do provide usage instructions in the Python Streamlit app:

### Python App Instructions (from app.py)
```python
st.caption("""
**How to interact:**
- 🖱️ Hover over nodes to see details
- 🔍 Zoom with scroll wheel
- 🖐️ Pan by clicking and dragging
- ▶️ Use controls on the right to adjust the layout in real-time
- 🔍 Toggle "Giant Component Only" above to focus on the main connected network
- 🎨 Node colors: Blue=Authors, Orange=Persons, Green=Locations, Red=Organizations
- 💡 The layout is computed in your browser using Force Atlas 2
""")
```

### Pre-visualization Slider in Python
```python
layout_iterations = st.slider(
    "Visualization Quality",
    50, 200, 100, 10,
    help="Force Atlas iterations (higher = better layout, slower)"
)
```

## 6. Additional Features

### Stats Display
```html
<div id="stats">
    <div class="stat-item">Nodes: <span id="node-count" class="stat-value">0</span></div>
    <div class="stat-item">Edges: <span id="edge-count" class="stat-value">0</span></div>
</div>
```

```javascript
// Update stats
document.getElementById('node-count').textContent = graph.order;
document.getElementById('edge-count').textContent = graph.size;
```

### Node Hover Highlighting
```javascript
renderer.on('enterNode', ({ node }) => {
    renderer.getGraph().setNodeAttribute(node, 'highlighted', true);
});

renderer.on('leaveNode', ({ node }) => {
    renderer.getGraph().setNodeAttribute(node, 'highlighted', false);
});
```

### Graph Initialization with Circular Layout
```javascript
// Store original node sizes for scaling
const originalNodeSizes = {};

// Add nodes with circular layout
const nodeCount = graphData.nodes.length;
graphData.nodes.forEach((node, index) => {
    originalNodeSizes[node.key] = node.size;

    // Circular layout
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

## 7. Data Injection Method

### Python Side (app.py)
```python
# Load HTML template
template_path = Path(__file__).parent / 'templates' / 'sigma_viewer.html'
with open(template_path, 'r') as f:
    html_template = f.read()

# Inject graph data
html_content = html_template.replace(
    '{{GRAPH_DATA}}',
    graph_json
)

# Display in Streamlit
components.html(html_content, height=850, scrolling=False)
```

### JavaScript Side (template)
```javascript
// Graph data will be injected here
const graphData = {{GRAPH_DATA}};
```

## Key Design Decisions

1. **Real-time Control Updates**: Changes to settings require killing and recreating the FA2Layout instance
2. **Separate Visual Controls**: Node size is purely visual and doesn't affect the layout algorithm
3. **Barnes-Hut Default**: Optimization is enabled by default for better performance
4. **Circular Initial Layout**: Nodes start in a circle to provide a stable starting point
5. **Minimal Settings Exposed**: Only 5 key FA2 parameters exposed to users (gravity, scaling, edge weight, Barnes-Hut, and visual node size)
6. **Clean Panel Design**: Simple, modern UI with clear labels and real-time value display
7. **No Tooltips**: Relies on clear labeling rather than hover tooltips

## Complete FA2 Settings Object

```javascript
const fa2Settings = {
    adjustSizes: false,                          // Not exposed to users
    barnesHutOptimize: true,                     // Controlled by checkbox
    barnesHutTheta: 1.2,                         // Fixed value
    edgeWeightInfluence: 1.0,                    // Controlled by slider (0-2)
    gravity: 1.0,                                // Controlled by slider (0-5)
    linLogMode: false,                           // Not exposed to users
    outboundAttractionDistribution: true,        // Not exposed to users
    scalingRatio: 10,                            // Controlled by slider (1-50)
    slowDown: 1,                                 // Not exposed to users
    strongGravityMode: false                     // Not exposed to users
};
```
