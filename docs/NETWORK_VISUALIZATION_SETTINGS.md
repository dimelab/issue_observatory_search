# Network Viewer Reference

**Last updated**: October 15, 2026
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
| `eigenvector` | "Size by" Eigenvector, the starting choice for undirected networks | Option is disabled; starts on Degree |
| `pagerank` | "Size by" PageRank, offered only when present and then the starting choice | Option is not listed |
| `component` | Per-component scaling of `eigenvector` sizes | Graph is treated as one component |
| `community` | Community colour mode | Community option is disabled |
| `weight` (node) | Selected-node panel only | Not shown |

`community`, `component`, `eigenvector` and `pagerank` are added by the backend when a
network is generated; see "Node Metrics" in
[NETWORK_GENERATION_GUIDE.md](NETWORK_GENERATION_GUIDE.md). Networks generated before that
was added need `python scripts/annotate_networks.py`; until then they show degree-based
sizes and Type colours only. Degree and betweenness need nothing from the file: the viewer
computes them from the graph it loaded.

A GEXF attribute whose name collides with a field the renderer owns (`x`, `y`, `size`,
`color`, `label`, `type`, `hidden`, `node_type`, ...) is stored as `attr_<name>` so it can
never override rendering. Nodes without a `viz:position` are placed on a circle; nothing
is laid out until the user presses Start Layout.

---

## Controls

### Node size

The **Size by** card in the sidebar picks what node size is based on:

| Option | Meaning | Where it comes from |
|--------|---------|---------------------|
| Degree | Number of connections (all nodes of the file, not the filtered view) | Computed in the browser |
| Eigenvector | Linked to well-connected nodes | The file's `eigenvector` attribute; disabled ("no data") without it |
| Betweenness | Lies on many shortest paths between other nodes | Computed in the browser on first use, then kept |
| PageRank | Share of random-walk visits | The file's `pagerank` attribute; only listed when present (directed networks) |

The viewer starts on PageRank if the file has it, else Eigenvector, else Degree, and the
text under the dropdown says what the current choice measures.

- **Eigenvector is scaled per component.** The backend stores eigenvector values
  normalised within each connected component, so a 2-node component scores 0.707 per node,
  more than the giant component's hub. The viewer multiplies each score by
  `sqrt(n_component / N)`, which gives each component a share of squared mass proportional
  to its node count. The other metrics are comparable across the graph and get no scaling.
- **Betweenness is unweighted.** Edge weights here are association strengths (higher =
  closer), while shortest-path code reads a weight as a distance, so weights are ignored.
  It is exact (it matches NetworkX `betweenness_centrality` on the 835-node test network)
  but runs on the main thread and grows with the square of the node count: about 0.1 s at
  800 nodes, 1 s at 3,400 and 3.4 s at 6,000. Above 8,000 nodes the page asks before
  computing it (`BETWEENNESS_SLOW_NODES`). Betweenness is very skewed (most nodes score
  near zero), so on the test network the typical node is about 3 px and a few bridges stand
  out; Eigenvector gives about 4 px.
- Scores map to a base size of 5-30 px on a square-root scale (`NODE_SIZE_MIN` and
  `NODE_SIZE_MAX` at the top of the JS file).
- The **Node Size** slider (ForceAtlas2 settings panel) is a global multiplier, 0.1x-3.0x,
  default 0.5x. At the default, a typical eigenvector-sized node is about 4 px and the
  largest hub about 15 px on the 835-node test network.
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

The **All labels** button (enabled while Labels is on) labels every visible node whatever the
zoom, and moves nodes apart so the labels do not overlap at the zoom you are at when you press
it. Sigma's `forceLabel` bypasses its one-label-per-cell rule and size threshold; the moving
is done by the viewer:

1. Every node gets a box in screen pixels (its circle plus its label as Sigma draws it).
2. The whole layout is scaled up about its centre by the smallest factor (at most 12x) that
   leaves no more than 1.5 overlapping pairs per node. A dense core needs this: pushing wide,
   short boxes apart pair by pair only stacks them into one tall column.
3. The overlaps that remain are pushed apart locally, large nodes moving less than small
   ones, until none are left or 2.5 seconds are up.

Because Sigma scales positions to the bounding box, the camera is then set to the same centre
and pixels-per-unit as before, and node circles keep their on-screen size. So you see the
same part of the network, with every label readable, and the network now extends well beyond
the screen: pan to see the rest. On the 835-node test network the layout grew 9x and the
spread took about 0.45 s; the note under the toolbar reports how many nodes moved and how
many overlaps remain.

- **Zooming out brings overlaps back.** Labels have a fixed pixel size, so no placement can
  keep them apart at every zoom. Turn the button off and on again to spread for the zoom you
  are at now.
- **Off restores the positions** (and the view) from before, unless a layout has run since,
  in which case the nodes stay where the layout left them.
- Hidden (filtered-out) nodes are neither moved nor counted. After changing filters, turn the
  button off and on again to include the newly visible nodes.
- PNG export includes the labels as drawn.

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
- **Testing.** Verified in headless Chrome with software WebGL against a 9-node and an
  835-node network, driven by throwaway harnesses (not part of the repository). The label
  spreading was also run on synthetic box sets of up to 3,000 nodes (uniform, clustered, all
  on one point): it stayed finite everywhere, converged up to about 2,500 nodes, and at 3,000
  nodes in one screen it hit the 2.5 s limit with about 99.5% of the overlaps removed. Not
  tested: real networks over about 1,000 nodes, Firefox, Safari, mobile, or the live page
  behind login.
- Sigma is pinned at 2.4.0 and graphology at 0.25.4; moving to Sigma 3 is a separate task.
