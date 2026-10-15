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
| `community` | Community colour mode, starting point | Communities are detected in the browser when Community is picked |
| `weight` (node) | Selected-node panel only | Not shown |

`community`, `component`, `eigenvector` and `pagerank` are added by the backend when a
network is generated; see "Node Metrics" in
[NETWORK_GENERATION_GUIDE.md](NETWORK_GENERATION_GUIDE.md). Networks generated before that
was added need `python scripts/annotate_networks.py`; until then the Eigenvector size option
is unavailable. Degree and betweenness need nothing from the file (the viewer computes them
from the graph it loaded), and neither does Community colouring: without a `community`
attribute the viewer detects communities itself.

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
- **Community**: the 10 largest communities (rank 0-9, 0 = largest) get the palette in
  `COMMUNITY_PALETTE`; every other community is gray (`#CBD5E1`).

**Where the communities come from.** The network file's `community` attribute is the Louvain
result the backend computed on the whole network when it was generated. A filter changes which
nodes you are looking at, so those communities may no longer describe it. Switching to
**Community** therefore checks whether the visible nodes are the same as when the communities
were last assigned:

- *Unchanged*: nothing happens (switching Type and Community back and forth is free).
- *Changed, and some filter is active*: Louvain runs in the browser on the visible nodes only
  (`detectCommunities`), the same algorithm and seed (42) as the backend, with edge weights
  (an edge with weight 0 or less is ignored). Communities are ranked by size so the palette
  applies as before. It takes about 10 ms at 1,000 nodes and 120 ms at 30,000, so it is not
  noticeable and has no button or progress indicator.
- *Changed, and no filter is active*: the file's communities are put back as they were, not
  recomputed, so clearing the filters returns exactly what the backend produced.
- *No file communities at all*: the same browser run on the whole network, so old
  networks need no `annotate_networks.py` run to be coloured by community.

A line under the switch says which of these you are looking at ("From the network file" or
"Detected in the browser (Louvain) on the 391 visible nodes: 14 communities"). If you change
a filter while Community is already showing, the colours stay as they were and the line adds
"Filters changed since: switch to Type and back to update." Hidden nodes have no community.
If the visible nodes have no edges between them (for example only one side of a bipartite
network), there are no communities and the nodes are drawn gray, and the line says so.

On the 391-node view of the 835-node test network, the browser's communities score a
modularity of 0.3842, against 0.3836 for NetworkX's Louvain on the same subgraph and 0.3357
for the unfiltered communities restricted to it. The selected-node panel shows the community
currently drawn. Downloads (GEXF, GraphML, JSON) are the stored network, so they still carry
only the backend's communities.

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

**Start Layout** runs ForceAtlas2 on the full graph (including nodes hidden by filters),
on the main thread, and stops by itself once the nodes stop moving. **Stop Layout** ends it
sooner. A network without stored positions starts on a circle, so the first thing to do is
press Start Layout.

The settings panel (gear icon):

| Setting | Effect |
|---------|--------|
| **Strong gravity** (on by default) | Gravity that grows with distance from the centre |
| **Stop automatically when settled** (on by default) | Stops the layout once nodes barely move; untick to run until you press Stop |
| **Gravity** (0-5) | With strong gravity: higher is more compact and even, lower is looser with small groups further out |
| **Scaling** (1-50) | Repulsion between nodes: higher spreads the layout out relative to gravity |
| **Edge Weight** (0-2) | How much edge weights pull connected nodes together |
| **Barnes-Hut** | Approximates repulsion; faster on large graphs |

Changes apply to a running layout on the next frame. If the layout is stopped, including
after it settled, moving a setting starts it again, so a slider always shows its effect.

**Why strong gravity is the default.** Classic ForceAtlas2 gravity has the same strength
everywhere. A big dense core then pushes small, sparsely connected subgraphs far out, they
keep drifting, and because the view fits the whole drawing the core ends up as a tight blob
with overlapping nodes (the Gravity and Scaling sliders barely change this). Strong gravity
keeps those subgraphs near, the layout settles, and the core fills the view. On the test
networks, with the same number of iterations as the old defaults (classic gravity):

| Network | Core's share of the drawing, old to new | Overlapping node pairs at the fit view, old to new |
|---------|-----------------------------------------|----------------------------------------------------|
| 835 nodes (real pipeline output) | 0.22 to 0.86 | 7,690 to 66 |
| 2,612 nodes (dense core plus 160 small subgraphs, synthetic) | 0.37 to 0.85 | 641,874 to 4,708 |

(Core share is the square root of the area of the 5th-95th percentile box over the area of
the bounding box; 1 means the core uses the whole drawing.) Untick **Strong gravity** to get
classic ForceAtlas2 back.

**Speed.** Each animation frame runs as many ForceAtlas2 iterations as fit in 10 ms (more
when drawing is slow, up to 40 ms, never more than 40 iterations) instead of one, then
redraws once. The count adapts as it goes. The 835-node network settled after about 450
iterations and the 2,612-node one after about 330 (software WebGL, which draws much slower
than a GPU: 1.6 s and 4.8 s; the old loop took 4.6 s and 33 s for the same graphs).

**Settling.** Every 50 iterations the layout compares node positions with 50 iterations
earlier. It stops when nodes moved on average less than 0.05% of the core's size per
iteration (`LAYOUT_SETTLE_MOVE`) and at least 100 iterations have run. The core's size is
the 5th-95th percentile range of the positions, not the bounding box, because outliers
inflate the box. Classic gravity can also trigger it, usually earlier, while its core is
still slowly collapsing. The slow-down parameter is set to `1 + ln(nodes)`
(ForceAtlas2's own recommendation) when a network loads; it has no slider.

**Does stopping early cost quality?** Measured with layout-quality metrics that do not
depend on scale (835-node network with the backend's communities; 2,612-node network without;
five random starting layouts per setting, mean and spread):

- *Running longer changes nothing measurable.* Stress (how well on-screen distances match graph
  distances), neighbourhood preservation and community separation are flat from about 450 to
  5,000 iterations; the improvement happens in the first few hundred. With a slow-down of 1 the
  layout never settles (still jittering after 13,000 iterations) and is no better for it.
- *Strong gravity keeps the structure.* At the same slow-down, strong and classic gravity give the
  same stress (0.19) and the same community separation (0.776 vs 0.776).
- *One small real cost.* The automatic slow-down `1 + ln(nodes)` that lets the layout settle gives
  somewhat less clear communities on the 835-node network than a slow-down of 1 (within/between
  community distance 0.87 vs 0.77, lower is clearer) and about 12% lower neighbourhood
  preservation. On the 2,612-node network it is much better locally (neighbour preservation 0.20
  vs 0.09 at slow-down 1), which is why it is the default.
- LinLog mode, which ForceAtlas2 offers to emphasise clusters, was worse on all of these
  measures here (stress 0.23-0.33 instead of 0.19) and is not used.

If you would rather watch it keep adjusting, untick **Stop automatically when settled**.

Large networks still run on the main thread: the page stays usable because work per frame is
bounded, but it is not instant.

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
- **Centralities do not follow filters.** Eigenvector and PageRank come from the file and
  betweenness and degree are computed once on the whole network, so node sizes do not change
  when you filter. Communities do follow filters, but only when you switch to Community (see
  Colour).
- **No node dragging.**
- **Keyboard shortcuts.** `+`, `-` and `0` work through a handler in the page. The "Network"
  group in `keyboard-shortcuts.js` (including the "Toggle physics" entry) refers to
  `window.currentNetworkVisualizer`, which nothing sets, so those entries do nothing.
- **Testing.** Verified in headless Chrome with software WebGL against a 9-node and an
  835-node network, driven by throwaway harnesses (not part of the repository). The label
  spreading was also run on synthetic box sets of up to 3,000 nodes (uniform, clustered, all
  on one point): it stayed finite everywhere, converged up to about 2,500 nodes, and at 3,000
  nodes in one screen it hit the 2.5 s limit with about 99.5% of the overlaps removed. Not
  tested: real networks over about 1,000 nodes (the 2,612-node network above is synthetic),
  Firefox, Safari, mobile, or the live page behind login.
- Sigma is pinned at 2.4.0 and graphology at 0.25.4; moving to Sigma 3 is a separate task.
