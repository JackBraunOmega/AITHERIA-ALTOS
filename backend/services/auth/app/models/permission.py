"""
AITHERIA ALTOS - Auth Service Permission Model
============================================

This module defines the Permission model for the Auth service, which represents
granular permissions in the AITHERIA ALTOS platform. Permissions define specific
actions that can be performed within the system and are assigned to roles.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Permission(Base):
    """
    Permission model representing granular permissions in the AITHERIA ALTOS platform.
    
    Permissions define specific actions that can be performed within the system.
    They are assigned to roles, which are then assigned to users.
    """
    __tablename__ = "permissions"
    
    # Basic identification
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4,
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(100), 
        unique=True, 
        index=True, 
        nullable=False
    )
    description: Mapped[str] = mapped_column(
        String(255), 
        nullable=True
    )
    
    # System permission flag
    is_system: Mapped[bool] = mapped_column(
        default=False, 
        nullable=False,
        comment="System permissions cannot be modified or deleted"
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
    roles = relationship(
        "Role",
        secondary="role_permission",
        back_populates="permissions",
        lazy="noload"
    )
    
    def __repr__(self) -> str:
        """String representation of the Permission model."""
        return f"<Permission {self.name}>"
