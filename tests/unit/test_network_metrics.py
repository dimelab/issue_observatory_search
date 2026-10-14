"""Unit tests for network node metrics (communities and centrality)."""
import io
import math
from typing import Dict, List

import networkx as nx
import pytest

from backend.core.networks.metrics import annotate_network


@pytest.fixture
def fragmented_bipartite() -> nx.Graph:
    """Websites and keywords: one 5-node component, two 2-node ones, one isolate."""
    graph = nx.Graph()
    for node in ["w1", "w2", "w3", "w4", "w5", "lonely"]:
        graph.add_node(node, node_type="website")
    for node in ["k1", "k2", "k3", "k8"]:
        graph.add_node(node, node_type="keyword")
    graph.add_weighted_edges_from(
        [
            ("w1", "k1", 3),
            ("w2", "k1", 2),
            ("w3", "k1", 1),
            ("w2", "k2", 1),
            ("w3", "k2", 1),
            ("w4", "k3", 1),
            ("w5", "k8", 1),
        ]
    )
    return graph


def _attr(graph: nx.Graph, name: str) -> Dict[str, object]:
    """Collect one node attribute for every node."""
    return {node: data[name] for node, data in graph.nodes(data=True)}


def test_adds_attributes_to_every_node(fragmented_bipartite: nx.Graph) -> None:
    """Every node gets a community, a component and an eigenvector score."""
    summary = annotate_network(fragmented_bipartite)

    for _, data in fragmented_bipartite.nodes(data=True):
        assert isinstance(data["community"], int)
        assert isinstance(data["component"], int)
        assert isinstance(data["eigenvector"], float)
        assert "pagerank" not in data

    assert summary["size_metric"] == "eigenvector"
    assert summary["component_count"] == 4
    assert summary["community_count"] >= summary["component_count"]
    assert 0.0 < summary["modularity"] < 1.0


def test_groups_are_numbered_largest_first(fragmented_bipartite: nx.Graph) -> None:
    """Community and component ids are contiguous and ordered by size."""
    annotate_network(fragmented_bipartite)

    for name in ("community", "component"):
        ids = list(_attr(fragmented_bipartite, name).values())
        sizes: List[int] = [ids.count(i) for i in range(max(ids) + 1)]
        assert all(size > 0 for size in sizes)
        assert sizes == sorted(sizes, reverse=True)


def test_hub_has_highest_eigenvector_in_its_component(
    fragmented_bipartite: nx.Graph,
) -> None:
    """The keyword linked to the most websites is the most central node."""
    annotate_network(fragmented_bipartite)

    giant = [
        node
        for node, data in fragmented_bipartite.nodes(data=True)
        if data["component"] == 0
    ]
    scores = _attr(fragmented_bipartite, "eigenvector")
    assert max(giant, key=lambda node: scores[node]) == "k1"


def test_isolated_node_scores_zero(fragmented_bipartite: nx.Graph) -> None:
    """networkx would give a lone node 1.0; it should not outrank real hubs."""
    annotate_network(fragmented_bipartite)

    assert fragmented_bipartite.nodes["lonely"]["eigenvector"] == 0.0


def test_same_seed_gives_same_result(fragmented_bipartite: nx.Graph) -> None:
    """Repeated runs on the same graph produce identical communities."""
    first = fragmented_bipartite.copy()
    second = fragmented_bipartite.copy()

    annotate_network(first, seed=7)
    annotate_network(second, seed=7)

    assert _attr(first, "community") == _attr(second, "community")
    assert _attr(first, "eigenvector") == _attr(second, "eigenvector")


def test_edge_weights_drive_communities() -> None:
    """Two heavy triangles joined by a weak bridge split into two communities."""
    graph = nx.Graph()
    graph.add_weighted_edges_from(
        [
            ("a", "b", 5),
            ("b", "c", 5),
            ("a", "c", 5),
            ("x", "y", 5),
            ("y", "z", 5),
            ("x", "z", 5),
            ("c", "x", 0.1),
        ]
    )

    summary = annotate_network(graph)

    communities = _attr(graph, "community")
    assert summary["community_count"] == 2
    assert communities["a"] == communities["b"] == communities["c"]
    assert communities["x"] == communities["y"] == communities["z"]
    assert communities["a"] != communities["x"]


def test_does_not_change_structure_or_weights(fragmented_bipartite: nx.Graph) -> None:
    """Only node attributes are added; edges and their weights are untouched."""
    before = sorted(fragmented_bipartite.edges(data=True))

    annotate_network(fragmented_bipartite)

    assert sorted(fragmented_bipartite.edges(data=True)) == before


def test_empty_graph() -> None:
    """An empty graph returns a zeroed summary without error."""
    summary = annotate_network(nx.Graph())

    assert summary["size_metric"] is None
    assert summary["community_count"] == 0
    assert summary["component_count"] == 0


def test_graph_without_edges() -> None:
    """Louvain is undefined without edges; each node becomes its own community."""
    graph = nx.Graph()
    graph.add_nodes_from(["a", "b", "c"])

    summary = annotate_network(graph)

    assert summary["community_count"] == 3
    assert summary["modularity"] is None
    assert set(_attr(graph, "eigenvector").values()) == {0.0}


def test_bad_weights_do_not_break_metrics() -> None:
    """NaN and text weights count as 1.0; zero or negative edges are ignored."""
    graph = nx.Graph()
    graph.add_edge("a", "b", weight=float("nan"))
    graph.add_edge("b", "c", weight=-1)
    graph.add_edge("c", "d", weight="heavy")
    graph.add_edge("d", "e")

    summary = annotate_network(graph)

    # The negative edge is ignored for metrics, which splits {a, b} from {c, d, e}
    assert summary["component_count"] == 2
    assert all(math.isfinite(v) for v in _attr(graph, "eigenvector").values())
    # ...but the edge itself is still in the graph
    assert graph.has_edge("b", "c")


def test_falls_back_to_weighted_degree_when_power_iteration_fails(
    fragmented_bipartite: nx.Graph,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-converging component gets normalised weighted degree instead."""

    def fail(*args: object, **kwargs: object) -> None:
        raise nx.PowerIterationFailedConvergence(1000)

    monkeypatch.setattr(nx, "eigenvector_centrality", fail)

    summary = annotate_network(fragmented_bipartite)

    # Components of size >= 2 (5 + 2 + 2 nodes) fall back; the isolate does not
    assert summary["centrality_fallback_nodes"] == 9
    scores = _attr(fragmented_bipartite, "eigenvector")
    assert scores["k1"] > scores["k2"]
    assert scores["lonely"] == 0.0


def test_directed_graph_gets_pagerank_not_eigenvector() -> None:
    """Directed networks are sized by PageRank, which sums to 1."""
    pytest.importorskip("scipy")
    graph = nx.DiGraph()
    graph.add_weighted_edges_from(
        [("a", "b", 1), ("b", "c", 1), ("c", "a", 2), ("c", "d", 1)]
    )

    summary = annotate_network(graph)

    assert summary["size_metric"] == "pagerank"
    for _, data in graph.nodes(data=True):
        assert "eigenvector" not in data
        assert isinstance(data["community"], int)
    assert math.isclose(sum(_attr(graph, "pagerank").values()), 1.0)


def test_attributes_survive_gexf_round_trip(fragmented_bipartite: nx.Graph) -> None:
    """The exported GEXF declares the new attributes with usable types."""
    annotate_network(fragmented_bipartite)

    buffer = io.BytesIO()
    nx.write_gexf(fragmented_bipartite, buffer)
    buffer.seek(0)
    restored = nx.read_gexf(buffer)

    data = restored.nodes["k1"]
    assert isinstance(data["community"], int)
    assert isinstance(data["component"], int)
    assert isinstance(data["eigenvector"], float)
    assert data["eigenvector"] == pytest.approx(
        fragmented_bipartite.nodes["k1"]["eigenvector"]
    )
