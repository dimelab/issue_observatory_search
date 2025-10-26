# Network Backboning - Technical Specification

## Overview

This specification defines the technical implementation for network backboning algorithms to reduce network complexity while preserving structural significance. Backboning filters edges based on statistical significance, removing noise while maintaining the most important relationships in search-website, website-noun, and website-concept networks.

## 1. Algorithm Selection

### Primary Algorithm: Disparity Filter

**Selected**: **Disparity Filter** (Serrano et al., 2009)

**Rationale:**
- **Statistically principled**: Based on null hypothesis testing of edge weight distributions
- **Parameter-free**: Only requires significance level (α), no arbitrary thresholds
- **Validated**: Widely used in digital methods research (Rogers, 2013; Venturini et al., 2021)
- **Preserves structure**: Keeps locally significant edges rather than just strongest globally
- **Fast**: O(E) complexity where E = number of edges
- **Works with weighted networks**: Perfect for TF-IDF weighted bipartite networks
- **Interpretable**: Clear statistical meaning (p-value based filtering)

**Why not alternatives:**
- **H-backbone**: Good but more complex, requires parameter tuning
- **Noise-corrected backbone**: Excellent but computationally expensive for large networks
- **Simpler filtering (top-k, threshold)**: Lacks statistical justification, arbitrary cutoffs
- **Maximum spanning tree**: Too aggressive, removes too many edges

### Algorithm Theory

The disparity filter tests whether an edge weight is significantly different from a random distribution. For each node, it compares the actual edge weights to what would be expected if weights were randomly distributed among that node's neighbors.

**Key concept**: An edge is significant if its weight is unusually high relative to other edges from the same node, not just high in absolute terms.

**Null hypothesis**: Edge weights from a node are uniformly distributed.

**Test statistic**: For edge (i,j) with weight w_ij:
```
α_ij = (1 - w_ij / Σw_i)^(k_i - 1)
```

Where:
- w_ij = weight of edge between i and j
- Σw_i = sum of all edge weights from node i
- k_i = degree of node i (number of neighbors)

**Decision rule**: Keep edge if α_ij < α (significance threshold)

Lower α_ij means the edge is more significant (less likely to occur by chance).

### Secondary Algorithm: Noise-Corrected Backbone (Optional)

For high-value networks where computation time is acceptable:

**Coscia & Neffke (2017) Noise-Corrected Backbone**
- More robust to noise than disparity filter
- Handles both positive and negative deviations
- Better for dense networks
- Slower: O(E × k) where k = degree

Use when:
- Network has >10,000 edges
- High data quality requirements
- Computation time not critical
- User explicitly requests it

## 2. Implementation

### 2.1 Library Selection

**Use existing library: `backbone`**

```bash
pip install backbone-network
```

This library provides:
- Disparity filter implementation (validated)
- Other backboning algorithms
- Well-tested, maintained
- Proper edge case handling

**Alternative**: NetworkX + custom implementation if specific customization needed.

### 2.2 Core Implementation

```python
import networkx as nx
import numpy as np
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class BackboningConfig:
    """Configuration for network backboning"""
    algorithm: str = "disparity_filter"  # or "noise_corrected", "threshold"
    alpha: float = 0.05  # Significance level for disparity filter
    threshold: Optional[float] = None  # For simple threshold filtering
    preserve_disconnected: bool = False  # Keep isolated nodes
    min_edge_weight: Optional[float] = None  # Minimum weight regardless of significance


class NetworkBackboner:
    """
    Apply backboning algorithms to reduce network complexity.

    Supports multiple algorithms with consistent interface.
    """

    def __init__(self, config: Optional[BackboningConfig] = None):
        self.config = config or BackboningConfig()

    def apply_backboning(
        self,
        graph: nx.Graph,
        weight_attribute: str = "weight"
    ) -> Tuple[nx.Graph, Dict[str, Any]]:
        """
        Apply configured backboning algorithm to graph.

        Args:
            graph: Input NetworkX graph (undirected or directed)
            weight_attribute: Name of edge attribute containing weights

        Returns:
            (backboned_graph, statistics)
        """
        if graph.number_of_edges() == 0:
            logger.warning("Empty graph provided, returning as-is")
            return graph.copy(), self._get_empty_stats()

        # Validate graph has weights
        if not self._validate_weights(graph, weight_attribute):
            raise ValueError(
                f"Graph edges must have '{weight_attribute}' attribute"
            )

        # Select algorithm
        if self.config.algorithm == "disparity_filter":
            backboned = self._apply_disparity_filter(graph, weight_attribute)
        elif self.config.algorithm == "noise_corrected":
            backboned = self._apply_noise_corrected(graph, weight_attribute)
        elif self.config.algorithm == "threshold":
            backboned = self._apply_threshold(graph, weight_attribute)
        else:
            raise ValueError(f"Unknown algorithm: {self.config.algorithm}")

        # Apply minimum weight filter if specified
        if self.config.min_edge_weight is not None:
            backboned = self._apply_min_weight_filter(
                backboned,
                weight_attribute,
                self.config.min_edge_weight
            )

        # Handle disconnected nodes
        if not self.config.preserve_disconnected:
            backboned = self._remove_isolates(backboned)

        # Calculate statistics
        stats = self._calculate_statistics(graph, backboned, weight_attribute)

        return backboned, stats

    def _apply_disparity_filter(
        self,
        graph: nx.Graph,
        weight_attr: str
    ) -> nx.Graph:
        """
        Apply disparity filter backboning.

        Implementation based on Serrano et al. (2009).
        """
        import backbone

        # The backbone library expects 'weight' attribute
        if weight_attr != "weight":
            # Create temporary graph with renamed attribute
            temp_graph = graph.copy()
            for u, v, data in temp_graph.edges(data=True):
                data["weight"] = data.get(weight_attr, 1.0)
            graph = temp_graph

        # Apply disparity filter
        try:
            backboned = backbone.disparity_filter(
                graph,
                alpha=self.config.alpha
            )
        except Exception as e:
            logger.error(f"Disparity filter failed: {e}")
            # Fallback to threshold-based filtering
            return self._apply_threshold_fallback(graph, weight_attr)

        return backboned

    def _apply_disparity_filter_custom(
        self,
        graph: nx.Graph,
        weight_attr: str
    ) -> nx.Graph:
        """
        Custom disparity filter implementation.

        Use if backbone library unavailable or customization needed.
        """
        backboned = nx.Graph()
        backboned.add_nodes_from(graph.nodes(data=True))

        # Calculate disparity for each edge
        for node in graph.nodes():
            neighbors = list(graph.neighbors(node))
            if len(neighbors) <= 1:
                # Keep all edges for nodes with 0-1 neighbors
                for neighbor in neighbors:
                    edge_data = graph[node][neighbor]
                    backboned.add_edge(node, neighbor, **edge_data)
                continue

            # Get edge weights
            edges = [(node, neighbor) for neighbor in neighbors]
            weights = np.array([
                graph[node][neighbor].get(weight_attr, 1.0)
                for neighbor in neighbors
            ])

            total_weight = weights.sum()
            if total_weight == 0:
                continue

            k = len(neighbors)  # degree

            # Calculate disparity for each edge
            for i, (u, v) in enumerate(edges):
                w_normalized = weights[i] / total_weight

                # Disparity score (p-value under uniform distribution)
                # α_ij = (1 - w_ij)^(k-1)
                disparity = (1 - w_normalized) ** (k - 1)

                # Keep edge if significant
                if disparity < self.config.alpha:
                    edge_data = graph[u][v]
                    backboned.add_edge(u, v, **edge_data)

        return backboned

    def _apply_noise_corrected(
        self,
        graph: nx.Graph,
        weight_attr: str
    ) -> nx.Graph:
        """
        Apply noise-corrected backbone algorithm.

        Based on Coscia & Neffke (2017).
        """
        try:
            import backbone

            if weight_attr != "weight":
                temp_graph = graph.copy()
                for u, v, data in temp_graph.edges(data=True):
                    data["weight"] = data.get(weight_attr, 1.0)
                graph = temp_graph

            backboned = backbone.noise_corrected(
                graph,
                alpha=self.config.alpha
            )
            return backboned

        except ImportError:
            logger.warning(
                "backbone library not available, "
                "falling back to disparity filter"
            )
            return self._apply_disparity_filter(graph, weight_attr)
        except Exception as e:
            logger.error(f"Noise-corrected backbone failed: {e}")
            return self._apply_threshold_fallback(graph, weight_attr)

    def _apply_threshold(
        self,
        graph: nx.Graph,
        weight_attr: str
    ) -> nx.Graph:
        """
        Simple threshold-based filtering.

        Keep only edges with weight >= threshold.
        """
        threshold = self.config.threshold
        if threshold is None:
            # Auto-calculate threshold (e.g., median weight)
            weights = [
                data.get(weight_attr, 0)
                for _, _, data in graph.edges(data=True)
            ]
            threshold = np.median(weights) if weights else 0

        backboned = nx.Graph()
        backboned.add_nodes_from(graph.nodes(data=True))

        for u, v, data in graph.edges(data=True):
            weight = data.get(weight_attr, 0)
            if weight >= threshold:
                backboned.add_edge(u, v, **data)

        return backboned

    def _apply_threshold_fallback(
        self,
        graph: nx.Graph,
        weight_attr: str
    ) -> nx.Graph:
        """
        Fallback threshold filtering when other algorithms fail.

        Uses 75th percentile as threshold.
        """
        weights = [
            data.get(weight_attr, 0)
            for _, _, data in graph.edges(data=True)
        ]
        threshold = np.percentile(weights, 75) if weights else 0

        logger.warning(
            f"Using fallback threshold filtering (threshold={threshold:.4f})"
        )

        return self._apply_threshold(graph, weight_attr)

    def _apply_min_weight_filter(
        self,
        graph: nx.Graph,
        weight_attr: str,
        min_weight: float
    ) -> nx.Graph:
        """Remove edges below minimum weight threshold"""
        filtered = nx.Graph()
        filtered.add_nodes_from(graph.nodes(data=True))

        for u, v, data in graph.edges(data=True):
            if data.get(weight_attr, 0) >= min_weight:
                filtered.add_edge(u, v, **data)

        return filtered

    def _remove_isolates(self, graph: nx.Graph) -> nx.Graph:
        """Remove nodes with no edges"""
        filtered = graph.copy()
        isolates = list(nx.isolates(filtered))
        filtered.remove_nodes_from(isolates)
        logger.info(f"Removed {len(isolates)} isolated nodes")
        return filtered

    def _validate_weights(
        self,
        graph: nx.Graph,
        weight_attr: str
    ) -> bool:
        """Check if graph edges have weight attribute"""
        if graph.number_of_edges() == 0:
            return True

        sample_edge = next(iter(graph.edges(data=True)))
        return weight_attr in sample_edge[2]

    def _calculate_statistics(
        self,
        original: nx.Graph,
        backboned: nx.Graph,
        weight_attr: str
    ) -> Dict[str, Any]:
        """Calculate backboning statistics"""
        original_edges = original.number_of_edges()
        backboned_edges = backboned.number_of_edges()
        edges_removed = original_edges - backboned_edges
        reduction_percentage = (
            (edges_removed / original_edges * 100)
            if original_edges > 0
            else 0
        )

        original_nodes = original.number_of_nodes()
        backboned_nodes = backboned.number_of_nodes()
        nodes_removed = original_nodes - backboned_nodes

        # Weight statistics
        original_weights = [
            data.get(weight_attr, 0)
            for _, _, data in original.edges(data=True)
        ]
        backboned_weights = [
            data.get(weight_attr, 0)
            for _, _, data in backboned.edges(data=True)
        ]

        stats = {
            "algorithm": self.config.algorithm,
            "alpha": self.config.alpha,
            "original_nodes": original_nodes,
            "backboned_nodes": backboned_nodes,
            "nodes_removed": nodes_removed,
            "original_edges": original_edges,
            "backboned_edges": backboned_edges,
            "edges_removed": edges_removed,
            "reduction_percentage": reduction_percentage,
            "original_weight_sum": sum(original_weights),
            "backboned_weight_sum": sum(backboned_weights),
            "weight_retention_percentage": (
                sum(backboned_weights) / sum(original_weights) * 100
                if sum(original_weights) > 0
                else 0
            ),
            "original_avg_degree": (
                2 * original_edges / original_nodes
                if original_nodes > 0
                else 0
            ),
            "backboned_avg_degree": (
                2 * backboned_edges / backboned_nodes
                if backboned_nodes > 0
                else 0
            ),
        }

        return stats

    def _get_empty_stats(self) -> Dict[str, Any]:
        """Return statistics for empty graph"""
        return {
            "algorithm": self.config.algorithm,
            "alpha": self.config.alpha,
            "original_nodes": 0,
            "backboned_nodes": 0,
            "nodes_removed": 0,
            "original_edges": 0,
            "backboned_edges": 0,
            "edges_removed": 0,
            "reduction_percentage": 0,
            "original_weight_sum": 0,
            "backboned_weight_sum": 0,
            "weight_retention_percentage": 0,
            "original_avg_degree": 0,
            "backboned_avg_degree": 0,
        }
```

### 2.3 Bipartite Network Handling

```python
class BipartiteBackboner(NetworkBackboner):
    """
    Specialized backboning for bipartite networks.

    Handles website-noun and website-concept networks.
    """

    def apply_backboning(
        self,
        graph: nx.Graph,
        weight_attribute: str = "weight",
        node_set_0: Optional[set] = None,
        node_set_1: Optional[set] = None
    ) -> Tuple[nx.Graph, Dict[str, Any]]:
        """
        Apply backboning to bipartite graph.

        Args:
            graph: Bipartite graph
            weight_attribute: Edge weight attribute
            node_set_0: First node set (e.g., websites)
            node_set_1: Second node set (e.g., nouns/concepts)

        Returns:
            (backboned_graph, statistics)
        """
        # Identify bipartite sets if not provided
        if node_set_0 is None or node_set_1 is None:
            node_set_0, node_set_1 = self._identify_bipartite_sets(graph)

        # Verify bipartite structure
        if not self._is_valid_bipartite(graph, node_set_0, node_set_1):
            logger.warning("Graph is not properly bipartite")

        # Apply standard backboning
        backboned, stats = super().apply_backboning(graph, weight_attribute)

        # Add bipartite-specific statistics
        stats.update(
            self._calculate_bipartite_stats(
                backboned, node_set_0, node_set_1
            )
        )

        return backboned, stats

    def _identify_bipartite_sets(
        self,
        graph: nx.Graph
    ) -> Tuple[set, set]:
        """
        Identify the two node sets in a bipartite graph.

        Uses node attributes if available (bipartite=0 or 1).
        """
        node_set_0 = set()
        node_set_1 = set()

        for node, data in graph.nodes(data=True):
            bipartite_attr = data.get("bipartite", None)
            if bipartite_attr == 0:
                node_set_0.add(node)
            elif bipartite_attr == 1:
                node_set_1.add(node)
            else:
                # Fallback: use node_type attribute
                node_type = data.get("node_type", "")
                if node_type in ["website", "search"]:
                    node_set_0.add(node)
                else:
                    node_set_1.add(node)

        # If still empty, try to infer from structure
        if not node_set_0 or not node_set_1:
            node_set_0, node_set_1 = nx.bipartite.sets(graph)

        return node_set_0, node_set_1

    def _is_valid_bipartite(
        self,
        graph: nx.Graph,
        set_0: set,
        set_1: set
    ) -> bool:
        """Verify graph is bipartite with given sets"""
        for u, v in graph.edges():
            if (u in set_0 and v in set_0) or (u in set_1 and v in set_1):
                return False
        return True

    def _calculate_bipartite_stats(
        self,
        graph: nx.Graph,
        set_0: set,
        set_1: set
    ) -> Dict[str, Any]:
        """Calculate bipartite-specific statistics"""
        nodes_0 = [n for n in graph.nodes() if n in set_0]
        nodes_1 = [n for n in graph.nodes() if n in set_1]

        return {
            "bipartite_set_0_count": len(nodes_0),
            "bipartite_set_1_count": len(nodes_1),
            "bipartite_avg_degree_0": (
                sum(graph.degree(n) for n in nodes_0) / len(nodes_0)
                if nodes_0 else 0
            ),
            "bipartite_avg_degree_1": (
                sum(graph.degree(n) for n in nodes_1) / len(nodes_1)
                if nodes_1 else 0
            ),
        }
```

## 3. Parameters

### 3.1 Algorithm Parameters

```python
@dataclass
class BackboningParameters:
    """
    Comprehensive backboning parameters with sensible defaults.
    """

    # Algorithm selection
    algorithm: str = "disparity_filter"
    # Options: "disparity_filter", "noise_corrected", "threshold", "none"

    # Disparity filter parameters
    alpha: float = 0.05
    # Significance level. Lower = more aggressive filtering.
    # Common values: 0.01 (very strict), 0.05 (standard), 0.1 (lenient)

    # Threshold filtering parameters
    threshold: Optional[float] = None
    # Absolute weight threshold. If None, auto-calculated.

    # General filtering
    min_edge_weight: Optional[float] = None
    # Minimum edge weight regardless of statistical significance

    min_node_degree: int = 0
    # Remove nodes with degree below this threshold after backboning

    preserve_disconnected: bool = False
    # Keep isolated nodes (no edges) in result

    # Performance optimization
    max_edges_before_backboning: int = 100000
    # If graph exceeds this, use more aggressive settings

    # Quality control
    target_reduction_percentage: Optional[float] = None
    # Target edge reduction (e.g., 0.5 for 50% reduction)
    # If specified, algorithm will adjust parameters to hit target

    max_iterations_for_target: int = 10
    # Maximum attempts to hit target reduction

    @classmethod
    def for_network_type(
        cls,
        network_type: str,
        node_count: int,
        edge_count: int
    ) -> "BackboningParameters":
        """
        Get recommended parameters for network type.

        Args:
            network_type: "search_website", "website_noun", or "website_concept"
            node_count: Number of nodes in network
            edge_count: Number of edges in network

        Returns:
            Configured parameters
        """
        if network_type == "search_website":
            # Search-website networks are usually sparse
            # Use lenient filtering to preserve connections
            return cls(
                algorithm="disparity_filter",
                alpha=0.1,
                preserve_disconnected=False,
                min_node_degree=1
            )

        elif network_type == "website_noun":
            # Noun networks tend to be dense
            # Use standard filtering
            return cls(
                algorithm="disparity_filter",
                alpha=0.05,
                preserve_disconnected=False,
                min_node_degree=2  # Remove very weakly connected nouns
            )

        elif network_type == "website_concept":
            # Concept networks should be pruned more aggressively
            # These are the "knowledge graphs"
            if edge_count > 50000:
                # Very dense concept network, use noise-corrected
                return cls(
                    algorithm="noise_corrected",
                    alpha=0.01,
                    preserve_disconnected=False,
                    min_node_degree=2,
                    target_reduction_percentage=0.85  # Keep only 15% of edges
                )
            else:
                return cls(
                    algorithm="disparity_filter",
                    alpha=0.03,
                    preserve_disconnected=False,
                    min_node_degree=2,
                    target_reduction_percentage=0.80  # Keep 20% of edges
                )

        else:
            # Default parameters
            return cls()
```

### 3.2 Adaptive Parameter Selection

```python
class AdaptiveBackboner(NetworkBackboner):
    """
    Automatically adjust backboning parameters to achieve target reduction.
    """

    def apply_backboning_with_target(
        self,
        graph: nx.Graph,
        weight_attribute: str = "weight",
        target_reduction: float = 0.8,
        tolerance: float = 0.05,
        max_iterations: int = 10
    ) -> Tuple[nx.Graph, Dict[str, Any]]:
        """
        Apply backboning with target edge reduction percentage.

        Uses binary search to find alpha that achieves target.

        Args:
            graph: Input graph
            weight_attribute: Edge weight attribute
            target_reduction: Target percentage of edges to remove (0.8 = remove 80%)
            tolerance: Acceptable deviation from target
            max_iterations: Maximum optimization iterations

        Returns:
            (backboned_graph, statistics)
        """
        original_edges = graph.number_of_edges()
        target_edges = int(original_edges * (1 - target_reduction))

        # Binary search for optimal alpha
        alpha_low = 0.001
        alpha_high = 0.5
        best_result = None
        best_diff = float("inf")

        for iteration in range(max_iterations):
            alpha = (alpha_low + alpha_high) / 2

            self.config.alpha = alpha
            backboned, stats = super().apply_backboning(graph, weight_attribute)

            current_edges = backboned.number_of_edges()
            diff = abs(current_edges - target_edges)

            logger.info(
                f"Iteration {iteration + 1}: "
                f"alpha={alpha:.4f}, "
                f"edges={current_edges}, "
                f"target={target_edges}"
            )

            # Track best result
            if diff < best_diff:
                best_diff = diff
                best_result = (backboned, stats)

            # Check if within tolerance
            relative_diff = diff / original_edges
            if relative_diff <= tolerance:
                logger.info(f"Target achieved in {iteration + 1} iterations")
                return backboned, stats

            # Adjust search range
            if current_edges > target_edges:
                # Too many edges, need more aggressive filtering
                alpha_high = alpha
            else:
                # Too few edges, need less aggressive filtering
                alpha_low = alpha

        logger.warning(
            f"Target not achieved within {max_iterations} iterations. "
            f"Returning best result."
        )
        return best_result if best_result else (graph.copy(), self._get_empty_stats())
```

## 4. Performance

### 4.1 Complexity Analysis

**Disparity Filter:**
- **Time**: O(E) where E = number of edges
- **Space**: O(N + E) where N = number of nodes
- **Expected runtime**:
  - 1,000 edges: <0.1 seconds
  - 10,000 edges: <1 second
  - 100,000 edges: <10 seconds
  - 1,000,000 edges: <2 minutes

**Noise-Corrected:**
- **Time**: O(E × k) where k = average degree
- **Space**: O(N + E)
- **Expected runtime**: 3-10x slower than disparity filter

### 4.2 Performance Optimizations

```python
class OptimizedBackboner(NetworkBackboner):
    """
    Performance-optimized backboning for large networks.
    """

    def __init__(self, config: Optional[BackboningConfig] = None):
        super().__init__(config)
        self.use_parallel = False
        self.chunk_size = 10000

    def apply_backboning(
        self,
        graph: nx.Graph,
        weight_attribute: str = "weight"
    ) -> Tuple[nx.Graph, Dict[str, Any]]:
        """
        Apply backboning with performance optimizations.

        For very large graphs (>100k edges), uses chunking.
        """
        edge_count = graph.number_of_edges()

        if edge_count > 100000:
            logger.info(f"Large graph ({edge_count} edges), using optimizations")
            return self._apply_chunked(graph, weight_attribute)
        else:
            return super().apply_backboning(graph, weight_attribute)

    def _apply_chunked(
        self,
        graph: nx.Graph,
        weight_attr: str
    ) -> Tuple[nx.Graph, Dict[str, Any]]:
        """
        Process graph in chunks for memory efficiency.

        Splits graph by connected components.
        """
        import time

        start = time.time()

        # Find connected components
        if graph.is_directed():
            components = list(nx.weakly_connected_components(graph))
        else:
            components = list(nx.connected_components(graph))

        logger.info(f"Processing {len(components)} connected components")

        # Process each component separately
        backboned_components = []
        for i, component in enumerate(components):
            subgraph = graph.subgraph(component).copy()

            if subgraph.number_of_edges() > 0:
                component_backboned, _ = super().apply_backboning(
                    subgraph,
                    weight_attr
                )
                backboned_components.append(component_backboned)

            if (i + 1) % 100 == 0:
                logger.info(f"Processed {i + 1}/{len(components)} components")

        # Combine results
        backboned = nx.Graph()
        for component_graph in backboned_components:
            backboned = nx.compose(backboned, component_graph)

        # Calculate statistics
        stats = self._calculate_statistics(graph, backboned, weight_attr)
        stats["processing_time"] = time.time() - start
        stats["components_processed"] = len(components)

        return backboned, stats
```

### 4.3 Benchmarks

Expected performance on typical hardware (4-core CPU, 16GB RAM):

| Network Size | Edges | Disparity Filter | Noise-Corrected | Memory Usage |
|--------------|-------|------------------|-----------------|--------------|
| Small        | 1K    | <0.1s            | <0.5s           | <50MB        |
| Medium       | 10K   | <1s              | <5s             | <200MB       |
| Large        | 100K  | <10s             | <60s            | <1GB         |
| Very Large   | 1M    | <2min            | <20min          | <5GB         |

**Performance target**: Network generation (including backboning) < 30s for 1000 nodes (per .clinerules).

## 5. Configuration

### 5.1 User-Controlled Parameters

Users should be able to control backboning through API:

```python
from pydantic import BaseModel, Field
from typing import Optional

class NetworkBackboningConfig(BaseModel):
    """User-facing backboning configuration"""

    enabled: bool = Field(
        default=True,
        description="Enable backboning (set false to get full network)"
    )

    algorithm: str = Field(
        default="disparity_filter",
        description="Algorithm: disparity_filter, noise_corrected, or threshold"
    )

    alpha: float = Field(
        default=0.05,
        ge=0.001,
        le=0.5,
        description="Significance level (lower = more aggressive filtering)"
    )

    threshold: Optional[float] = Field(
        default=None,
        description="Absolute weight threshold (for threshold algorithm)"
    )

    target_reduction: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=0.99,
        description="Target edge reduction percentage (0.8 = remove 80% of edges)"
    )

    preserve_weak_edges: bool = Field(
        default=False,
        description="Keep edges even if statistically insignificant"
    )

    class Config:
        schema_extra = {
            "example": {
                "enabled": True,
                "algorithm": "disparity_filter",
                "alpha": 0.05,
                "target_reduction": 0.8
            }
        }
```

### 5.2 Preset Configurations

```python
class BackboningPresets:
    """Predefined configurations for common use cases"""

    @staticmethod
    def conservative() -> BackboningConfig:
        """
        Conservative filtering - keeps most edges.

        Use for: Exploratory analysis, small networks
        """
        return BackboningConfig(
            algorithm="disparity_filter",
            alpha=0.1,
            preserve_disconnected=True
        )

    @staticmethod
    def standard() -> BackboningConfig:
        """
        Standard filtering - balanced reduction.

        Use for: Most use cases, medium networks
        """
        return BackboningConfig(
            algorithm="disparity_filter",
            alpha=0.05,
            preserve_disconnected=False
        )

    @staticmethod
    def aggressive() -> BackboningConfig:
        """
        Aggressive filtering - keeps only strongest edges.

        Use for: Dense networks, knowledge graphs
        """
        return BackboningConfig(
            algorithm="disparity_filter",
            alpha=0.01,
            preserve_disconnected=False,
            min_edge_weight=0.1
        )

    @staticmethod
    def for_visualization() -> BackboningConfig:
        """
        Optimized for visualization - very aggressive.

        Use for: Creating clean, readable network visualizations
        """
        return BackboningConfig(
            algorithm="disparity_filter",
            alpha=0.005,
            preserve_disconnected=False,
            min_edge_weight=0.2
        )

    @staticmethod
    def none() -> BackboningConfig:
        """
        No filtering - full network.

        Use for: Analysis requiring all edges, very small networks
        """
        return BackboningConfig(
            algorithm="threshold",
            threshold=0.0,
            preserve_disconnected=True
        )
```

## 6. Edge Weight Handling

### 6.1 Weight Normalization

```python
class EdgeWeightNormalizer:
    """
    Normalize edge weights before backboning.

    Ensures fair comparison across different weight scales.
    """

    @staticmethod
    def normalize_weights(
        graph: nx.Graph,
        weight_attr: str = "weight",
        method: str = "minmax"
    ) -> nx.Graph:
        """
        Normalize edge weights to [0, 1] range.

        Args:
            graph: Input graph
            weight_attr: Weight attribute name
            method: Normalization method
                - "minmax": Scale to [0, 1]
                - "standard": Z-score normalization
                - "log": Logarithmic transformation

        Returns:
            Graph with normalized weights
        """
        normalized = graph.copy()

        # Extract weights
        weights = [
            data.get(weight_attr, 0)
            for _, _, data in normalized.edges(data=True)
        ]

        if not weights:
            return normalized

        if method == "minmax":
            min_weight = min(weights)
            max_weight = max(weights)
            weight_range = max_weight - min_weight

            if weight_range == 0:
                # All weights are the same
                for u, v in normalized.edges():
                    normalized[u][v][weight_attr] = 1.0
            else:
                for u, v, data in normalized.edges(data=True):
                    original = data.get(weight_attr, 0)
                    normalized_weight = (original - min_weight) / weight_range
                    data[weight_attr] = normalized_weight

        elif method == "standard":
            mean_weight = np.mean(weights)
            std_weight = np.std(weights)

            if std_weight == 0:
                for u, v in normalized.edges():
                    normalized[u][v][weight_attr] = 0.0
            else:
                for u, v, data in normalized.edges(data=True):
                    original = data.get(weight_attr, 0)
                    z_score = (original - mean_weight) / std_weight
                    data[weight_attr] = z_score

        elif method == "log":
            for u, v, data in normalized.edges(data=True):
                original = data.get(weight_attr, 0)
                # Add 1 to handle zero weights
                log_weight = np.log1p(original)
                data[weight_attr] = log_weight

        return normalized

    @staticmethod
    def handle_different_weight_types(
        graph: nx.Graph,
        network_type: str
    ) -> nx.Graph:
        """
        Convert different weight types to compatible format.

        Different network types have different weight semantics:
        - search_website: Rank-based (lower is better) → invert
        - website_noun: TF-IDF score (higher is better) → use as-is
        - website_concept: Similarity score (higher is better) → use as-is
        """
        normalized = graph.copy()

        if network_type == "search_website":
            # Invert rank weights (rank 1 is best)
            # Transform: weight = 1 / (rank + 1)
            for u, v, data in normalized.edges(data=True):
                rank = data.get("weight", 1)
                inverted_weight = 1.0 / (rank + 1)
                data["weight"] = inverted_weight

        # For other types, weights are already in correct format
        return normalized
```

### 6.2 Multiple Weight Types

```python
class MultiWeightBackboner:
    """
    Handle graphs with multiple edge weight attributes.

    Example: Edge has both 'tfidf_score' and 'frequency'
    """

    def __init__(self, backboner: NetworkBackboner):
        self.backboner = backboner

    def apply_backboning_multi_weight(
        self,
        graph: nx.Graph,
        weight_attributes: list[str],
        combination_method: str = "product"
    ) -> Tuple[nx.Graph, Dict[str, Any]]:
        """
        Backbone graph using multiple weight attributes.

        Args:
            graph: Input graph
            weight_attributes: List of weight attribute names
            combination_method: How to combine weights
                - "product": Multiply weights
                - "sum": Add weights
                - "average": Average weights
                - "max": Take maximum
                - "min": Take minimum

        Returns:
            (backboned_graph, statistics)
        """
        # Create temporary combined weight
        combined_graph = graph.copy()

        for u, v, data in combined_graph.edges(data=True):
            weights_values = [
                data.get(attr, 0) for attr in weight_attributes
            ]

            if combination_method == "product":
                combined = np.prod(weights_values)
            elif combination_method == "sum":
                combined = np.sum(weights_values)
            elif combination_method == "average":
                combined = np.mean(weights_values)
            elif combination_method == "max":
                combined = np.max(weights_values)
            elif combination_method == "min":
                combined = np.min(weights_values)
            else:
                raise ValueError(f"Unknown combination: {combination_method}")

            data["_combined_weight"] = combined

        # Apply backboning with combined weight
        backboned, stats = self.backboner.apply_backboning(
            combined_graph,
            weight_attribute="_combined_weight"
        )

        # Remove temporary attribute and restore original weights
        for u, v, data in backboned.edges(data=True):
            if "_combined_weight" in data:
                del data["_combined_weight"]

        return backboned, stats
```

## 7. Validation

### 7.1 Backboning Quality Metrics

```python
class BackboningValidator:
    """
    Validate backboning results for quality.
    """

    def validate(
        self,
        original: nx.Graph,
        backboned: nx.Graph,
        weight_attr: str = "weight"
    ) -> Dict[str, Any]:
        """
        Comprehensive validation of backboning results.

        Checks:
        1. Structural integrity
        2. Weight preservation
        3. Community structure preservation
        4. Statistical properties

        Returns:
            Validation report
        """
        report = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "metrics": {}
        }

        # Check structural integrity
        if backboned.number_of_edges() > original.number_of_edges():
            report["valid"] = False
            report["errors"].append("Backboned graph has more edges than original")

        # Check weight preservation (should keep high-weight edges)
        weight_correlation = self._check_weight_preservation(
            original, backboned, weight_attr
        )
        report["metrics"]["weight_correlation"] = weight_correlation

        if weight_correlation < 0.5:
            report["warnings"].append(
                f"Low weight correlation ({weight_correlation:.3f}), "
                "backboning may be too aggressive"
            )

        # Check connectivity preservation
        connectivity = self._check_connectivity(original, backboned)
        report["metrics"]["connectivity"] = connectivity

        if connectivity < 0.3:
            report["warnings"].append(
                f"Low connectivity preservation ({connectivity:.3f}), "
                "network may be fragmented"
            )

        # Check community structure preservation
        if original.number_of_nodes() > 10:  # Only for non-trivial networks
            community_similarity = self._check_community_structure(
                original, backboned
            )
            report["metrics"]["community_similarity"] = community_similarity

            if community_similarity < 0.5:
                report["warnings"].append(
                    f"Low community similarity ({community_similarity:.3f}), "
                    "structure significantly altered"
                )

        return report

    def _check_weight_preservation(
        self,
        original: nx.Graph,
        backboned: nx.Graph,
        weight_attr: str
    ) -> float:
        """
        Check if high-weight edges are preserved.

        Returns correlation between edge weights and preservation.
        """
        # Get weights of all original edges
        original_weights = {}
        for u, v, data in original.edges(data=True):
            edge = tuple(sorted([u, v]))
            original_weights[edge] = data.get(weight_attr, 0)

        # Check which edges are preserved
        preserved = []
        not_preserved = []

        for edge, weight in original_weights.items():
            u, v = edge
            if backboned.has_edge(u, v) or backboned.has_edge(v, u):
                preserved.append(weight)
            else:
                not_preserved.append(weight)

        if not preserved and not not_preserved:
            return 1.0

        # Calculate correlation
        # Higher weights should be more likely to be preserved
        preserved_mean = np.mean(preserved) if preserved else 0
        not_preserved_mean = np.mean(not_preserved) if not_preserved else 0

        if preserved_mean == 0 and not_preserved_mean == 0:
            return 1.0

        # Normalized difference
        correlation = (preserved_mean - not_preserved_mean) / (
            preserved_mean + not_preserved_mean
        )

        return max(0, correlation)  # Clip to [0, 1]

    def _check_connectivity(
        self,
        original: nx.Graph,
        backboned: nx.Graph
    ) -> float:
        """
        Check if connectivity is preserved.

        Returns: Ratio of preserved connected node pairs.
        """
        if original.number_of_nodes() < 2:
            return 1.0

        # Sample node pairs (for efficiency on large graphs)
        nodes = list(original.nodes())
        sample_size = min(1000, len(nodes) * (len(nodes) - 1) // 2)

        import random
        random.seed(42)
        sampled_pairs = random.sample(
            [(u, v) for u in nodes for v in nodes if u < v],
            sample_size
        )

        preserved_count = 0
        for u, v in sampled_pairs:
            original_connected = nx.has_path(original, u, v)
            backboned_connected = (
                backboned.has_node(u) and
                backboned.has_node(v) and
                nx.has_path(backboned, u, v)
            )

            if original_connected and backboned_connected:
                preserved_count += 1

        return preserved_count / sample_size if sample_size > 0 else 0

    def _check_community_structure(
        self,
        original: nx.Graph,
        backboned: nx.Graph
    ) -> float:
        """
        Check if community structure is preserved.

        Uses modularity-based community detection.

        Returns: Normalized mutual information between communities.
        """
        try:
            import networkx.algorithms.community as nx_comm
            from sklearn.metrics import normalized_mutual_info_score

            # Detect communities
            original_communities = list(
                nx_comm.greedy_modularity_communities(original)
            )
            backboned_communities = list(
                nx_comm.greedy_modularity_communities(backboned)
            )

            # Convert to labels for comparison
            common_nodes = set(original.nodes()) & set(backboned.nodes())
            if not common_nodes:
                return 0.0

            original_labels = {}
            for i, community in enumerate(original_communities):
                for node in community:
                    if node in common_nodes:
                        original_labels[node] = i

            backboned_labels = {}
            for i, community in enumerate(backboned_communities):
                for node in community:
                    if node in common_nodes:
                        backboned_labels[node] = i

            # Align labels
            nodes = sorted(common_nodes)
            orig_label_list = [original_labels.get(n, -1) for n in nodes]
            back_label_list = [backboned_labels.get(n, -1) for n in nodes]

            # Calculate NMI
            nmi = normalized_mutual_info_score(orig_label_list, back_label_list)
            return nmi

        except Exception as e:
            logger.warning(f"Community structure check failed: {e}")
            return 0.5  # Unknown
```

### 7.2 Automated Testing

```python
import pytest
import networkx as nx

class TestNetworkBackboner:
    """Unit tests for backboning functionality"""

    def test_disparity_filter_reduces_edges(self):
        """Test that disparity filter removes edges"""
        # Create test graph
        G = nx.Graph()
        G.add_edge("A", "B", weight=10)
        G.add_edge("A", "C", weight=1)
        G.add_edge("A", "D", weight=1)
        G.add_edge("B", "C", weight=5)

        # Apply backboning
        backboner = NetworkBackboner(
            BackboningConfig(algorithm="disparity_filter", alpha=0.05)
        )
        backboned, stats = backboner.apply_backboning(G)

        # Should remove some edges
        assert backboned.number_of_edges() < G.number_of_edges()
        assert stats["reduction_percentage"] > 0

    def test_preserves_high_weight_edges(self):
        """Test that high-weight edges are preserved"""
        G = nx.Graph()
        G.add_edge("A", "B", weight=100)
        G.add_edge("A", "C", weight=1)

        backboner = NetworkBackboner(
            BackboningConfig(algorithm="disparity_filter", alpha=0.05)
        )
        backboned, _ = backboner.apply_backboning(G)

        # High-weight edge should be preserved
        assert backboned.has_edge("A", "B")

    def test_bipartite_structure_maintained(self):
        """Test that bipartite structure is maintained"""
        G = nx.Graph()
        # Websites
        G.add_node("W1", bipartite=0, node_type="website")
        G.add_node("W2", bipartite=0, node_type="website")
        # Nouns
        G.add_node("N1", bipartite=1, node_type="noun")
        G.add_node("N2", bipartite=1, node_type="noun")
        # Edges
        G.add_edge("W1", "N1", weight=10)
        G.add_edge("W1", "N2", weight=5)
        G.add_edge("W2", "N1", weight=8)
        G.add_edge("W2", "N2", weight=2)

        backboner = BipartiteBackboner(
            BackboningConfig(algorithm="disparity_filter", alpha=0.1)
        )
        backboned, _ = backboner.apply_backboning(G)

        # Should still be bipartite
        assert nx.is_bipartite(backboned)

    def test_empty_graph_handling(self):
        """Test handling of empty graph"""
        G = nx.Graph()
        backboner = NetworkBackboner()
        backboned, stats = backboner.apply_backboning(G)

        assert backboned.number_of_nodes() == 0
        assert backboned.number_of_edges() == 0
        assert stats["reduction_percentage"] == 0

    def test_target_reduction(self):
        """Test adaptive backboning with target reduction"""
        # Create graph with 100 edges
        G = nx.gnp_random_graph(20, 0.3, seed=42)
        for u, v in G.edges():
            G[u][v]["weight"] = np.random.rand()

        backboner = AdaptiveBackboner()
        backboned, stats = backboner.apply_backboning_with_target(
            G,
            target_reduction=0.5,  # Remove 50% of edges
            tolerance=0.1
        )

        actual_reduction = stats["reduction_percentage"] / 100
        assert abs(actual_reduction - 0.5) < 0.15  # Within tolerance
```

## 8. API Integration

### 8.1 Configuration in Network Generation

Update the network generation API to include backboning options:

```python
from pydantic import BaseModel, Field
from typing import Optional

class NetworkGenerationRequest(BaseModel):
    """Extended network generation request with backboning"""

    name: str
    type: str  # "search_website", "website_noun", "website_concept"
    session_ids: list[int]

    # Backboning configuration
    backboning: Optional[NetworkBackboningConfig] = Field(
        default=None,
        description="Backboning configuration (uses defaults if not specified)"
    )

    # Network-specific config
    config: dict = {}

    class Config:
        schema_extra = {
            "example": {
                "name": "Climate websites and concepts",
                "type": "website_concept",
                "session_ids": [1, 2],
                "backboning": {
                    "enabled": True,
                    "algorithm": "disparity_filter",
                    "alpha": 0.05,
                    "target_reduction": 0.8
                },
                "config": {
                    "languages": ["da"],
                    "embedding_model": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
                }
            }
        }


# In network generation endpoint
@router.post("/generate", response_model=NetworkGenerationResponse)
async def generate_network(
    request: NetworkGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate network with optional backboning.

    Backboning is applied by default using sensible parameters
    based on network type. Users can disable or customize.
    """
    # ... existing validation ...

    # Queue network generation task
    from app.tasks import generate_network_task

    task = generate_network_task.delay(
        network_type=request.type,
        session_ids=request.session_ids,
        user_id=current_user.id,
        network_name=request.name,
        network_config=request.config,
        backboning_config=request.backboning.dict() if request.backboning else None
    )

    # ... return response ...
```

### 8.2 Backboning Statistics in Response

Include backboning statistics in network metadata:

```python
class NetworkMetadata(BaseModel):
    """Network metadata including backboning info"""

    node_count: int
    edge_count: int
    original_edge_count: Optional[int] = None  # Before backboning
    backboning_applied: bool = False
    backboning_algorithm: Optional[str] = None
    backboning_alpha: Optional[float] = None
    edge_reduction_percentage: Optional[float] = None
    weight_retention_percentage: Optional[float] = None

class NetworkGenerationResult(BaseModel):
    """Result from network generation"""

    network_id: int
    name: str
    type: str
    metadata: NetworkMetadata
    download_url: str
```

## 9. Database Storage

### 9.1 Network Metadata Storage

Store both original and backboned networks metadata:

```sql
-- Add backboning metadata columns to network_exports table
ALTER TABLE network_exports
ADD COLUMN backboning_applied BOOLEAN DEFAULT FALSE,
ADD COLUMN backboning_algorithm VARCHAR(50) NULL,
ADD COLUMN backboning_alpha FLOAT NULL,
ADD COLUMN original_edge_count INTEGER NULL,
ADD COLUMN backboning_statistics JSONB NULL;

-- Index for querying by backboning status
CREATE INDEX idx_network_backboning ON network_exports(backboning_applied);

-- Example of backboning_statistics JSON:
-- {
--   "algorithm": "disparity_filter",
--   "alpha": 0.05,
--   "original_edges": 10000,
--   "backboned_edges": 2000,
--   "reduction_percentage": 80.0,
--   "weight_retention": 65.5,
--   "processing_time": 2.3,
--   "validation": {
--     "weight_correlation": 0.82,
--     "connectivity": 0.75,
--     "community_similarity": 0.68
--   }
-- }
```

### 9.2 Version Control

Option to store both versions:

```sql
-- Network version table (optional)
CREATE TABLE network_versions (
    id SERIAL PRIMARY KEY,
    network_id INTEGER NOT NULL REFERENCES network_exports(id) ON DELETE CASCADE,
    version_type VARCHAR(20) NOT NULL,  -- 'original', 'backboned'
    file_path TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    edge_count INTEGER NOT NULL,
    node_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_network_versions_network ON network_versions(network_id);
CREATE INDEX idx_network_versions_type ON network_versions(version_type);
```

## 10. Testing Strategy

### 10.1 Unit Tests

```python
# tests/test_backboning.py

def test_disparity_filter_correctness():
    """Test disparity filter produces correct results"""
    # Known test case from literature
    # ...

def test_algorithm_consistency():
    """Test same input produces same output"""
    # ...

def test_parameter_validation():
    """Test invalid parameters are rejected"""
    # ...
```

### 10.2 Integration Tests

```python
# tests/integration/test_network_backboning.py

async def test_network_generation_with_backboning(db, test_user):
    """Test full network generation pipeline with backboning"""
    # Create test data
    # Generate network with backboning
    # Verify results
    # ...

async def test_backboning_preserves_bipartite_structure(db):
    """Test bipartite networks remain bipartite after backboning"""
    # ...
```

### 10.3 Performance Tests

```python
# tests/performance/test_backboning_performance.py

def test_large_network_performance():
    """Test backboning performance on large networks"""
    # Generate network with 100k edges
    # Time backboning
    # Assert < 30s
    # ...

def test_memory_usage():
    """Test memory usage stays within limits"""
    # ...
```

### 10.4 Validation Tests

```python
# tests/validation/test_backboning_quality.py

def test_preserves_high_weight_edges():
    """Test that important edges are preserved"""
    # ...

def test_statistical_significance():
    """Test that removed edges are statistically insignificant"""
    # ...

def test_network_structure_preservation():
    """Test that overall structure is preserved"""
    # ...
```

## Summary

This specification provides a complete, production-ready implementation plan for network backboning:

1. **Scientifically rigorous**: Uses disparity filter (Serrano et al., 2009), widely accepted in digital methods
2. **Performant**: O(E) complexity, meets <30s target for 1000-node networks
3. **Flexible**: Supports multiple algorithms, user-configurable parameters
4. **Validated**: Comprehensive quality metrics and testing
5. **Research-ready**: Preserves network structure, interpretable results

**Key Implementation Points:**

- Use `backbone` Python library for validated implementations
- Default to α=0.05 for disparity filter (standard significance level)
- Provide presets for different network types
- Store backboning metadata for reproducibility
- Validate results using weight correlation, connectivity, and community metrics

**Performance Characteristics:**

- Small networks (<10K edges): <1 second
- Medium networks (<100K edges): <10 seconds
- Large networks (>100K edges): <2 minutes
- Expected reduction: 70-90% of edges removed while preserving 60-80% of total weight

**For Different Network Types:**

- **search_website**: α=0.1 (lenient, preserve sparse structure)
- **website_noun**: α=0.05 (standard filtering)
- **website_concept**: α=0.01-0.03 (aggressive, target 80-85% reduction)
