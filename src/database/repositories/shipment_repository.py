"""
Shipment repository for database operations.
"""

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.database.schema import Shipment
from .base import BaseRepository


class ShipmentRepository(BaseRepository[Shipment]):
    """Repository for Shipment operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Shipment, session)

    async def get_by_number(self, shipment_number: str) -> Optional[Shipment]:
        """
        Get shipment by shipment number.

        Args:
            shipment_number: Shipment number

        Returns:
            Shipment instance or None
        """
        result = await self.session.execute(
            select(Shipment).where(Shipment.shipment_number == shipment_number)
        )
        return result.scalar_one_or_none()

    async def get_with_documents(self, shipment_id: str) -> Optional[Shipment]:
        """
        Get shipment with all related documents loaded.

        Args:
            shipment_id: Shipment ID

        Returns:
            Shipment with documents or None
        """
        result = await self.session.execute(
            select(Shipment)
            .where(Shipment.id == shipment_id)
            .options(
                selectinload(Shipment.invoices),
                selectinload(Shipment.bill_of_entries),
                selectinload(Shipment.packing_lists),
                selectinload(Shipment.certificates_of_origin),
                selectinload(Shipment.freight_documents),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_status(self, status: str, limit: int = 100) -> List[Shipment]:
        """
        Get shipments by status.

        Args:
            status: Status (pending, validated, errors)
            limit: Maximum results

        Returns:
            List of shipments
        """
        result = await self.session.execute(
            select(Shipment)
            .where(Shipment.status == status)
            .limit(limit)
            .order_by(Shipment.created_at.desc())
        )
        return list(result.scalars().all())
