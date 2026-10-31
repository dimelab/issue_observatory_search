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
on the main thread, and stops by itself once the drawing has settled. **Stop Layout** ends it
sooner. A network without stored positions starts on a circle, so the first thing to do is
press Start Layout.

The **Layout** switch in the toolbar chooses between two styles:

- **Compact** (the default) uses strong gravity. Everything stays close to the centre, the layout
  settles and fills the view, and small pieces of the network cannot drift away. The price is a
  round drawing whatever the structure of the network.
- **Organic** uses the defaults of Gephi's ForceAtlas2, so the drawing takes the shape of the
  data: a chain of topics comes out as a chain, a strip as a strip, separate topics as separate
  clusters. Only networks that really are round (one big dense core) come out round. It also
  turns on *Keep small components near the main cluster* (see below).

Switching starts the layout from the current positions. If you change one of the settings below
by hand, the switch shows **Custom**; changing it back shows the style again.

The settings panel (gear icon) shows what each style sets, and the rest:

| Setting | Compact | Organic | Effect |
|---------|---------|---------|--------|
| **Strong gravity** | on | off | Gravity that grows with the distance from the centre. Keeps everything compact, but makes every network round; with it, lowering Gravity (about 0.05 is gentle) gives a looser result |
| **Gravity** (0-5) | 1 | 1 | Pull towards the centre. Higher: more compact and rounder. Lower: looser |
| **Scaling** (1-50) | 10 | 2 from 100 nodes, 10 below (Gephi's rule) | Repulsion between nodes. Mostly changes the scale of the drawing, not its shape |
| **Keep small components near the main cluster** | off | on | Holds separate small pieces of the network just outside the main cluster (see below) |
| **Stop automatically when settled** (on) | | | Stops the layout once it has settled; untick to run until you press Stop |
| **Edge Weight** (0-2) | | | How much edge weights pull connected nodes together |
| **Barnes-Hut** | | | Approximates repulsion; faster on large graphs |

Changes apply to a running layout on the next frame. If the layout is stopped, including
after it settled, moving a setting starts it again, so a slider always shows its effect.

**Why Compact is round.** It uses strong gravity with Gravity 1, which is a much harder pull
than ForceAtlas2's own recommendation for strong gravity (0.05). A force that grows with the
distance squeezes every network into the same round blob; the structure only shows inside it.
Measured on synthetic networks (headless Chrome, the layout run for 1,500 iterations with the
settings of the two styles; aspect is the shorter over the longer principal axis of the
drawing, 1 is a circle; fidelity is the correlation between on-screen distance and the number
of edges between two nodes, higher is better):

| Network | Aspect, Compact to Organic | Fidelity, Compact to Organic |
|---------|--------------------|----------------------|
| 36x8 strip (360 nodes) | 0.98 to 0.11 | 0.54 to 0.99 |
| Chain of 6 topics (588) | 0.98 to 0.05 | 0.56 to 0.91 |
| Tree (520) | 1.00 to 0.61 | 0.34 to 0.67 |
| 4 topics, few links between (600) | 0.99 to 0.96 | 0.54 to 0.61 |
| One dense core with hubs (629) | 0.99 to 0.96 | 0.23 to 0.35 |

The last two are round in both versions because their structure is round. What changes is
how well the topics separate: the distance between topic centres divided by the spread
inside a topic goes from 3.1 to 6.1 (600 nodes), and from 3.8 to 7.5 on a network of
2,800 nodes with 8 topics, where Compact gives a single disc.

**What Organic costs.** Without the pull towards the centre, nodes sit in tight clumps: the
single-link neighbours of a hub (a keyword with many sites that appear nowhere else) are
packed around it, and the nodes of a cluster, a chain or a strip lie close together, the way
they do in Gephi. At the fit-to-screen view, in the test networks of chains, strips, trees,
stars and 8 large clusters, 67-98% of the nodes have a neighbour closer than 0.8% of the
main cluster's width, against 0-8% in Compact. Zoom in, or lower **Node Size**, to read
them. Gephi's answer is a separate overlap-removal step (Noverlap), which the viewer
does not have.

**Keeping small components near.** Classic ForceAtlas2 gravity is the same strength
everywhere. A big dense core pushes small, sparsely connected pieces (a few sites that share
one keyword) far out, they keep drifting, and because the view fits the whole drawing the
core ends up small on screen. Gephi has the same behaviour. Strong gravity fixed this only by
making everything round, and raising Gravity does it only by bringing the round shape back
(raising Gravity from 1 to 16 changes the aspect of the test strip from 0.10 to 0.97, while on
the network with stray pieces the main cluster's share of the width only goes from 0.11 to
0.35). So the layout loop does it separately: after every
frame, a component other than the main one whose edge would lie further than 1.3 times the main
component's radius (95th percentile of the distance from its centre) from the main component's
centre is moved back as a whole, and the drawing is re-centred on the main component (the
pieces crowd one side of it and would otherwise push the whole drawing along without end).
Nothing inside a component changes, and networks with a single component are not affected.
In Organic, the share of the drawing's width that the main cluster uses, without and with it:

| Network | Main cluster's share of the width |
|---------|-----------------------------------|
| 506 nodes, 18 small pieces | 0.14 to 0.87 |
| 569 nodes, 60 small pieces | 0.07 to 0.77 |
| 2,553 nodes, 40 small pieces | 0.10 to 1.00 |

It only applies when the largest component holds at least half of the nodes; in a network of
many similar-sized pieces (or with no edges) there is no main cluster to gather them
around, and the layout is plain ForceAtlas2. Untick the setting to get Gephi's behaviour. In
Compact it is off, because strong gravity already keeps the pieces near; ticking it there
shows **Custom**.

**Speed.** Each animation frame runs as many ForceAtlas2 iterations as fit in 10 ms (more
when drawing is slow, up to 40 ms, never more than 40 iterations) instead of one, then
redraws once. The count adapts as it goes. With software WebGL (much slower than a GPU),
the 29-node test network settled in about 1 s, the 588-node chain in about 2 s and the
2,796-node one in about 8 s.

**Settling.** The layout stops when two things hold. First, nodes barely move: every 50
iterations it compares node positions with 50 iterations earlier, and the nodes of the main
component must have moved on average less than 0.05% of the core's size per iteration
(`LAYOUT_SETTLE_MOVE`), with at least 100 iterations run. The core's size is the 5th-95th
percentile range of the positions, not the bounding box, because outliers inflate the box.
Second, the shape is steady: the two principal axes of the drawing must have changed by less
than 5% over the last 200 iterations (`LAYOUT_SHAPE_SPAN`, `LAYOUT_SHAPE_TOLERANCE`). The
second condition matters for chains, strips and trees, which stretch slowly: their nodes move
little per iteration, so the first condition alone stopped the 588-node chain after about 340
iterations at aspect 0.27, where it ends up at 0.05; with both it stops after about 1,100
iterations at 0.07. Small components held at the edge of their allowed zone keep sliding
along it, so only the main component is judged. The slow-down parameter is set to
`1 + ln(nodes)` (ForceAtlas2's own recommendation) when a network loads; it has no slider.

How long it takes to stop, on the synthetic networks (Barnes-Hut on): a few hundred
iterations for networks of clusters and for fragmented ones, roughly 1,000 to 2,500 for chains,
strips and trees, and up to a few thousand for a dense core with hubs, whose nodes keep
jittering a little with the approximate repulsion. Pressing Stop earlier is always possible.

**Quality of stopping early.** The measurements of the earlier versions (835-node network
with the backend's communities and 2,612-node network without, five random starting layouts
per setting) were made with strong gravity: stress, neighbourhood preservation and community
separation were flat from about 450 to 5,000 iterations, strong and classic gravity gave the
same stress, and LinLog mode, which ForceAtlas2 offers to emphasise clusters, was worse on
all measures (stress 0.23-0.33 instead of 0.19) and is not used. They do not carry over to
the Organic style, where chains and strips keep stretching slowly, which is why the second stop condition exists.

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
  In the CSV (and the `edgelist` format) the websites are always in the Source column and
  the other node type (keywords, entities or search queries) in the Target column, so a
  column never mixes the two. Networks that connect nodes of one type only (projections)
  keep NetworkX's order. GEXF, GraphML and JSON still list each edge's endpoints in
  NetworkX order; the networks are undirected, so this does not change what they contain.

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
