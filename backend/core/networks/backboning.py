"""Network backboning algorithms for Phase 6.

Implements the disparity filter algorithm from:
Serrano, M. Á., Boguñá, M., & Vespignani, A. (2009).
Extracting the multiscale backbone of complex weighted networks.
Proceedings of the National Academy of Sciences, 106(16), 6483-6488.
"""
from typing import Dict, Any, Optional, List, Tuple
import logging
import networkx as nx
from scipy import stats
import math

logger = logging.getLogger(__name__)


def apply_disparity_filter(
    graph: nx.Graph,
    alpha: float = 0.05,
    min_edge_weight: Optional[float] = None,
) -> Tuple[nx.Graph, Dict[str, Any]]:
    """
    Apply disparity filter for network backboning.

    The disparity filter preserves edges that are statistically significant
    based on the weight distribution of each node's connections.

    From Serrano et al. (2009):
    For each edge (i,j) with weight w_ij, we calculate:
    - k_i: degree of node i
    - p_ij: w_ij / sum(weights of i's edges)
    - α_ij: (1 - p_ij)^(k_i - 1)

    If α_ij < α (significance level), the edge is retained.

    Args:
        graph: NetworkX graph with edge weights
        alpha: Significance level (default 0.05, i.e., 95% confidence)
        min_edge_weight: Optional minimum edge weight (edges below are removed first)

    Returns:
        Tuple of (backboned_graph, statistics)
    """
    logger.info(
        f"Applying disparity filter: alpha={alpha}, min_weight={min_edge_weight}"
    )

    # Create a copy of the graph
    backbone = graph.copy()
    original_edges = backbone.number_of_edges()

    # Step 1: Remove edges below minimum weight if specified
    if min_edge_weight is not None:
        edges_to_remove = []
        for u, v, data in backbone.edges(data=True):
            weight = data.get("weight", 1.0)
            if weight < min_edge_weight:
                edges_to_remove.append((u, v))

        backbone.remove_edges_from(edges_to_remove)
        logger.debug(
            f"Removed {len(edges_to_remove)} edges below min_weight={min_edge_weight}"
        )

    # Step 2: Calculate disparity filter for each edge
    edges_to_remove = []

    for node in backbone.nodes():
        # Get all edges for this node
        if backbone.is_directed():
            # For directed graphs, consider out-edges
            edges = list(backbone.out_edges(node, data=True))
        else:
            # For undirected graphs, consider all edges
            edges = list(backbone.edges(node, data=True))

        if len(edges) == 0:
            continue

        k = len(edges)  # Degree

        # Calculate total weight of all edges
        total_weight = sum(data.get("weight", 1.0) for u, v, data in edges)

        if total_weight == 0:
            # Remove all edges if total weight is 0
            edges_to_remove.extend([(u, v) for u, v, _ in edges])
            continue

        # Calculate significance for each edge
        for u, v, data in edges:
            weight = data.get("weight", 1.0)

            # Normalized weight (fraction of total)
            p_ij = weight / total_weight

            # Calculate alpha_ij using the disparity filter formula
            # α_ij = (1 - p_ij)^(k - 1)
            if k > 1:
                alpha_ij = math.pow(1 - p_ij, k - 1)
            else:
                # If k=1, keep the edge (it's the only one)
                alpha_ij = 0.0

            # Remove edge if not significant
            if alpha_ij >= alpha:
                edges_to_remove.append((u, v))

    # Remove insignificant edges
    backbone.remove_edges_from(edges_to_remove)

    # Remove isolated nodes
    isolated = list(nx.isolates(backbone))
    backbone.remove_nodes_from(isolated)

    # Calculate statistics
    stats_dict = {
        "algorithm": "disparity_filter",
        "alpha": alpha,
        "min_edge_weight": min_edge_weight,
        "original_nodes": graph.number_of_nodes(),
        "original_edges": original_edges,
        "backbone_nodes": backbone.number_of_nodes(),
        "backbone_edges": backbone.number_of_edges(),
        "nodes_removed": graph.number_of_nodes() - backbone.number_of_nodes(),
        "edges_removed": original_edges - backbone.number_of_edges(),
        "edge_retention_rate": (
            backbone.number_of_edges() / original_edges
            if original_edges > 0
            else 0
        ),
    }

    logger.info(
        f"Disparity filter complete: "
        f"{backbone.number_of_edges()}/{original_edges} edges retained "
        f"({stats_dict['edge_retention_rate']:.2%})"
    )

    return backbone, stats_dict


def apply_threshold_filter(
    graph: nx.Graph,
    threshold: float,
    weight_attr: str = "weight",
) -> Tuple[nx.Graph, Dict[str, Any]]:
    """
    Apply simple threshold filter - remove edges below a weight threshold.

    Args:
        graph: NetworkX graph
        threshold: Minimum weight to retain edge
        weight_attr: Edge attribute containing weight

    Returns:
        Tuple of (filtered_graph, statistics)
    """
    logger.info(f"Applying threshold filter: threshold={threshold}")

    # Create copy
    filtered = graph.copy()
    original_edges = filtered.number_of_edges()

    # Remove edges below threshold
    edges_to_remove = []
    for u, v, data in filtered.edges(data=True):
        weight = data.get(weight_attr, 1.0)
        if weight < threshold:
            edges_to_remove.append((u, v))

    filtered.remove_edges_from(edges_to_remove)

    # Remove isolated nodes
    isolated = list(nx.isolates(filtered))
    filtered.remove_nodes_from(isolated)

    # Statistics
    stats_dict = {
        "algorithm": "threshold_filter",
        "threshold": threshold,
        "original_nodes": graph.number_of_nodes(),
        "original_edges": original_edges,
        "filtered_nodes": filtered.number_of_nodes(),
        "filtered_edges": filtered.number_of_edges(),
        "nodes_removed": graph.number_of_nodes() - filtered.number_of_nodes(),
        "edges_removed": original_edges - filtered.number_of_edges(),
        "edge_retention_rate": (
            filtered.number_of_edges() / original_edges
            if original_edges > 0
            else 0
        ),
    }

    logger.info(
        f"Threshold filter complete: "
        f"{filtered.number_of_edges()}/{original_edges} edges retained "
        f"({stats_dict['edge_retention_rate']:.2%})"
    )

    return filtered, stats_dict


def apply_top_k_filter(
    graph: nx.Graph,
    k: int,
    weight_attr: str = "weight",
) -> Tuple[nx.Graph, Dict[str, Any]]:
    """
    Keep only top K edges by weight.

    Args:
        graph: NetworkX graph
        k: Number of edges to keep
        weight_attr: Edge attribute containing weight

    Returns:
        Tuple of (filtered_graph, statistics)
    """
    logger.info(f"Applying top-K filter: k={k}")

    # Get all edges with weights
    edges_with_weights = [
        (u, v, data.get(weight_attr, 1.0))
        for u, v, data in graph.edges(data=True)
    ]

    # Sort by weight (descending)
    edges_with_weights.sort(key=lambda x: x[2], reverse=True)

    # Take top K
    top_k_edges = edges_with_weights[:k]

    # Create new graph with only top K edges
    filtered = nx.Graph() if not graph.is_directed() else nx.DiGraph()

    # Copy graph attributes
    filtered.graph.update(graph.graph)

    # Add nodes (copy attributes)
    for node, data in graph.nodes(data=True):
        filtered.add_node(node, **data)

    # Add top K edges
    for u, v, weight in top_k_edges:
        edge_data = graph[u][v].copy()
        filtered.add_edge(u, v, **edge_data)

    # Remove isolated nodes
    isolated = list(nx.isolates(filtered))
    filtered.remove_nodes_from(isolated)

    # Statistics
    stats_dict = {
        "algorithm": "top_k_filter",
        "k": k,
        "original_nodes": graph.number_of_nodes(),
        "original_edges": graph.number_of_edges(),
        "filtered_nodes": filtered.number_of_nodes(),
        "filtered_edges": filtered.number_of_edges(),
        "nodes_removed": graph.number_of_nodes() - filtered.number_of_nodes(),
        "edges_removed": graph.number_of_edges() - filtered.number_of_edges(),
    }

    logger.info(
        f"Top-K filter complete: kept {filtered.number_of_edges()} edges"
    )

    return filtered, stats_dict


def apply_backboning(
    graph: nx.Graph,
    algorithm: str = "disparity_filter",
    **kwargs,
) -> Tuple[nx.Graph, Dict[str, Any]]:
    """
    Apply network backboning algorithm.

    Args:
        graph: NetworkX graph
        algorithm: Backboning algorithm name
                   Options: disparity_filter, threshold, top_k
        **kwargs: Algorithm-specific parameters

    Returns:
        Tuple of (backboned_graph, statistics)

    Raises:
        ValueError: If algorithm is not supported
    """
    if algorithm == "disparity_filter":
        alpha = kwargs.get("alpha", 0.05)
        min_edge_weight = kwargs.get("min_edge_weight")
        return apply_disparity_filter(graph, alpha, min_edge_weight)

    elif algorithm == "threshold":
        threshold = kwargs.get("threshold")
        if threshold is None:
            raise ValueError("threshold parameter required for threshold filter")
        return apply_threshold_filter(graph, threshold)

    elif algorithm == "top_k":
        k = kwargs.get("k")
        if k is None:
            raise ValueError("k parameter required for top_k filter")
        return apply_top_k_filter(graph, k)

    else:
        raise ValueError(
            f"Unknown backboning algorithm: {algorithm}. "
            f"Supported: disparity_filter, threshold, top_k"
        )


def get_edge_significance_scores(
    graph: nx.Graph,
) -> Dict[Tuple[str, str], float]:
    """
    Calculate disparity filter significance scores for all edges.

    This calculates the α_ij value for each edge without filtering.
    Lower values indicate more significant edges.

    Args:
        graph: NetworkX graph

    Returns:
        Dictionary mapping (u, v) to significance score
    """
    significance_scores = {}

    for node in graph.nodes():
        # Get all edges for this node
        if graph.is_directed():
            edges = list(graph.out_edges(node, data=True))
        else:
            edges = list(graph.edges(node, data=True))

        if len(edges) == 0:
            continue

        k = len(edges)
        total_weight = sum(data.get("weight", 1.0) for u, v, data in edges)

        if total_weight == 0:
            continue

        for u, v, data in edges:
            weight = data.get("weight", 1.0)
            p_ij = weight / total_weight

            if k > 1:
                alpha_ij = math.pow(1 - p_ij, k - 1)
            else:
                alpha_ij = 0.0

            # Store the score
            edge_key = (u, v) if graph.is_directed() else tuple(sorted([u, v]))
            significance_scores[edge_key] = alpha_ij

    return significance_scores
