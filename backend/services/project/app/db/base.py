"""
AITHERIA ALTOS - Project Service Database Base Module
====================================================

This module imports all models to ensure they're registered with SQLAlchemy's
Base.metadata before creating tables. This is important for SQLAlchemy's
metadata-driven approach to work correctly, especially for relationship
definitions and foreign keys.

This file should be imported whenever you need access to all models.
"""

# Import Base class
from app.db.base_class import Base

# Import all models to register them with Base.metadata
from app.models.project import Project
# from app.models.task import Task # Example for future models

__all__ = [
    "Base",
    "Project",
    # "Task", # Example for future models
]
