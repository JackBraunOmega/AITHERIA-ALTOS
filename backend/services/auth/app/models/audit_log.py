"""
AITHERIA ALTOS - Auth Service Audit Log Model
============================================

This module defines the AuditLog model for the Auth service, which records
all significant user actions in the AITHERIA ALTOS platform for security,
compliance, and auditing purposes.

The audit log is crucial for compliance with FDA 21 CFR Part 11 and HIPAA
regulations, providing an immutable record of all system activities.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class AuditLog(Base):
    """
    AuditLog model for recording user actions in the AITHERIA ALTOS platform.
    
    This model stores detailed information about user activities, including
    what action was performed, on which resource, by whom, when, and additional
    context details. It provides a comprehensive audit trail for compliance
    and security purposes.
    """
    __tablename__ = "audit_logs"
    
    # Basic identification
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4,
        index=True
    )
    
    # Action information
    action: Mapped[str] = mapped_column(
        String(100), 
        nullable=False,
        index=True,
        comment="Type of action performed (create, read, update, delete, login, etc.)"
    )
    
    # Resource information
    resource_type: Mapped[str] = mapped_column(
        String(100), 
        nullable=False,
        index=True,
        comment="Type of resource affected (user, project, experiment, etc.)"
    )
    
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(255), 
        nullable=True,
        index=True,
        comment="ID of the specific resource affected"
    )
    
    # User who performed the action
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True,
        index=True,
        comment="User who performed the action (null for system actions)"
    )
    
    # Additional context
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # IPv6 addresses can be up to 45 characters
        nullable=True,
        comment="IP address from which the action was performed"
    )
    
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="User agent (browser/client) information"
    )
    
    # Detailed information about the action
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional details about the action in JSON format"
    )
    
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="success",
        comment="Outcome of the action (success, failure, error)"
    )
    
    # For failed actions, store the error message
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if the action failed"
    )
    
    # Timestamps
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False,
        index=True,
        comment="When the action occurred"
    )
    
    # Relationships
    user = relationship(
        "User",
        back_populates="audit_logs",
        lazy="joined"
    )
    
    def __repr__(self) -> str:
        """String representation of the AuditLog model."""
        return f"<AuditLog {self.action} on {self.resource_type}:{self.resource_id} by {self.user_id} at {self.timestamp}>"
