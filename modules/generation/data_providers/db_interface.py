"""
Database connection interface for data providers.

Abstracts database connection to make PostgresDataProvider truly modular.
"""

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import AsyncContextManager, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession


class IDatabaseConnection(ABC):
    """
    Abstract interface for database connections.
    
    This allows PostgresDataProvider to work with any database connection
    implementation without hard dependency on src.database.connection.
    """
    
    @abstractmethod
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get async database session with automatic cleanup.
        
        Yields:
            AsyncSession instance
        
        Example:
            async with connection.get_session() as session:
                result = await session.execute(query)
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if database connection is healthy.
        
        Returns:
            True if connection is working, False otherwise
        """
        pass


class DefaultDatabaseConnection(IDatabaseConnection):
    """
    Default implementation using project's database connection.
    
    This is used when generation module is used within this project.
    For standalone usage, provide a custom implementation.
    """
    
    def __init__(self):
        """Initialize default database connection."""
        # Import here to avoid hard dependency at module level
        try:
            from src.database.connection import get_session as _get_session, check_connection
            self._get_session = _get_session
            self._check_connection = check_connection
        except ImportError:
            raise ImportError(
                "Default database connection requires src.database.connection. "
                "For standalone usage, provide a custom IDatabaseConnection implementation."
            )
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session using project's connection."""
        async with self._get_session() as session:
            yield session
    
    async def health_check(self) -> bool:
        """Check database health using project's connection."""
        return await self._check_connection()


class CustomDatabaseConnection(IDatabaseConnection):
    """
    Custom database connection implementation.
    
    Example for standalone usage with custom connection string.
    """
    
    def __init__(self, connection_string: str, **engine_kwargs):
        """
        Initialize custom database connection.
        
        Args:
            connection_string: SQLAlchemy connection string
            **engine_kwargs: Additional engine configuration
        """
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy import text
        
        self.connection_string = connection_string
        self.engine = create_async_engine(connection_string, **engine_kwargs)
        self.session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session."""
        session = self.session_maker()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    async def health_check(self) -> bool:
        """Check database health."""
        try:
            from sqlalchemy import text
            async with self.get_session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
    
    async def close(self):
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()
