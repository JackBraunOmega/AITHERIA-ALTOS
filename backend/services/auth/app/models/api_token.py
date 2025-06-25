"""
AITHERIA ALTOS - Auth Service API Token Model
============================================

This module defines the APIToken model for the Auth service, which represents
API tokens that can be used for programmatic access to the AITHERIA ALTOS platform.
These tokens allow users to authenticate with the API without using their username
and password.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, func, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class APIToken(Base):
    """
    APIToken model representing API access tokens in the AITHERIA ALTOS platform.
    
    API tokens provide a secure way for users to authenticate with the API
    programmatically, without exposing their credentials. They can be used
    for integrations, scripts, and automated workflows.
    """
    __tablename__ = "api_tokens"
    
    # Basic identification
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4,
        index=True
    )
    
    # Token information
    name: Mapped[str] = mapped_column(
        String(255), 
        nullable=False,
        comment="Human-readable name for the token"
    )
    
    token: Mapped[str] = mapped_column(
        String(255), 
        unique=True, 
        index=True, 
        nullable=False,
        comment="Hashed token value"
    )
    
    # Token metadata
    description: Mapped[Optional[str]] = mapped_column(
        Text, 
        nullable=True,
        comment="Description of the token's purpose"
    )
    
    scopes: Mapped[Optional[str]] = mapped_column(
        String(1000), 
        nullable=True,
        comment="Space-separated list of permission scopes"
    )
    
    # Token status
    is_active: Mapped[bool] = mapped_column(
        default=True, 
        nullable=False,
        comment="Whether the token is active and can be used"
    )
    
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), 
        nullable=True,
        comment="When the token was last used"
    )
    
    # Token owner
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    
    # Expiration
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), 
        nullable=True,
        index=True,
        comment="When the token expires (null = no expiration)"
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
    user = relationship(
        "User",
        back_populates="api_tokens",
        lazy="joined"
    )
    
    def __repr__(self) -> str:
        """String representation of the APIToken model."""
        return f"<APIToken {self.name} for user {self.user_id}>"
    
    @property
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        if self.expires_at is None:
            return False
        return self.expires_at < datetime.now()
    
    @property
    def is_valid(self) -> bool:
        """Check if the token is valid (active and not expired)."""
        return self.is_active and not self.is_expired
