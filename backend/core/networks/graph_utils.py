"""Graph utilities for NetworkX integration."""
from typing import Dict, Any, List, Set, Tuple, Optional
import logging
import networkx as nx
from collections import defaultdict

logger = logging.getLogger(__name__)


def calculate_graph_metrics(graph: nx.Graph) -> Dict[str, Any]:
    """
    Calculate comprehensive graph metrics.

    Args:
        graph: NetworkX graph

    Returns:
        Dictionary of graph metrics
    """
    if graph.number_of_nodes() == 0:
        return {
            "node_count": 0,
            "edge_count": 0,
            "density": 0.0,
            "avg_degree": 0.0,
        }

    metrics = {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "is_directed": graph.is_directed(),
    }

    # Density
    metrics["density"] = nx.density(graph)

    # Degree statistics
    degrees = [d for n, d in graph.degree()]
    metrics["avg_degree"] = sum(degrees) / len(degrees) if degrees else 0
    metrics["min_degree"] = min(degrees) if degrees else 0
    metrics["max_degree"] = max(degrees) if degrees else 0

    # Node type distribution
    node_types = defaultdict(int)
    for node, data in graph.nodes(data=True):
        node_type = data.get("node_type", "unknown")
        node_types[node_type] += 1
    metrics["node_types"] = dict(node_types)

    # Connected components (undirected only)
    if not graph.is_directed():
        metrics["connected_components"] = nx.number_connected_components(graph)

        # Largest component size
        if nx.number_connected_components(graph) > 0:
            largest_cc = max(nx.connected_components(graph), key=len)
            metrics["largest_component_size"] = len(largest_cc)
            metrics["largest_component_fraction"] = (
                len(largest_cc) / graph.number_of_nodes()
            )

    # Weight statistics
    if graph.number_of_edges() > 0:
        weights = [
            data.get("weight", 1.0)
            for _, _, data in graph.edges(data=True)
        ]
        metrics["avg_weight"] = sum(weights) / len(weights)
        metrics["min_weight"] = min(weights)
        metrics["max_weight"] = max(weights)
        metrics["total_weight"] = sum(weights)

    return metrics


def get_bipartite_sets(
    graph: nx.Graph,
    node_type_attr: str = "node_type",
) -> Tuple[Set[str], Set[str]]:
    """
    Extract the two node sets from a bipartite graph.

    Args:
        graph: NetworkX bipartite graph
        node_type_attr: Name of the node type attribute

    Returns:
        Tuple of (set1, set2) containing node IDs
    """
    node_types = defaultdict(set)

    for node, data in graph.nodes(data=True):
        node_type = data.get(node_type_attr, "unknown")
        node_types[node_type].add(node)

    if len(node_types) != 2:
        raise ValueError(
            f"Expected 2 node types for bipartite graph, found {len(node_types)}: "
            f"{list(node_types.keys())}"
        )

    types = list(node_types.keys())
    return node_types[types[0]], node_types[types[1]]


def validate_bipartite_graph(
    graph: nx.Graph,
    expected_types: Optional[Tuple[str, str]] = None,
) -> bool:
    """
    Validate that a graph is a proper bipartite graph.

    Args:
        graph: NetworkX graph to validate
        expected_types: Optional tuple of expected node types

    Returns:
        True if valid bipartite graph

    Raises:
        ValueError: If graph is not bipartite
    """
    # Get node types
    node_types = set()
    for node, data in graph.nodes(data=True):
        node_type = data.get("node_type")
        if node_type is None:
            raise ValueError(f"Node {node} missing 'node_type' attribute")
        node_types.add(node_type)

    # Check we have exactly 2 types
    if len(node_types) != 2:
        raise ValueError(
            f"Bipartite graph must have exactly 2 node types, found {len(node_types)}"
        )

    # Check expected types if provided
    if expected_types:
        if set(expected_types) != node_types:
            raise ValueError(
                f"Expected node types {expected_types}, found {node_types}"
            )

    # Check that edges only connect different types
    for u, v in graph.edges():
        u_type = graph.nodes[u].get("node_type")
        v_type = graph.nodes[v].get("node_type")

        if u_type == v_type:
            raise ValueError(
                f"Edge ({u}, {v}) connects nodes of same type '{u_type}'"
            )

    logger.debug(f"Graph is valid bipartite with types: {node_types}")
    return True


def project_bipartite_graph(
    graph: nx.Graph,
    nodes: Set[str],
    weighted: bool = True,
) -> nx.Graph:
    """
    Project a bipartite graph onto one set of nodes.

    Args:
        graph: Bipartite graph
        nodes: Set of nodes to project onto
        weighted: Whether to include edge weights

    Returns:
        Projected unipartite graph
    """
    if weighted:
        # Use weighted projection
        projected = nx.bipartite.weighted_projected_graph(graph, nodes)
    else:
        # Simple projection
        projected = nx.bipartite.projected_graph(graph, nodes)

    logger.debug(
        f"Projected graph: {len(nodes)} nodes -> "
        f"{projected.number_of_nodes()} nodes, "
        f"{projected.number_of_edges()} edges"
    )

    return projected


def calculate_centrality_measures(
    graph: nx.Graph,
    measures: Optional[List[str]] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Calculate various centrality measures for nodes.

    Args:
        graph: NetworkX graph
        measures: List of centrality measures to calculate
                  Options: degree, betweenness, closeness, eigenvector

    Returns:
        Dictionary mapping measure names to node centrality values
    """
    if measures is None:
        measures = ["degree"]

    results = {}

    if graph.number_of_nodes() == 0:
        return results

    # Degree centrality (fast, always compute)
    if "degree" in measures:
        results["degree"] = nx.degree_centrality(graph)

    # Betweenness centrality (slower)
    if "betweenness" in measures:
        try:
            results["betweenness"] = nx.betweenness_centrality(graph)
        except Exception as e:
            logger.warning(f"Failed to calculate betweenness centrality: {e}")

    # Closeness centrality (slower)
    if "closeness" in measures:
        try:
            results["closeness"] = nx.closeness_centrality(graph)
        except Exception as e:
            logger.warning(f"Failed to calculate closeness centrality: {e}")

    # Eigenvector centrality (may not converge)
    if "eigenvector" in measures:
        try:
            results["eigenvector"] = nx.eigenvector_centrality(
                graph, max_iter=100, tol=1e-6
            )
        except Exception as e:
            logger.warning(f"Failed to calculate eigenvector centrality: {e}")

    return results


def add_centrality_to_nodes(
    graph: nx.Graph,
    centrality_measure: str = "degree",
    attr_name: Optional[str] = None,
) -> None:
    """
    Calculate centrality and add as node attribute.

    Args:
        graph: NetworkX graph
        centrality_measure: Type of centrality (degree, betweenness, etc.)
        attr_name: Name of attribute to add (defaults to centrality_measure)
    """
    if attr_name is None:
        attr_name = f"{centrality_measure}_centrality"

    centralities = calculate_centrality_measures(graph, [centrality_measure])

    if centrality_measure not in centralities:
        logger.warning(f"Centrality measure '{centrality_measure}' not calculated")
        return

    # Add to node attributes
    nx.set_node_attributes(graph, centralities[centrality_measure], attr_name)

    logger.debug(f"Added {attr_name} to {graph.number_of_nodes()} nodes")


def filter_graph_by_weight(
    graph: nx.Graph,
    min_weight: float,
) -> nx.Graph:
    """
    Filter graph by removing edges below a weight threshold.

    Args:
        graph: NetworkX graph
        min_weight: Minimum edge weight to keep

    Returns:
        Filtered graph
    """
    # Create copy
    filtered = graph.copy()

    # Remove edges below threshold
    edges_to_remove = []
    for u, v, data in filtered.edges(data=True):
        weight = data.get("weight", 1.0)
        if weight < min_weight:
            edges_to_remove.append((u, v))

    filtered.remove_edges_from(edges_to_remove)

    # Remove isolated nodes
    isolated = list(nx.isolates(filtered))
    filtered.remove_nodes_from(isolated)

    logger.info(
        f"Filtered graph: removed {len(edges_to_remove)} edges and "
        f"{len(isolated)} isolated nodes (threshold={min_weight})"
    )

    return filtered


def get_top_nodes_by_degree(
    graph: nx.Graph,
    top_n: int = 10,
    node_type: Optional[str] = None,
) -> List[Tuple[str, int]]:
    """
    Get top N nodes by degree.

    Args:
        graph: NetworkX graph
        top_n: Number of top nodes to return
        node_type: Optional filter by node type

    Returns:
        List of (node_id, degree) tuples
    """
    # Get degrees
    degrees = dict(graph.degree())

    # Filter by node type if specified
    if node_type:
        degrees = {
            node: deg
            for node, deg in degrees.items()
            if graph.nodes[node].get("node_type") == node_type
        }

    # Sort and return top N
    top_nodes = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:top_n]

    return top_nodes


def calculate_node_colors(
    graph: nx.Graph,
    node_type_colors: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Calculate node colors based on node type.

    Args:
        graph: NetworkX graph
        node_type_colors: Optional mapping of node types to colors

    Returns:
        Dictionary mapping node IDs to color codes
    """
    default_colors = {
        "query": "#3498db",  # Blue
        "search": "#3498db",  # Blue
        "website": "#2ecc71",  # Green
        "url": "#2ecc71",  # Green
        "noun": "#e67e22",  # Orange
        "concept": "#9b59b6",  # Purple
        "entity": "#e74c3c",  # Red
    }

    if node_type_colors:
        default_colors.update(node_type_colors)

    colors = {}
    for node, data in graph.nodes(data=True):
        node_type = data.get("node_type", "unknown")
        colors[node] = default_colors.get(node_type, "#95a5a6")  # Gray default

    return colors


def calculate_node_sizes(
    graph: nx.Graph,
    size_attr: str = "degree",
    min_size: float = 10.0,
    max_size: float = 100.0,
) -> Dict[str, float]:
    """
    Calculate node sizes based on an attribute or metric.

    Args:
        graph: NetworkX graph
        size_attr: Attribute to base size on ('degree' or node attribute name)
        min_size: Minimum node size
        max_size: Maximum node size

    Returns:
        Dictionary mapping node IDs to sizes
    """
    if size_attr == "degree":
        # Use degree
        values = dict(graph.degree())
    else:
        # Use node attribute
        values = nx.get_node_attributes(graph, size_attr)

        if not values:
            logger.warning(
                f"Attribute '{size_attr}' not found, using degree instead"
            )
            values = dict(graph.degree())

    if not values:
        # No values, return default size
        return {node: min_size for node in graph.nodes()}

    # Normalize to [min_size, max_size]
    min_val = min(values.values())
    max_val = max(values.values())

    sizes = {}
    if max_val == min_val:
        # All same value
        for node in values:
            sizes[node] = max_size
    else:
        # Scale to range
        for node, val in values.items():
            normalized = (val - min_val) / (max_val - min_val)
            sizes[node] = min_size + normalized * (max_size - min_size)

    return sizes
