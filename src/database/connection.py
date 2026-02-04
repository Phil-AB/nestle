"""
Database connection management using SQLAlchemy with async support.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from shared.utils.config import settings
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)

# Base class for all models
Base = declarative_base()

# Global engine and session maker
_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """
    Get or create the async database engine.

    Returns:
        AsyncEngine instance
    """
    global _engine

    if _engine is None:
        # Convert postgresql:// to postgresql+asyncpg://
        db_url = settings.DATABASE_URL
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        logger.info(f"Creating database engine: {db_url.split('@')[1]}")  # Log without credentials

        _engine = create_async_engine(
            db_url,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_pre_ping=settings.DATABASE_POOL_PRE_PING,
            pool_recycle=settings.DATABASE_POOL_RECYCLE,
            echo=settings.DATABASE_ECHO,
            future=True,
        )

    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """
    Get or create the session maker.

    Returns:
        Session maker instance
    """
    global _session_maker

    if _session_maker is None:
        engine = get_engine()
        _session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    return _session_maker


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get async database session with automatic cleanup.

    Yields:
        AsyncSession instance

    Example:
        async with get_session() as session:
            result = await session.execute(query)
    """
    session_maker = get_session_maker()
    session = session_maker()

    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        await session.close()


async def create_tables():
    """
    Create all database tables.
    Used for testing or initial setup.
    In production, use Alembic migrations instead.
    """
    engine = get_engine()

    logger.info("Creating database tables...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created successfully")


async def drop_tables():
    """
    Drop all database tables.
    WARNING: This will delete all data!
    Only use in development/testing.
    """
    if not settings.DEBUG:
        raise RuntimeError("Cannot drop tables in production mode")

    engine = get_engine()

    logger.warning("Dropping all database tables...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    logger.info("Database tables dropped")


async def close_connections():
    """
    Close all database connections.
    Call this on application shutdown.
    """
    global _engine

    if _engine:
        logger.info("Closing database connections...")
        await _engine.dispose()
        _engine = None

    logger.info("Database connections closed")


async def check_connection() -> bool:
    """
    Check if database connection is working.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection check: SUCCESS")
        return True
    except Exception as e:
        logger.error(f"Database connection check: FAILED - {e}")
        return False


def get_database_url() -> str:
    """
    Get the database URL for async connections.

    Returns:
        Database URL with asyncpg driver
    """
    db_url = settings.DATABASE_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return db_url
