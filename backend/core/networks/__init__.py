"""Network generation module for Phase 6."""
from backend.core.networks.base import NetworkBuilder
from backend.core.networks.search_website import SearchWebsiteNetworkBuilder
from backend.core.networks.website_noun import WebsiteNounNetworkBuilder
from backend.core.networks.website_concept import WebsiteConceptNetworkBuilder
from backend.core.networks.graph_utils import (
    calculate_graph_metrics,
    get_bipartite_sets,
    validate_bipartite_graph,
    project_bipartite_graph,
    calculate_centrality_measures,
    filter_graph_by_weight,
    get_top_nodes_by_degree,
)
from backend.core.networks.backboning import (
    apply_disparity_filter,
    apply_threshold_filter,
    apply_top_k_filter,
    apply_backboning,
)
from backend.core.networks.exporters import (
    export_to_gexf,
    export_to_graphml,
    export_to_edgelist,
    export_to_json,
    export_graph,
)

__all__ = [
    # Builders
    "NetworkBuilder",
    "SearchWebsiteNetworkBuilder",
    "WebsiteNounNetworkBuilder",
    "WebsiteConceptNetworkBuilder",
    # Graph utilities
    "calculate_graph_metrics",
    "get_bipartite_sets",
    "validate_bipartite_graph",
    "project_bipartite_graph",
    "calculate_centrality_measures",
    "filter_graph_by_weight",
    "get_top_nodes_by_degree",
    # Backboning
    "apply_disparity_filter",
    "apply_threshold_filter",
    "apply_top_k_filter",
    "apply_backboning",
    # Exporters
    "export_to_gexf",
    "export_to_graphml",
    "export_to_edgelist",
    "export_to_json",
    "export_graph",
]
