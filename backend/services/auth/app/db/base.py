"""
AITHERIA ALTOS - Auth Service Database Base Module
=================================================

This module imports all models to ensure they're registered with SQLAlchemy's
Base.metadata before creating tables. This is important for SQLAlchemy's
metadata-driven approach to work correctly, especially for relationship
definitions and foreign keys.

This file should be imported whenever you need access to all models.
"""

# Import Base class
from app.db.base_class import Base

# Import all models to register them with Base.metadata
from app.models.user import User
from app.models.role import Role
from app.models.permission import Permission
from app.models.organization import Organization
from app.models.audit_log import AuditLog
from app.models.api_token import APIToken

# Import any additional models here
# from app.models.some_model import SomeModel

__all__ = [
    "Base",
    "User",
    "Role",
    "Permission",
    "Organization",
    "AuditLog",
    "APIToken",
]
