"""Base network builder class for Phase 6."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple, Optional
import logging
import networkx as nx
from datetime import datetime

logger = logging.getLogger(__name__)


class NetworkBuilder(ABC):
    """
    Abstract base class for network builders.

    Provides common functionality for building bipartite and unipartite networks
    following digital methods research principles (Richard Rogers).
    """

    def __init__(self, name: str, network_type: str):
        """
        Initialize the network builder.

        Args:
            name: Name of the network
            network_type: Type identifier (search_website, website_noun, etc.)
        """
        self.name = name
        self.network_type = network_type
        self.graph: Optional[nx.Graph] = None
        self.metadata: Dict[str, Any] = {
            "created_at": datetime.utcnow().isoformat(),
            "builder_version": "1.0.0",
        }
        self._node_id_counter = 0

    @abstractmethod
    async def build(self, **kwargs) -> nx.Graph:
        """
        Build the network graph.

        Returns:
            NetworkX graph object
        """
        pass

    def create_graph(self, directed: bool = False) -> nx.Graph:
        """
        Create a new NetworkX graph.

        Args:
            directed: Whether to create a directed graph

        Returns:
            NetworkX Graph or DiGraph
        """
        if directed:
            self.graph = nx.DiGraph()
        else:
            self.graph = nx.Graph()

        # Add metadata
        self.graph.graph["name"] = self.name
        self.graph.graph["type"] = self.network_type
        self.graph.graph["metadata"] = self.metadata

        logger.debug(
            f"Created {'directed' if directed else 'undirected'} graph: {self.name}"
        )
        return self.graph

    def add_node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        **attributes,
    ) -> None:
        """
        Add a node to the graph with attributes.

        Args:
            node_id: Unique node identifier
            node_type: Type of node (e.g., 'query', 'website', 'noun')
            label: Human-readable label
            **attributes: Additional node attributes
        """
        if self.graph is None:
            raise ValueError("Graph not initialized. Call create_graph() first.")

        self.graph.add_node(
            node_id,
            node_type=node_type,
            label=label,
            **attributes,
        )

    def add_edge(
        self,
        source: str,
        target: str,
        weight: float = 1.0,
        **attributes,
    ) -> None:
        """
        Add an edge to the graph with weight and attributes.

        Args:
            source: Source node ID
            target: Target node ID
            weight: Edge weight (default 1.0)
            **attributes: Additional edge attributes
        """
        if self.graph is None:
            raise ValueError("Graph not initialized. Call create_graph() first.")

        # Check if nodes exist
        if source not in self.graph.nodes:
            raise ValueError(f"Source node '{source}' does not exist in graph")
        if target not in self.graph.nodes:
            raise ValueError(f"Target node '{target}' does not exist in graph")

        self.graph.add_edge(
            source,
            target,
            weight=weight,
            **attributes,
        )

    def normalize_weights(
        self,
        min_weight: float = 0.0,
        max_weight: float = 1.0,
    ) -> None:
        """
        Normalize edge weights to a specified range.

        Args:
            min_weight: Minimum weight value
            max_weight: Maximum weight value
        """
        if self.graph is None or self.graph.number_of_edges() == 0:
            return

        # Get all edge weights
        weights = [data["weight"] for _, _, data in self.graph.edges(data=True)]

        if not weights:
            return

        current_min = min(weights)
        current_max = max(weights)

        # Avoid division by zero
        if current_max == current_min:
            # All weights are the same, set to max_weight
            for u, v in self.graph.edges():
                self.graph[u][v]["weight"] = max_weight
            return

        # Normalize to [min_weight, max_weight]
        for u, v in self.graph.edges():
            old_weight = self.graph[u][v]["weight"]
            normalized = (old_weight - current_min) / (current_max - current_min)
            self.graph[u][v]["weight"] = (
                min_weight + normalized * (max_weight - min_weight)
            )

        logger.debug(
            f"Normalized {len(weights)} edge weights to [{min_weight}, {max_weight}]"
        )

    def add_metadata(self, key: str, value: Any) -> None:
        """
        Add metadata to the network.

        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value

        if self.graph is not None:
            self.graph.graph["metadata"] = self.metadata

    def get_statistics(self) -> Dict[str, Any]:
        """
        Calculate basic graph statistics.

        Returns:
            Dictionary of statistics
        """
        if self.graph is None:
            return {}

        stats = {
            "node_count": self.graph.number_of_nodes(),
            "edge_count": self.graph.number_of_edges(),
            "is_directed": self.graph.is_directed(),
        }

        # Node type distribution
        node_types = {}
        for node, data in self.graph.nodes(data=True):
            node_type = data.get("node_type", "unknown")
            node_types[node_type] = node_types.get(node_type, 0) + 1
        stats["node_types"] = node_types

        # Basic metrics for non-empty graphs
        if self.graph.number_of_nodes() > 0:
            # Density
            if self.graph.is_directed():
                stats["density"] = nx.density(self.graph)
            else:
                stats["density"] = nx.density(self.graph)

            # Average degree
            degrees = [d for n, d in self.graph.degree()]
            stats["avg_degree"] = sum(degrees) / len(degrees) if degrees else 0
            stats["max_degree"] = max(degrees) if degrees else 0

            # Connected components (for undirected graphs)
            if not self.graph.is_directed():
                stats["connected_components"] = nx.number_connected_components(
                    self.graph
                )

        # Weight statistics
        if self.graph.number_of_edges() > 0:
            weights = [data.get("weight", 1.0) for _, _, data in self.graph.edges(data=True)]
            stats["avg_weight"] = sum(weights) / len(weights)
            stats["min_weight"] = min(weights)
            stats["max_weight"] = max(weights)

        return stats

    def validate_bipartite(self, node_types: Tuple[str, str]) -> bool:
        """
        Validate that the graph is a proper bipartite network.

        Args:
            node_types: Tuple of the two node types in the bipartite graph

        Returns:
            True if valid bipartite graph
        """
        if self.graph is None:
            return False

        type1, type2 = node_types

        # Check that all nodes have one of the two types
        for node, data in self.graph.nodes(data=True):
            node_type = data.get("node_type")
            if node_type not in node_types:
                logger.error(
                    f"Node {node} has invalid type '{node_type}' for bipartite graph"
                )
                return False

        # Check that edges only connect different node types
        for u, v in self.graph.edges():
            u_type = self.graph.nodes[u].get("node_type")
            v_type = self.graph.nodes[v].get("node_type")

            if u_type == v_type:
                logger.error(
                    f"Edge ({u}, {v}) connects nodes of same type '{u_type}'"
                )
                return False

        logger.debug(f"Graph is valid bipartite: {type1} <-> {type2}")
        return True

    def _generate_node_id(self, prefix: str = "node") -> str:
        """
        Generate a unique node ID.

        Args:
            prefix: Prefix for the node ID

        Returns:
            Unique node ID
        """
        self._node_id_counter += 1
        return f"{prefix}_{self._node_id_counter}"

    def _sanitize_node_id(self, raw_id: str) -> str:
        """
        Sanitize a raw string to be used as a node ID.

        Args:
            raw_id: Raw identifier string

        Returns:
            Sanitized node ID
        """
        # Replace problematic characters
        sanitized = raw_id.replace(" ", "_")
        sanitized = sanitized.replace("/", "_")
        sanitized = sanitized.replace(":", "_")
        sanitized = sanitized.replace("?", "_")
        sanitized = sanitized.replace("&", "_")
        sanitized = sanitized.replace("=", "_")

        # Limit length
        if len(sanitized) > 200:
            sanitized = sanitized[:200]

        return sanitized
