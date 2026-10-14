"""Node metrics written onto network graphs before export.

``annotate_network`` adds the node attributes the viewer and Gephi use for
colour and size:

- ``community``: Louvain community id (0 is the largest community).
- ``component``: connected-component id (0 is the largest component).
- ``eigenvector``: eigenvector centrality, undirected graphs only.
- ``pagerank``: PageRank, directed graphs only.

Eigenvector centrality is computed separately for each connected component.
On a fragmented graph networkx's whole-graph version concentrates almost all
of the score in the dominant component and leaves the rest near zero. Each
component's scores are L2-normalised on their own, so values are comparable
within a component but not across components; use ``component`` to tell
them apart. Isolated nodes get 0.0.

Edge weights are read from the ``weight`` attribute. A missing or non-numeric
weight counts as 1.0 and a zero or negative weight removes the edge from the
metric calculations only (the graph itself is not changed).
"""
import logging
import math
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import networkx as nx

logger = logging.getLogger(__name__)

DEFAULT_SEED = 42
EIGENVECTOR_MAX_ITER = 1000
EIGENVECTOR_TOL = 1e-8


def annotate_network(
    graph: nx.Graph,
    seed: int = DEFAULT_SEED,
    resolution: float = 1.0,
) -> Dict[str, Any]:
    """
    Add community, component and centrality attributes to the nodes of a graph.

    The graph is modified in place. Call this after backboning and before
    export so the metrics describe the network that is actually shown.

    Args:
        graph: NetworkX graph (undirected or directed)
        seed: Random seed for Louvain, so repeated runs give the same result
        resolution: Louvain resolution (higher gives more, smaller communities)

    Returns:
        JSON-serializable summary: size_metric, community_count, modularity,
        component_count, centrality_fallback_nodes, louvain_seed and
        louvain_resolution
    """
    summary: Dict[str, Any] = {
        "size_metric": None,
        "community_count": 0,
        "modularity": None,
        "component_count": 0,
        "centrality_fallback_nodes": 0,
        "louvain_seed": seed,
        "louvain_resolution": resolution,
    }

    if graph.number_of_nodes() == 0:
        return summary

    undirected = _cleaned_copy(graph, nx.Graph)

    components = _rank_sets(nx.connected_components(undirected))
    nx.set_node_attributes(graph, _membership(components), "component")
    summary["component_count"] = len(components)

    communities, modularity = _detect_communities(undirected, seed, resolution)
    nx.set_node_attributes(graph, _membership(communities), "community")
    summary["community_count"] = len(communities)
    summary["modularity"] = modularity

    if graph.is_directed():
        pagerank = _pagerank(_cleaned_copy(graph, nx.DiGraph))
        if pagerank is not None:
            nx.set_node_attributes(graph, pagerank, "pagerank")
            summary["size_metric"] = "pagerank"
    else:
        eigenvector, fallback_nodes = _eigenvector_by_component(
            undirected, components
        )
        nx.set_node_attributes(graph, eigenvector, "eigenvector")
        summary["size_metric"] = "eigenvector"
        summary["centrality_fallback_nodes"] = fallback_nodes

    logger.info(
        f"Annotated network: {graph.number_of_nodes()} nodes, "
        f"{summary['community_count']} communities, "
        f"{summary['component_count']} components, "
        f"size_metric={summary['size_metric']}"
    )

    return summary


def _clean_weight(value: Any) -> Optional[float]:
    """Return a usable edge weight, or None if the edge should be ignored."""
    if value is None:
        return 1.0
    try:
        weight = float(value)
    except (TypeError, ValueError):
        return 1.0
    if not math.isfinite(weight):
        return 1.0
    return weight if weight > 0 else None


def _cleaned_copy(graph: nx.Graph, factory: Callable[[], nx.Graph]) -> nx.Graph:
    """
    Copy nodes and edges into a fresh graph with validated, summed weights.

    With ``nx.Graph`` as the factory, edges between the same pair of nodes
    (reciprocal directed edges, parallel multigraph edges) are merged and
    their weights added.
    """
    cleaned = factory()
    cleaned.add_nodes_from(graph.nodes)

    for u, v, data in graph.edges(data=True):
        weight = _clean_weight(data.get("weight"))
        if weight is None:
            continue
        if cleaned.has_edge(u, v):
            cleaned[u][v]["weight"] += weight
        else:
            cleaned.add_edge(u, v, weight=weight)

    return cleaned


def _rank_sets(groups: Any) -> List[Set[Any]]:
    """Order node sets largest first, breaking ties deterministically."""
    return sorted(
        (set(group) for group in groups),
        key=lambda group: (-len(group), min(str(node) for node in group)),
    )


def _membership(ranked_groups: List[Set[Any]]) -> Dict[Any, int]:
    """Map each node to the index of the group it belongs to."""
    return {
        node: index for index, group in enumerate(ranked_groups) for node in group
    }


def _detect_communities(
    undirected: nx.Graph,
    seed: int,
    resolution: float,
) -> Tuple[List[Set[Any]], Optional[float]]:
    """Run weighted Louvain; returns communities (largest first) and modularity."""
    if undirected.number_of_edges() == 0:
        # Louvain is undefined without edges: every node is its own community
        return _rank_sets({node} for node in undirected.nodes), None

    communities = nx.community.louvain_communities(
        undirected, weight="weight", resolution=resolution, seed=seed
    )
    modularity = nx.community.modularity(
        undirected, communities, weight="weight", resolution=resolution
    )
    return _rank_sets(communities), float(modularity)


def _eigenvector_by_component(
    undirected: nx.Graph,
    components: List[Set[Any]],
) -> Tuple[Dict[Any, float], int]:
    """
    Eigenvector centrality computed on each connected component in turn.

    Returns the scores and the number of nodes that fell back to normalised
    weighted degree because the power iteration did not converge.
    """
    scores: Dict[Any, float] = {}
    fallback_nodes = 0

    for component in components:
        if len(component) == 1:
            scores[next(iter(component))] = 0.0
            continue

        # Copy rather than use the subgraph view: networkx algorithms run
        # several times slower on views (33s vs 10s on a 10k-node graph)
        subgraph = undirected.subgraph(component).copy()
        try:
            component_scores = nx.eigenvector_centrality(
                subgraph,
                max_iter=EIGENVECTOR_MAX_ITER,
                tol=EIGENVECTOR_TOL,
                weight="weight",
            )
        except (nx.NetworkXException, ArithmeticError) as e:
            logger.warning(
                f"Eigenvector centrality failed for a {len(component)}-node "
                f"component, using weighted degree instead: {e}"
            )
            component_scores = _weighted_degree_scores(subgraph)
            fallback_nodes += len(component)

        scores.update((node, float(value)) for node, value in component_scores.items())

    return scores, fallback_nodes


def _weighted_degree_scores(graph: nx.Graph) -> Dict[Any, float]:
    """Weighted degree scaled to unit L2 norm, matching eigenvector scaling."""
    degrees = dict(graph.degree(weight="weight"))
    norm = math.hypot(*degrees.values()) or 1.0
    return {node: degree / norm for node, degree in degrees.items()}


def _pagerank(directed: nx.DiGraph) -> Optional[Dict[Any, float]]:
    """PageRank for a directed graph, or None if it could not be computed."""
    try:
        scores = nx.pagerank(directed, weight="weight")
    except (ImportError, nx.NetworkXException, ArithmeticError) as e:
        logger.warning(f"PageRank failed, skipping: {e}")
        return None
    return {node: float(value) for node, value in scores.items()}
