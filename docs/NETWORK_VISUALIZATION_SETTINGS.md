# Network Viewer Reference

**Last updated**: October 14, 2026
**Code**: `frontend/static/js/network-viz-graphology.js` (class `GraphologyNetworkVisualizer`) and
`frontend/templates/networks/visualize.html` (Alpine component `networkViewer`)
**Based on**: some2net visualization patterns (https://github.com/dimelab/some2net)

The viewer loads a network's GEXF file from `/api/networks/{id}/download`, builds a
Graphology graph once, and renders it with Sigma.js 2.4.0 (WebGL). Layout is
ForceAtlas2 from `graphology-library` 0.8.0. All libraries load from CDN in `base.html`;
there is no build step.

This file replaces the earlier implementation summary, which covered only the node-size
slider and the giant-component filter. For the history of the move from Vis.js see
[GRAPHOLOGY_MIGRATION.md](GRAPHOLOGY_MIGRATION.md).

---

## What the viewer needs from the GEXF

The viewer reads the GEXF `<attributes>` table, so node attributes are keyed by their
title (`node_type`, not the numeric id networkx writes) and cast by declared type.

| Node attribute | Used for | If missing |
|----------------|----------|------------|
| `node_type` | Colour (Type mode), type filter, selected-node panel | Node is type `default` |
| `eigenvector` | Node size (undirected networks) | Falls back to degree |
| `pagerank` | Node size (directed networks), takes priority over `eigenvector` | Falls back to `eigenvector`, then degree |
| `component` | Per-component scaling of `eigenvector` sizes | Graph is treated as one component |
| `community` | Community colour mode | Community option is disabled |
| `weight` (node) | Selected-node panel only | Not shown |

`community`, `component`, `eigenvector` and `pagerank` are added by the backend when a
network is generated; see "Node Metrics" in
[NETWORK_GENERATION_GUIDE.md](NETWORK_GENERATION_GUIDE.md). Networks generated before that
was added need `python scripts/annotate_networks.py`; until then they show degree-based
sizes and Type colours only.

A GEXF attribute whose name collides with a field the renderer owns (`x`, `y`, `size`,
`color`, `label`, `type`, `hidden`, `node_type`, ...) is stored as `attr_<name>` so it can
never override rendering. Nodes without a `viz:position` are placed on a circle; nothing
is laid out until the user presses Start Layout.

---

## Controls

### Node size

Size comes from a centrality score, chosen once per file: `pagerank` if any node has it,
else `eigenvector`, else full-graph degree. The panel under the Node Size slider says which
one is in use.

- **Eigenvector is scaled per component.** The backend stores eigenvector values
  normalised within each connected component, so a 2-node component scores 0.707 per node,
  more than the giant component's hub. The viewer multiplies each score by
  `sqrt(n_component / N)`, which gives each component a share of squared mass proportional
  to its node count. PageRank and degree are already comparable across the graph and get no
  scaling.
- Scores map to a base size of 5-30 px on a square-root scale (`NODE_SIZE_MIN` and
  `NODE_SIZE_MAX` at the top of the JS file).
- The **Node Size** slider (ForceAtlas2 settings panel) is a global multiplier, 0.1x-3.0x,
  default 0.5x. At the default, a typical node is about 4 px and the largest hub about
  15 px on the 835-node test network.
- Sizes are computed over all nodes at load, so filters never change them.

### Colour

A **Colour by** switch in the sidebar:

- **Type** (default): one colour per `node_type`. In a bipartite network that is the two
  sides. Known types have fixed colours (`website` green, `keyword`/`noun` amber, `query`/
  `search` blue, `entity` purple, `topic`/`concept` pink); unknown types get a stable
  colour hashed from the type name.
- **Community**: the 10 largest communities (rank 0-9, numbered by the backend, 0 =
  largest) get the palette in `COMMUNITY_PALETTE`; every other community is gray
  (`#CBD5E1`). Disabled when the file has no `community` attribute.

### Labels

The **Labels** toolbar button turns node labels on or off (default on). Sigma still decides
which labels fit at the current zoom, so a dense network shows few labels until zoomed in.

### Filters

Applied in this order, through Sigma reducers (the graph is not rebuilt, so layout
positions survive):

1. **Type** checkboxes (built from the types in the file) and **Search** (case-insensitive
   substring of the label).
2. **Giant Component Only**: the largest connected component among the nodes that passed
   step 1.
3. **Min. Degree** (0-20): keeps nodes with at least that many neighbours among the nodes
   that passed steps 1-2. One pass, not repeated until stable.

**Clear All Filters** resets all four. The statistics panel (nodes, edges, density, average
degree) describes the visible subgraph.

### Layout

**Start Layout** / **Stop Layout** run ForceAtlas2, one synchronous iteration per animation
frame on the main thread, on the full graph (including nodes hidden by filters). The
settings panel (gear icon) sets gravity (0-5), scaling (1-50), edge weight influence (0-2)
and Barnes-Hut; changes apply on the next frame without restarting. Large networks will
make the page less responsive while the layout runs.

### Selection and navigation

Click a node to see its type, degree (among visible nodes) and, when present, weight,
community, eigenvector and PageRank. Double-click a node to zoom to it. Keys **+** / **=**,
**-** and **0** zoom in, zoom out and fit the view.

### Export

The **Export** menu offers:

- **PNG image**: composites Sigma's `edges`, `edgeLabels`, `nodes` and `labels` canvases
  onto a white background at the backing-store resolution. It shows exactly what is on
  screen: current filters, colour mode and label setting. Sigma 2.4.0 does not keep the
  nodes layer's pixels after rendering, so export re-renders and copies every layer in the
  same task.
- **GEXF (Gephi)**, **GraphML**, **Edge list (CSV)**, **JSON**: plain links to
  `/api/networks/{id}/download?format=...`. These are the stored network, not the filtered
  view. GEXF, GraphML and JSON include the node metrics; the CSV edge list has edges only.

---

## Limits and known gaps

- **Undirected only.** The graph is created undirected, so a duplicate edge is skipped (with
  one console warning) and its weight is lost. No network builder produces directed graphs
  today, so PageRank is computed by the backend only if one ever does.
- **Metrics do not follow filters.** Communities and centralities are computed once on the
  whole network at generation time, not recomputed for the filtered subgraph.
- **No node dragging.**
- **Keyboard shortcuts.** `+`, `-` and `0` work through a handler in the page. The "Network"
  group in `keyboard-shortcuts.js` (including the "Toggle physics" entry) refers to
  `window.currentNetworkVisualizer`, which nothing sets, so those entries do nothing.
- **Testing.** Verified in headless Chrome with software WebGL against a 14-node and an
  835-node network, driven by throwaway harnesses (not part of the repository). Not tested:
  networks over about 1,000 nodes, Firefox, Safari, mobile, or the live page behind login.
- Sigma is pinned at 2.4.0 and graphology at 0.25.4; moving to Sigma 3 is a separate task.
