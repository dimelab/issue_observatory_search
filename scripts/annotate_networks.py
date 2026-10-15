#!/usr/bin/env python3
"""Add community and centrality attributes to already-generated networks.

Networks generated before the metrics step have no ``community``,
``component`` or ``eigenvector`` attributes, so the viewer falls back to node
type and degree. This reads each stored GEXF file, annotates it, writes it
back and records the analysis summary in the network's metadata.

Usage:
    python scripts/annotate_networks.py --dry-run     # show what would change
    python scripts/annotate_networks.py               # annotate all networks
    python scripts/annotate_networks.py --id 12 --id 15
    python scripts/annotate_networks.py --force       # redo annotated networks
"""
# Add the project root to sys.path so "backend" resolves when this file is run
# as "python scripts/<name>.py" (sys.path[0] is the script's own directory).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import networkx as nx

from backend.core.networks.exporters import export_to_gexf
from backend.core.networks.metrics import annotate_network


def annotate_gexf_file(
    path: Path,
    expected_nodes: int,
    expected_edges: int,
    dry_run: bool = False,
    force: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Annotate one GEXF file in place.

    The new file is written next to the original and swapped in only once it
    has been written completely, so a failure never leaves a half-written
    network behind.

    Args:
        path: GEXF file to annotate
        expected_nodes: Node count recorded for this network in the database
        expected_edges: Edge count recorded for this network in the database
        dry_run: Compute the analysis but do not write the file
        force: Annotate even if the file already has community attributes

    Returns:
        The analysis summary plus the new ``file_size`` (None on a dry run),
        or None if the file was skipped

    Raises:
        ValueError: If the file does not match the recorded node/edge counts
    """
    graph = nx.read_gexf(str(path))

    if graph.number_of_nodes() != expected_nodes or graph.number_of_edges() != expected_edges:
        raise ValueError(
            f"file has {graph.number_of_nodes()} nodes / {graph.number_of_edges()} "
            f"edges but the database records {expected_nodes} / {expected_edges}"
        )

    already_annotated = any("community" in data for _, data in graph.nodes(data=True))
    if already_annotated and not force:
        return None

    summary = annotate_network(graph)
    summary["file_size"] = None

    if dry_run:
        return summary

    temp_path = path.with_name(path.name + ".tmp")
    try:
        export_stats = export_to_gexf(graph, str(temp_path))
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    summary["file_size"] = export_stats["file_size"]
    return summary


async def annotate_all(ids: List[int], dry_run: bool, force: bool) -> None:
    """Annotate the selected networks (all of them if no ids are given)."""
    from sqlalchemy import select

    from backend.database import AsyncSessionLocal
    from backend.models.network import NetworkExport

    done = skipped = failed = 0

    async with AsyncSessionLocal() as db:
        stmt = select(NetworkExport).order_by(NetworkExport.id)
        if ids:
            stmt = stmt.where(NetworkExport.id.in_(ids))
        networks = (await db.execute(stmt)).scalars().all()

        print(f"{len(networks)} network(s) selected{' (dry run)' if dry_run else ''}")

        for network in networks:
            label = f"#{network.id} {network.name!r}"
            path = Path(network.file_path)

            if not path.exists():
                print(f"  {label}: file missing, skipped")
                skipped += 1
                continue

            try:
                summary = annotate_gexf_file(
                    path,
                    network.node_count,
                    network.edge_count,
                    dry_run=dry_run,
                    force=force,
                )
            except Exception as e:
                print(f"  {label}: FAILED ({type(e).__name__}: {e})")
                failed += 1
                continue

            if summary is None:
                print(f"  {label}: already annotated, skipped (use --force)")
                skipped += 1
                continue

            print(
                f"  {label}: {summary['community_count']} communities, "
                f"{summary['component_count']} components, "
                f"size by {summary['size_metric']}"
            )
            done += 1

            if not dry_run:
                analysis = {k: v for k, v in summary.items() if k != "file_size"}
                # Assign a new dict so SQLAlchemy sees the JSON column change
                network.network_metadata = {
                    **(network.network_metadata or {}),
                    "analysis": analysis,
                }
                network.file_size = summary["file_size"]
                network.updated_at = datetime.utcnow()
                await db.commit()

    print(f"Done: {done} annotated, {skipped} skipped, {failed} failed")


def main() -> None:
    """Parse arguments and run."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--id", type=int, action="append", default=[], dest="ids",
        help="network id to annotate (repeatable); default is all networks",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="compute and report the analysis without writing anything",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="re-annotate networks that already have community attributes",
    )
    args = parser.parse_args()

    asyncio.run(annotate_all(args.ids, args.dry_run, args.force))


if __name__ == "__main__":
    main()
