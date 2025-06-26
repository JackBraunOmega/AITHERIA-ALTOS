"""
AITHERIA ALTOS - Project Service Database Initialization
=====================================================

This module handles the initialization of the database for the Project service.
It creates database tables and can be extended to add initial data if needed.

Functions:
    init_db: Initialize the database with tables.
"""

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.exc import SQLAlchemyError

from app.db.base import Base


async def init_db(engine: AsyncEngine) -> None:
    """
    Initialize the database with tables.
    
    Args:
        engine: SQLAlchemy async engine instance
    
    Raises:
        Exception: If database initialization fails
    """
    try:
        logger.info("Creating database tables for Project Service...")
        async with engine.begin() as conn:
            # Create all tables defined in Base.metadata
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Project Service database tables created successfully")
        
        # No initial data (like superusers or default roles) for Project Service,
        # but this function can be extended if needed in the future.
        
        logger.info("Project Service database initialization completed successfully")
    except SQLAlchemyError as e:
        logger.error(f"Database initialization failed for Project Service: {e}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during Project Service database initialization: {e}")
        raise
