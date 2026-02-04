"""
Base repository pattern for database operations.
"""

from typing import Generic, TypeVar, Type, Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from shared.utils.logger import setup_logger

logger = setup_logger(__name__)

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """
    Base repository providing CRUD operations.

    This pattern ensures all database operations are consistent
    and can be easily mocked for testing.
    """

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        """
        Initialize repository.

        Args:
            model: SQLAlchemy model class
            session: Async database session
        """
        self.model = model
        self.session = session

    async def create(self, **kwargs) -> ModelType:
        """
        Create a new record.

        Args:
            **kwargs: Model fields

        Returns:
            Created model instance
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        logger.debug(f"Created {self.model.__name__}: {instance.id}")
        return instance

    async def get_by_id(self, id: str) -> Optional[ModelType]:
        """
        Get record by ID.

        Args:
            id: Record ID

        Returns:
            Model instance or None
        """
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, limit: Optional[int] = None) -> List[ModelType]:
        """
        Get all records.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of model instances
        """
        query = select(self.model)
        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(self, id: str, **kwargs) -> Optional[ModelType]:
        """
        Update a record.

        Args:
            id: Record ID
            **kwargs: Fields to update

        Returns:
            Updated model instance or None
        """
        stmt = (
            update(self.model)
            .where(self.model.id == id)
            .values(**kwargs)
            .returning(self.model)
        )

        result = await self.session.execute(stmt)
        await self.session.flush()

        updated = result.scalar_one_or_none()
        if updated:
            logger.debug(f"Updated {self.model.__name__}: {id}")

        return updated

    async def delete(self, id: str) -> bool:
        """
        Delete a record.

        Args:
            id: Record ID

        Returns:
            True if deleted, False if not found
        """
        stmt = delete(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        await self.session.flush()

        deleted = result.rowcount > 0
        if deleted:
            logger.debug(f"Deleted {self.model.__name__}: {id}")

        return deleted

    async def exists(self, id: str) -> bool:
        """
        Check if record exists.

        Args:
            id: Record ID

        Returns:
            True if exists, False otherwise
        """
        result = await self.session.execute(
            select(self.model.id).where(self.model.id == id)
        )
        return result.scalar_one_or_none() is not None

    async def count(self) -> int:
        """
        Count total records.

        Returns:
            Total count
        """
        from sqlalchemy import func

        result = await self.session.execute(
            select(func.count()).select_from(self.model)
        )
        return result.scalar_one()
