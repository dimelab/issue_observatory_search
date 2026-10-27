"""Unit tests for the edge-list exporters (source/target orientation)."""

import csv
from pathlib import Path
from typing import List, Tuple

import networkx as nx
import pytest

from backend.core.networks.exporters import (
    export_graph,
    export_to_gexf,
    oriented_edges,
)


def _bipartite(second_type: str = "keyword", order: str = "interleaved") -> nx.Graph:
    """
    Websites and a second node type.

    ``order`` is the node insertion order: "interleaved" (what the builders
    produce, and what mixes the columns in a plain NetworkX edge list),
    "others_first" or "websites_first".
    """
    graph = nx.Graph()
    websites = [
        (f"w{i}", {"node_type": "website", "label": f"site{i}.dk"}) for i in (1, 2, 3)
    ]
    others = [
        (f"k{i}", {"node_type": second_type, "label": f"term{i}"}) for i in (1, 2)
    ]
    if order == "others_first":
        nodes = others + websites
    elif order == "websites_first":
        nodes = websites + others
    else:
        nodes = [websites[0], others[0], websites[1], others[1], websites[2]]
    graph.add_nodes_from(nodes)
    graph.add_weighted_edges_from(
        [("w1", "k1", 3), ("k1", "w2", 2), ("w3", "k2", 1), ("k2", "w1", 4)]
    )
    return graph


def _edge_types(graph: nx.Graph) -> List[Tuple[str, str]]:
    """(source type, target type) for every edge as exported."""
    return [
        (graph.nodes[u]["node_type"], graph.nodes[v]["node_type"])
        for u, v, _ in oriented_edges(graph)
    ]


@pytest.mark.parametrize("order", ["interleaved", "others_first", "websites_first"])
@pytest.mark.parametrize("second_type", ["keyword", "entity", "query"])
def test_websites_are_always_source(second_type: str, order: str) -> None:
    """Whatever the insertion order, websites come first and the other type second."""
    graph = _bipartite(second_type, order)
    assert set(_edge_types(graph)) == {("website", second_type)}
    assert len(list(oriented_edges(graph))) == graph.number_of_edges()


def test_plain_networkx_order_is_mixed() -> None:
    """Guards the premise: without orienting, both orders occur."""
    graph = _bipartite()
    plain = {
        (graph.nodes[u]["node_type"], graph.nodes[v]["node_type"])
        for u, v in graph.edges()
    }
    assert len(plain) == 2


def test_edge_attributes_are_kept() -> None:
    """Orienting an edge does not lose or change its weight."""
    weights = {
        frozenset((u, v)): d["weight"] for u, v, d in _bipartite().edges(data=True)
    }
    for u, v, data in oriented_edges(_bipartite()):
        assert weights[frozenset((u, v))] == data["weight"]


def test_projection_keeps_original_order() -> None:
    """Edges between nodes of one type (a projection) are left as they are."""
    graph = nx.Graph()
    graph.add_nodes_from(["b", "a", "c"], node_type="website")
    graph.add_edges_from([("b", "a"), ("c", "b")])
    assert [(u, v) for u, v, _ in oriented_edges(graph)] == list(graph.edges())


def test_untyped_graph_keeps_original_order() -> None:
    """Without node_type attributes there is nothing to orient by."""
    graph = nx.Graph([("b", "a"), ("c", "b")])
    assert [(u, v) for u, v, _ in oriented_edges(graph)] == list(graph.edges())


def test_two_types_without_websites_use_a_stable_side() -> None:
    """Two types and no website: the alphabetically first type is the source."""
    graph = nx.Graph()
    graph.add_node("z1", node_type="query")
    graph.add_node("a1", node_type="entity")
    graph.add_edge("z1", "a1")
    assert [(u, v) for u, v, _ in oriented_edges(graph)] == [("a1", "z1")]


def test_csv_export_uses_website_labels_as_source(tmp_path: Path) -> None:
    """The CSV download has websites under Source and the other type under Target."""
    out = tmp_path / "edges.csv"
    export_graph(_bipartite(), str(out), format="csv")

    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["Source", "Target", "Weight"]
    assert len(rows) == 1 + 4
    assert all(
        src.startswith("site") and tgt.startswith("term") for src, tgt, _ in rows[1:]
    )


def test_edgelist_export_uses_website_ids_as_source(tmp_path: Path) -> None:
    """The edgelist export has websites in column one and the other type in column two."""
    out = tmp_path / "edges.tsv"
    export_graph(_bipartite(), str(out), format="edgelist")

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4
    for line in lines:
        source, target = line.split("\t")[:2]
        assert source.startswith("w") and target.startswith("k")


def test_download_path_gexf_roundtrip(tmp_path: Path) -> None:
    """The download endpoint reloads the stored GEXF; orientation survives that."""
    gexf = tmp_path / "net.gexf"
    export_to_gexf(_bipartite("entity"), str(gexf))
    loaded = nx.read_gexf(str(gexf))

    out = tmp_path / "edges.csv"
    export_graph(loaded, str(out), format="csv")
    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))[1:]
    assert len(rows) == 4
    assert all(
        src.startswith("site") and tgt.startswith("term") for src, tgt, _ in rows
    )
