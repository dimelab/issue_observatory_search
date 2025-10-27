"""Network exporters for Phase 6.

Export NetworkX graphs to various formats, primarily GEXF for Gephi.
"""
from typing import Dict, Any, Optional
import logging
from pathlib import Path
import networkx as nx
from backend.core.networks.graph_utils import calculate_node_colors, calculate_node_sizes

logger = logging.getLogger(__name__)


def export_to_gexf(
    graph: nx.Graph,
    file_path: str,
    node_type_colors: Optional[Dict[str, str]] = None,
    size_attr: str = "degree",
    min_size: float = 10.0,
    max_size: float = 100.0,
    add_visual_attributes: bool = False,
) -> Dict[str, Any]:
    """
    Export NetworkX graph to GEXF format (Gephi-compatible).

    GEXF (Graph Exchange XML Format) is the standard format for Gephi.
    By default, exports without visual attributes so users can style in Gephi.

    Args:
        graph: NetworkX graph to export
        file_path: Output file path
        node_type_colors: Optional mapping of node types to hex colors
        size_attr: Node attribute to use for sizing ('degree' or attribute name)
        min_size: Minimum node size
        max_size: Maximum node size
        add_visual_attributes: Whether to add pre-computed colors/sizes (default: False)

    Returns:
        Dictionary with export statistics
    """
    logger.info(f"Exporting graph to GEXF: {file_path}")

    # Create a copy to avoid modifying the original
    export_graph = graph.copy()

    # Clean None values from attributes (GEXF doesn't support them)
    _clean_none_values(export_graph)

    # Optionally add visual attributes (disabled by default)
    if add_visual_attributes:
        _add_visual_attributes(
            export_graph,
            node_type_colors=node_type_colors,
            size_attr=size_attr,
            min_size=min_size,
            max_size=max_size,
        )
    else:
        # Ensure all nodes have labels
        for node in export_graph.nodes():
            if "label" not in export_graph.nodes[node]:
                export_graph.nodes[node]["label"] = str(node)

    # Ensure output directory exists
    output_path = Path(file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Export to GEXF
    nx.write_gexf(export_graph, str(output_path))

    # Get file size
    file_size = output_path.stat().st_size

    stats = {
        "file_path": str(output_path),
        "file_size": file_size,
        "node_count": export_graph.number_of_nodes(),
        "edge_count": export_graph.number_of_edges(),
        "format": "gexf",
    }

    logger.info(
        f"Exported GEXF: {export_graph.number_of_nodes()} nodes, "
        f"{export_graph.number_of_edges()} edges, {file_size} bytes"
    )

    return stats


def _clean_none_values(graph: nx.Graph) -> None:
    """
    Remove None values from node and edge attributes.

    GEXF format doesn't support None values, so we need to remove them
    or replace them with empty strings.

    Args:
        graph: NetworkX graph (modified in place)
    """
    # Clean node attributes
    for node in graph.nodes():
        attrs_to_remove = []
        for key, value in graph.nodes[node].items():
            if value is None:
                attrs_to_remove.append(key)

        for key in attrs_to_remove:
            del graph.nodes[node][key]

    # Clean edge attributes
    for u, v in graph.edges():
        attrs_to_remove = []
        for key, value in graph.edges[u, v].items():
            if value is None:
                attrs_to_remove.append(key)

        for key in attrs_to_remove:
            del graph.edges[u, v][key]


def _add_visual_attributes(
    graph: nx.Graph,
    node_type_colors: Optional[Dict[str, str]] = None,
    size_attr: str = "degree",
    min_size: float = 10.0,
    max_size: float = 100.0,
) -> None:
    """
    Add visual attributes to graph for better visualization.

    Args:
        graph: NetworkX graph (modified in place)
        node_type_colors: Optional color mapping
        size_attr: Attribute to use for node sizing
        min_size: Minimum node size
        max_size: Maximum node size
    """
    # Define default color scheme
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

    # Calculate colors based on node type
    colors = calculate_node_colors(graph, default_colors)

    # Calculate sizes
    sizes = calculate_node_sizes(graph, size_attr, min_size, max_size)

    # Add visual attributes to nodes
    for node in graph.nodes():
        # Color (hex format)
        graph.nodes[node]["viz"] = {
            "color": {
                "r": int(colors[node][1:3], 16),
                "g": int(colors[node][3:5], 16),
                "b": int(colors[node][5:7], 16),
            },
            "size": sizes[node],
        }

        # Ensure label is set
        if "label" not in graph.nodes[node]:
            graph.nodes[node]["label"] = str(node)


def export_to_graphml(
    graph: nx.Graph,
    file_path: str,
) -> Dict[str, Any]:
    """
    Export NetworkX graph to GraphML format.

    GraphML is another XML-based format supported by many tools.

    Args:
        graph: NetworkX graph to export
        file_path: Output file path

    Returns:
        Dictionary with export statistics
    """
    logger.info(f"Exporting graph to GraphML: {file_path}")

    # Ensure output directory exists
    output_path = Path(file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Export to GraphML
    nx.write_graphml(graph, str(output_path))

    # Get file size
    file_size = output_path.stat().st_size

    stats = {
        "file_path": str(output_path),
        "file_size": file_size,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "format": "graphml",
    }

    logger.info(
        f"Exported GraphML: {graph.number_of_nodes()} nodes, "
        f"{graph.number_of_edges()} edges, {file_size} bytes"
    )

    return stats


def export_to_edgelist(
    graph: nx.Graph,
    file_path: str,
    data: bool = True,
    delimiter: str = "\t",
) -> Dict[str, Any]:
    """
    Export NetworkX graph to edge list format (TSV/CSV).

    Args:
        graph: NetworkX graph to export
        file_path: Output file path
        data: Whether to include edge attributes
        delimiter: Field delimiter (tab or comma)

    Returns:
        Dictionary with export statistics
    """
    logger.info(f"Exporting graph to edge list: {file_path}")

    # Ensure output directory exists
    output_path = Path(file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Export to edge list
    nx.write_edgelist(graph, str(output_path), data=data, delimiter=delimiter)

    # Get file size
    file_size = output_path.stat().st_size

    stats = {
        "file_path": str(output_path),
        "file_size": file_size,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "format": "edgelist",
    }

    logger.info(
        f"Exported edge list: {graph.number_of_edges()} edges, {file_size} bytes"
    )

    return stats


def export_to_csv(
    graph: nx.Graph,
    file_path: str,
) -> Dict[str, Any]:
    """
    Export NetworkX graph to simple CSV format with Source,Target,Weight columns.

    Args:
        graph: NetworkX graph to export
        file_path: Output file path

    Returns:
        Dictionary with export statistics
    """
    logger.info(f"Exporting graph to CSV: {file_path}")

    # Ensure output directory exists
    output_path = Path(file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write CSV with header
    import csv

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Source', 'Target', 'Weight'])

        for u, v, data in graph.edges(data=True):
            weight = data.get('weight', 1.0)
            writer.writerow([u, v, weight])

    # Get file size
    file_size = output_path.stat().st_size

    stats = {
        "file_path": str(output_path),
        "file_size": file_size,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "format": "csv",
    }

    logger.info(
        f"Exported CSV: {graph.number_of_edges()} edges, {file_size} bytes"
    )

    return stats


def export_to_json(
    graph: nx.Graph,
    file_path: str,
) -> Dict[str, Any]:
    """
    Export NetworkX graph to JSON format (node-link format).

    Args:
        graph: NetworkX graph to export
        file_path: Output file path

    Returns:
        Dictionary with export statistics
    """
    logger.info(f"Exporting graph to JSON: {file_path}")

    # Ensure output directory exists
    output_path = Path(file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to node-link format
    from networkx.readwrite import json_graph
    import json

    data = json_graph.node_link_data(graph)

    # Write to file
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    # Get file size
    file_size = output_path.stat().st_size

    stats = {
        "file_path": str(output_path),
        "file_size": file_size,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "format": "json",
    }

    logger.info(
        f"Exported JSON: {graph.number_of_nodes()} nodes, "
        f"{graph.number_of_edges()} edges, {file_size} bytes"
    )

    return stats


def export_graph(
    graph: nx.Graph,
    file_path: str,
    format: str = "gexf",
    **kwargs,
) -> Dict[str, Any]:
    """
    Export graph to specified format.

    Args:
        graph: NetworkX graph to export
        file_path: Output file path
        format: Export format (gexf, graphml, edgelist, csv, json)
        **kwargs: Format-specific parameters

    Returns:
        Dictionary with export statistics

    Raises:
        ValueError: If format is not supported
    """
    if format == "gexf":
        return export_to_gexf(graph, file_path, **kwargs)
    elif format == "graphml":
        return export_to_graphml(graph, file_path)
    elif format == "edgelist":
        return export_to_edgelist(graph, file_path, **kwargs)
    elif format == "csv":
        return export_to_csv(graph, file_path)
    elif format == "json":
        return export_to_json(graph, file_path)
    else:
        raise ValueError(
            f"Unsupported export format: {format}. "
            f"Supported formats: gexf, graphml, edgelist, csv, json"
        )
