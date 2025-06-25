"""
AITHERIA ALTOS - Auth Service User Model
=======================================

This module defines the User model for the Auth service, which represents
users in the AITHERIA ALTOS platform. It includes basic user properties,
authentication fields, and relationships to other models.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,  # Added missing Integer type
    String,
    Table,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

# Association table for User-Role many-to-many relationship
user_role = Table(
    "user_role",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)


class User(Base):
    """
    User model representing users in the AITHERIA ALTOS platform.
    
    This model stores user authentication information, profile data,
    and relationships to other entities like roles and organizations.
    """
    __tablename__ = "users"
    
    # Basic identification
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4,
        index=True
    )
    email: Mapped[str] = mapped_column(
        String(255), 
        unique=True, 
        index=True, 
        nullable=False
    )
    
    # Authentication fields
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Profile information
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Authentication method tracking
    auth_provider: Mapped[str] = mapped_column(
        String(50), 
        default="email", 
        nullable=False,
        comment="Authentication provider (email, google, orcid, etc.)"
    )
    auth_provider_id: Mapped[Optional[str]] = mapped_column(
        String(255), 
        nullable=True,
        comment="ID from the authentication provider"
    )
    
    # Multi-factor authentication
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mfa_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Security and session management
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), 
        nullable=True
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), 
        nullable=True
    )
    last_login_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, 
        default=0, 
        nullable=False
    )
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), 
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
    
    # Deletion tracking
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), 
        nullable=True
    )
    
    # Relationships
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary=user_role,
        back_populates="users",
        lazy="selectin"
    )
    
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("organizations.id", ondelete="SET NULL"), 
        nullable=True
    )
    organization: Mapped[Optional["Organization"]] = relationship(
        "Organization",
        back_populates="users",
        lazy="selectin"
    )
    
    # Audit logging
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        lazy="noload"
    )
    
    # API tokens
    api_tokens: Mapped[List["APIToken"]] = relationship(
        "APIToken",
        back_populates="user",
        lazy="noload"
    )
    
    def __repr__(self) -> str:
        """String representation of the User model."""
        return f"<User {self.email}>"
    
    @property
    def full_name(self) -> str:
        """Get the user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return self.email
    
    @property
    def is_locked(self) -> bool:
        """Check if the user account is locked."""
        if self.locked_until is None:
            return False
        return self.locked_until > datetime.now()
    
    def has_role(self, role_name: str) -> bool:
        """
        Check if the user has a specific role.
        
        Args:
            role_name: The name of the role to check
            
        Returns:
            True if the user has the role, False otherwise
        """
        return any(role.name == role_name for role in self.roles)
    
    def has_permission(self, permission_name: str) -> bool:
        """
        Check if the user has a specific permission through any of their roles.
        
        Args:
            permission_name: The name of the permission to check
            
        Returns:
            True if the user has the permission, False otherwise
        """
        for role in self.roles:
            for permission in role.permissions:
                if permission.name == permission_name:
                    return True
        return False
