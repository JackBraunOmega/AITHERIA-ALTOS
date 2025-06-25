"""
AITHERIA ALTOS - Auth Service Organization Model
==============================================

This module defines the Organization model for the Auth service, which represents
organizations in the AITHERIA ALTOS platform. Organizations are collections of users
that can collaborate and share resources.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, String, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Organization(Base):
    """
    Organization model representing organizations in the AITHERIA ALTOS platform.
    
    Organizations are collections of users that can collaborate and share resources.
    They provide a way to manage access control and resource sharing at a group level.
    """
    __tablename__ = "organizations"
    
    # Basic identification
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4,
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(255), 
        unique=True, 
        index=True, 
        nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(1000), 
        nullable=True
    )
    
    # Organization type and status
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False, 
        nullable=False,
        comment="System organizations cannot be modified or deleted"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True, 
        nullable=False
    )
    
    # Contact information
    email: Mapped[Optional[str]] = mapped_column(
        String(255), 
        nullable=True
    )
    website: Mapped[Optional[str]] = mapped_column(
        String(255), 
        nullable=True
    )
    
    # Timestamps
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
    
    # Relationships
    users: Mapped[List["User"]] = relationship(
        "User",
        back_populates="organization",
        lazy="noload"
    )
    
    def __repr__(self) -> str:
        """String representation of the Organization model."""
        return f"<Organization {self.name}>"
