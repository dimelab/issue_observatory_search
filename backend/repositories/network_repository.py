"""Repository for network database operations."""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, delete, func, desc, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.network import NetworkExport

logger = logging.getLogger(__name__)


class NetworkRepository:
    """
    Repository for network database operations.

    Handles all database interactions for network exports.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def create_export(
        self,
        user_id: int,
        name: str,
        network_type: str,
        session_ids: List[int],
        file_path: str,
        file_size: int,
        node_count: int,
        edge_count: int,
        network_metadata: Dict[str, Any],
        backboning_applied: bool = False,
        backboning_algorithm: Optional[str] = None,
        backboning_alpha: Optional[float] = None,
        original_edge_count: Optional[int] = None,
        backboning_statistics: Optional[Dict[str, Any]] = None,
    ) -> NetworkExport:
        """
        Create a new network export record.

        Args:
            user_id: User ID
            name: Network name
            network_type: Network type (search_website, website_noun, etc.)
            session_ids: List of session IDs used
            file_path: Path to exported file
            file_size: File size in bytes
            node_count: Number of nodes
            edge_count: Number of edges
            network_metadata: Network metadata
            backboning_applied: Whether backboning was applied
            backboning_algorithm: Backboning algorithm used
            backboning_alpha: Alpha parameter for backboning
            original_edge_count: Edge count before backboning
            backboning_statistics: Backboning statistics

        Returns:
            Created NetworkExport object
        """
        network = NetworkExport(
            user_id=user_id,
            name=name,
            type=network_type,
            session_ids=session_ids,
            file_path=file_path,
            file_size=file_size,
            node_count=node_count,
            edge_count=edge_count,
            network_metadata=network_metadata,
            backboning_applied=backboning_applied,
            backboning_algorithm=backboning_algorithm,
            backboning_alpha=backboning_alpha,
            original_edge_count=original_edge_count,
            backboning_statistics=backboning_statistics,
        )

        self.session.add(network)
        await self.session.flush()
        await self.session.refresh(network)

        logger.info(
            f"Created network export: id={network.id}, "
            f"type={network_type}, nodes={node_count}, edges={edge_count}"
        )

        return network

    async def get_by_id(self, network_id: int) -> Optional[NetworkExport]:
        """
        Get network export by ID.

        Args:
            network_id: Network export ID

        Returns:
            NetworkExport object or None
        """
        stmt = select(NetworkExport).where(NetworkExport.id == network_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user(
        self,
        user_id: int,
        page: int = 1,
        per_page: int = 20,
        network_type: Optional[str] = None,
        session_id: Optional[int] = None,
    ) -> tuple[List[NetworkExport], int]:
        """
        Get networks for a user with pagination.

        Args:
            user_id: User ID
            page: Page number (1-based)
            per_page: Results per page
            network_type: Optional filter by network type
            session_id: Optional filter by session ID

        Returns:
            Tuple of (networks list, total count)
        """
        # Base query
        stmt = select(NetworkExport).where(NetworkExport.user_id == user_id)

        # Apply filters
        if network_type:
            stmt = stmt.where(NetworkExport.type == network_type)

        if session_id:
            # PostgreSQL array contains
            stmt = stmt.where(NetworkExport.session_ids.contains([session_id]))

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Apply ordering and pagination
        stmt = (
            stmt
            .order_by(desc(NetworkExport.created_at))
            .offset((page - 1) * per_page)
            .limit(per_page)
        )

        result = await self.session.execute(stmt)
        networks = list(result.scalars().all())

        logger.debug(
            f"Retrieved {len(networks)} networks for user {user_id} "
            f"(page {page}, total {total})"
        )

        return networks, total

    async def get_by_session(
        self,
        session_id: int,
        user_id: Optional[int] = None,
    ) -> List[NetworkExport]:
        """
        Get all networks that include a specific session.

        Args:
            session_id: Session ID
            user_id: Optional filter by user ID

        Returns:
            List of NetworkExport objects
        """
        stmt = select(NetworkExport).where(
            NetworkExport.session_ids.contains([session_id])
        )

        if user_id:
            stmt = stmt.where(NetworkExport.user_id == user_id)

        stmt = stmt.order_by(desc(NetworkExport.created_at))

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_export(self, network_id: int) -> bool:
        """
        Delete a network export.

        Args:
            network_id: Network export ID

        Returns:
            True if deleted, False if not found
        """
        stmt = delete(NetworkExport).where(NetworkExport.id == network_id)
        result = await self.session.execute(stmt)
        await self.session.flush()

        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Deleted network export: id={network_id}")

        return deleted

    async def update_statistics(
        self,
        network_id: int,
        node_count: int,
        edge_count: int,
        file_size: int,
    ) -> Optional[NetworkExport]:
        """
        Update network statistics.

        Args:
            network_id: Network export ID
            node_count: Updated node count
            edge_count: Updated edge count
            file_size: Updated file size

        Returns:
            Updated NetworkExport object or None
        """
        stmt = select(NetworkExport).where(NetworkExport.id == network_id)
        result = await self.session.execute(stmt)
        network = result.scalar_one_or_none()

        if not network:
            return None

        network.node_count = node_count
        network.edge_count = edge_count
        network.file_size = file_size
        network.updated_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(network)

        logger.debug(f"Updated network statistics: id={network_id}")

        return network

    async def get_old_exports(
        self,
        days: int = 30,
    ) -> List[NetworkExport]:
        """
        Get network exports older than specified days.

        Args:
            days: Number of days

        Returns:
            List of old NetworkExport objects
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        stmt = (
            select(NetworkExport)
            .where(NetworkExport.created_at < cutoff_date)
            .order_by(NetworkExport.created_at)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_user_network_count(self, user_id: int) -> int:
        """
        Get count of networks for a user.

        Args:
            user_id: User ID

        Returns:
            Network count
        """
        stmt = (
            select(func.count())
            .select_from(NetworkExport)
            .where(NetworkExport.user_id == user_id)
        )

        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_network_types_count(
        self,
        user_id: Optional[int] = None,
    ) -> Dict[str, int]:
        """
        Get count of networks by type.

        Args:
            user_id: Optional filter by user ID

        Returns:
            Dictionary mapping network type to count
        """
        stmt = (
            select(
                NetworkExport.type,
                func.count(NetworkExport.id).label("count"),
            )
            .group_by(NetworkExport.type)
        )

        if user_id:
            stmt = stmt.where(NetworkExport.user_id == user_id)

        result = await self.session.execute(stmt)
        rows = result.all()

        return {row.type: row.count for row in rows}

    async def get_total_file_size(
        self,
        user_id: Optional[int] = None,
    ) -> int:
        """
        Get total file size of all network exports.

        Args:
            user_id: Optional filter by user ID

        Returns:
            Total file size in bytes
        """
        stmt = select(func.sum(NetworkExport.file_size))

        if user_id:
            stmt = stmt.where(NetworkExport.user_id == user_id)

        result = await self.session.execute(stmt)
        return result.scalar() or 0
