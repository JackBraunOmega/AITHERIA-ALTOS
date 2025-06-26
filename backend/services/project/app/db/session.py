"""
AITHERIA ALTOS - Project Service Database Session
===============================================

This module provides database session management utilities for the Project service.
It configures the SQLAlchemy async engine and provides session factories and
dependency functions for FastAPI routes.

Usage:
    from app.db.session import get_db
    
    @app.get("/projects")
    async def get_projects(db: AsyncSession = Depends(get_db)):
        # Use db session here
        ...
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Create async engine
engine = create_async_engine(
    str(settings.DATABASE_URL),  # ensure plain string for SQLAlchemy
    echo=settings.DATABASE_ECHO,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_pre_ping=True,  # Check connection before using from pool
    pool_recycle=3600,   # Recycle connections after 1 hour
)

# Create session factory
async_session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.
    
    Yields:
        AsyncSession: SQLAlchemy async session
        
    Example:
        async with get_session() as session:
            result = await session.execute(...)
    """
    session = async_session_maker()
    try:
        yield session
        await session.commit()
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Unexpected error in database session: {e}")
        raise
    finally:
        await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for getting a database session.
    
    This function should be used as a dependency in FastAPI route functions
    to get a database session that will be automatically closed after the request.
    
    Yields:
        AsyncSession: SQLAlchemy async session
        
    Example:
        @app.get("/projects")
        async def get_projects(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Project))
            return result.scalars().all()
    """
    session = async_session_maker()
    try:
        yield session
        await session.commit()
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Unexpected error in database session: {e}")
        raise
    finally:
        await session.close()


async def close_db_connections() -> None:
    """
    Close all database connections.
    
    This function should be called when the application is shutting down.
    """
    global engine
    
    if engine is not None:
        logger.info("Closing database connections...")
        await engine.dispose()
        logger.info("Database connections closed")


def get_engine() -> AsyncEngine:
    """
    Get the SQLAlchemy async engine instance.
    
    Returns:
        AsyncEngine: SQLAlchemy async engine
    """
    return engine


# Create a test engine with NullPool for testing
def get_test_engine() -> AsyncEngine:
    """
    Get a SQLAlchemy async engine instance for testing.
    
    This engine uses NullPool to avoid connection pooling in tests,
    which can cause issues with transaction isolation.
    
    Returns:
        AsyncEngine: SQLAlchemy async engine for testing
    """
    test_engine = create_async_engine(
        str(settings.DATABASE_URL),  # ensure plain string for SQLAlchemy
        echo=settings.DATABASE_ECHO,
        poolclass=NullPool,  # Disable connection pooling for tests
    )
    return test_engine


# Create a test session factory
def get_test_session_maker() -> async_sessionmaker:
    """
    Get an async session maker for testing.
    
    Returns:
        async_sessionmaker: SQLAlchemy async session maker for testing
    """
    test_engine = get_test_engine()
    return async_sessionmaker(
        test_engine,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
