"""
AITHERIA ALTOS - Auth Service Role Model
=======================================

This module defines the Role model for the Auth service, which represents
user roles in the AITHERIA ALTOS platform. Roles are collections of permissions
that can be assigned to users.
"""

import uuid
from datetime import datetime
from typing import List

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

# Association table for Role-Permission many-to-many relationship
role_permission = Table(
    "role_permission",
    Base.metadata,
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)


class Role(Base):
    """
    Role model representing user roles in the AITHERIA ALTOS platform.
    
    Roles are collections of permissions that can be assigned to users.
    They define what actions users can perform in the system.
    """
    __tablename__ = "roles"
    
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
    
    # System role flag
    is_system: Mapped[bool] = mapped_column(
        default=False, 
        nullable=False,
        comment="System roles cannot be modified or deleted"
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
        secondary="user_role",
        back_populates="roles",
        lazy="selectin"
    )
    
    permissions: Mapped[List["Permission"]] = relationship(
        "Permission",
        secondary=role_permission,
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        """String representation of the Role model."""
        return f"<Role {self.name}>"
