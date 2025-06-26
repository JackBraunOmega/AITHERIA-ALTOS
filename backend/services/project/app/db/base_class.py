"""
AITHERIA ALTOS - Project Service Base Model Class
=================================================

This module defines the base SQLAlchemy model class that all models in the
Project service will inherit from. It provides common functionality, type
annotations, and configuration for SQLAlchemy ORM models.

Usage:
    from app.db.base_class import Base
    
    class Project(Base):
        __tablename__ = "projects"
        
        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        # ...
"""

import uuid
from typing import Any, Dict
from datetime import datetime

from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase, registry, Mapped, mapped_column
from sqlalchemy import DateTime, func


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    
    This class provides common functionality for all models, including:
    - Automatic table name generation from class name
    - Common methods like to_dict() and from_dict()
    - Type annotations for SQLAlchemy ORM
    
    All models should inherit from this class.
    """
    
    # Registry for SQLAlchemy models
    registry = registry()
    
    # Use class name as table name by default
    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        """
        Generate table name automatically from class name.
        
        Returns:
            Table name in snake_case format
        """
        # Convert CamelCase to snake_case
        name = cls.__name__
        return ''.join(['_' + c.lower() if c.isupper() else c for c in name]).lstrip('_')
    
    # Common fields for all models
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.
        
        This method converts all columns of the model to a dictionary,
        which is useful for serialization and API responses.
        
        Returns:
            Dictionary representation of the model
        """
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Base":
        """
        Create model instance from dictionary.
        
        This method creates a new instance of the model from a dictionary,
        which is useful for deserialization and API requests.
        
        Args:
            data: Dictionary containing model attributes
            
        Returns:
            New instance of the model
        """
        return cls(**{
            key: value
            for key, value in data.items()
            if key in cls.__table__.columns.keys()
        })
    
    def __repr__(self) -> str:
        """
        String representation of the model.
        
        Returns:
            String representation in format <Class(key=value, ...)>
        """
        values = ", ".join(
            f"{column.name}={getattr(self, column.name)!r}"
            for column in self.__table__.columns
            if column.primary_key
        )
        return f"<{self.__class__.__name__}({values})>"
