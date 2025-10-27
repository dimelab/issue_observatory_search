"""Script to check network generation status."""
import asyncio
from sqlalchemy import select, func
from backend.database import AsyncSessionLocal
from backend.models.network import NetworkExport


async def check_networks():
    async with AsyncSessionLocal() as db:
        print("=" * 60)
        print("NETWORK STATUS CHECK")
        print("=" * 60)

        # Check networks
        networks_result = await db.execute(select(func.count(NetworkExport.id)))
        networks_count = networks_result.scalar()
        print(f'\nTotal Networks: {networks_count}')

        if networks_count > 0:
            # Get all networks
            result = await db.execute(
                select(NetworkExport)
                .order_by(NetworkExport.created_at.desc())
            )
            networks = result.scalars().all()

            print("\n" + "-" * 60)
            print("NETWORK DETAILS:")
            print("-" * 60)
            for network in networks:
                print(f'\nNetwork ID: {network.id}')
                print(f'  Name: {network.name}')
                print(f'  Type: {network.network_type}')
                print(f'  User ID: {network.user_id}')
                print(f'  Status: {getattr(network, "status", "N/A")}')
                print(f'  Nodes: {network.node_count}')
                print(f'  Edges: {network.edge_count}')
                print(f'  File Path: {network.file_path}')
                print(f'  Session IDs: {network.session_ids}')
                print(f'  Created: {network.created_at}')
        else:
            print("\nNo networks found in database")

        print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(check_networks())
