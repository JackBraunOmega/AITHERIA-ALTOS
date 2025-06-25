"""
AITHERIA ALTOS - Auth Service Database Initialization
====================================================

This module handles the initialization of the database for the Auth service.
It creates database tables, initial superuser, and default roles/permissions.

Functions:
    init_db: Initialize the database with tables and initial data
    create_first_superuser: Create the initial superuser if configured
    create_default_roles_and_permissions: Create default roles and permissions
"""

import asyncio
from typing import List

from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import async_session_maker
from app.models.organization import Organization
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User


async def init_db(engine: AsyncEngine) -> None:
    """
    Initialize the database with tables and initial data.
    
    Args:
        engine: SQLAlchemy async engine instance
    
    Raises:
        Exception: If database initialization fails
    """
    try:
        logger.info("Creating database tables...")
        async with engine.begin() as conn:
            # Create all tables defined in Base.metadata
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
        
        # Create default roles and permissions
        async with async_session_maker() as session:
            await create_default_roles_and_permissions(session)
            await session.commit()
        
        logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


async def create_first_superuser(db: AsyncSession = None) -> None:
    """
    Create the first superuser if configured in settings.
    
    This function checks if a superuser already exists before creating a new one.
    
    Args:
        db: Optional SQLAlchemy async session. If not provided, a new session is created.
    
    Raises:
        ValueError: If superuser email or password is not configured
    """
    if not settings.FIRST_SUPERUSER or not settings.FIRST_SUPERUSER_PASSWORD:
        logger.info("First superuser not configured, skipping creation")
        return
    
    try:
        if db is None:
            async with async_session_maker() as session:
                db = session
                await _create_superuser(db)
                await db.commit()
        else:
            await _create_superuser(db)
    except Exception as e:
        logger.error(f"Failed to create first superuser: {e}")
        raise


async def _create_superuser(db: AsyncSession) -> None:
    """
    Internal helper function to create the superuser.
    
    Args:
        db: SQLAlchemy async session
    """
    # Check if superuser already exists
    result = await db.execute(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    )
    user = result.scalars().first()
    
    if user:
        logger.info(f"Superuser {settings.FIRST_SUPERUSER} already exists")
        return
    
    # Find admin role
    result = await db.execute(select(Role).where(Role.name == "admin"))
    admin_role = result.scalars().first()
    
    if not admin_role:
        logger.warning("Admin role not found, creating superuser without admin role")
    
    # Create default organization for superuser
    org = Organization(
        name="AITHERIA ALTOS Admin",
        description="Default organization for system administrators",
        is_system=True
    )
    db.add(org)
    await db.flush()
    
    # Create superuser
    superuser = User(
        email=settings.FIRST_SUPERUSER,
        hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
        is_active=True,
        is_superuser=True,
        is_verified=True,
        first_name="System",
        last_name="Administrator",
        organization_id=org.id
    )
    
    if admin_role:
        superuser.roles = [admin_role]
    
    db.add(superuser)
    await db.flush()
    
    logger.info(f"Superuser {settings.FIRST_SUPERUSER} created successfully")


async def create_default_roles_and_permissions(db: AsyncSession) -> None:
    """
    Create default roles and permissions for the system.
    
    This function creates the following roles if they don't exist:
    - admin: Full system access
    - lab_manager: Lab management access
    - researcher: Research and experiment access
    - viewer: Read-only access
    
    Args:
        db: SQLAlchemy async session
    """
    try:
        # Define default permissions
        default_permissions = [
            # User management permissions
            Permission(name="user:read", description="Read user information"),
            Permission(name="user:create", description="Create new users"),
            Permission(name="user:update", description="Update user information"),
            Permission(name="user:delete", description="Delete users"),
            
            # Project permissions
            Permission(name="project:read", description="Read project information"),
            Permission(name="project:create", description="Create new projects"),
            Permission(name="project:update", description="Update project information"),
            Permission(name="project:delete", description="Delete projects"),
            
            # Lab permissions
            Permission(name="lab:read", description="Read lab information"),
            Permission(name="lab:create", description="Create lab resources"),
            Permission(name="lab:update", description="Update lab information"),
            Permission(name="lab:delete", description="Delete lab resources"),
            
            # Experiment permissions
            Permission(name="experiment:read", description="Read experiment information"),
            Permission(name="experiment:create", description="Create new experiments"),
            Permission(name="experiment:update", description="Update experiment information"),
            Permission(name="experiment:delete", description="Delete experiments"),
            
            # System permissions
            Permission(name="system:read", description="Read system settings"),
            Permission(name="system:update", description="Update system settings"),
        ]
        
        # Create permissions if they don't exist
        existing_permissions = {}
        result = await db.execute(select(Permission))
        for perm in result.scalars().all():
            existing_permissions[perm.name] = perm
        
        permissions_to_create = []
        for perm in default_permissions:
            if perm.name not in existing_permissions:
                permissions_to_create.append(perm)
        
        if permissions_to_create:
            db.add_all(permissions_to_create)
            await db.flush()
            logger.info(f"Created {len(permissions_to_create)} new permissions")
        
        # Refresh permissions dict with newly created ones
        result = await db.execute(select(Permission))
        for perm in result.scalars().all():
            existing_permissions[perm.name] = perm
        
        # Define default roles with permissions
        default_roles = [
            {
                "name": "admin",
                "description": "Full system access",
                "permissions": [perm for perm in existing_permissions.values()]  # All permissions
            },
            {
                "name": "lab_manager",
                "description": "Lab management access",
                "permissions": [
                    existing_permissions.get("user:read"),
                    existing_permissions.get("project:read"),
                    existing_permissions.get("project:update"),
                    existing_permissions.get("lab:read"),
                    existing_permissions.get("lab:create"),
                    existing_permissions.get("lab:update"),
                    existing_permissions.get("lab:delete"),
                    existing_permissions.get("experiment:read"),
                    existing_permissions.get("experiment:create"),
                    existing_permissions.get("experiment:update"),
                ]
            },
            {
                "name": "researcher",
                "description": "Research and experiment access",
                "permissions": [
                    existing_permissions.get("user:read"),
                    existing_permissions.get("project:read"),
                    existing_permissions.get("lab:read"),
                    existing_permissions.get("experiment:read"),
                    existing_permissions.get("experiment:create"),
                    existing_permissions.get("experiment:update"),
                ]
            },
            {
                "name": "viewer",
                "description": "Read-only access",
                "permissions": [
                    existing_permissions.get("user:read"),
                    existing_permissions.get("project:read"),
                    existing_permissions.get("lab:read"),
                    existing_permissions.get("experiment:read"),
                ]
            }
        ]
        
        # Create roles if they don't exist
        existing_roles = {}
        result = await db.execute(select(Role))
        for role in result.scalars().all():
            existing_roles[role.name] = role
        
        for role_data in default_roles:
            role_name = role_data["name"]
            
            if role_name in existing_roles:
                # Update existing role permissions
                role = existing_roles[role_name]
                role.permissions = [p for p in role_data["permissions"] if p is not None]
                db.add(role)
                logger.info(f"Updated permissions for role: {role_name}")
            else:
                # Create new role
                role = Role(
                    name=role_name,
                    description=role_data["description"],
                    permissions=[p for p in role_data["permissions"] if p is not None]
                )
                db.add(role)
                logger.info(f"Created new role: {role_name}")
        
        await db.flush()
        logger.info("Default roles and permissions created successfully")
        
    except SQLAlchemyError as e:
        logger.error(f"Failed to create default roles and permissions: {e}")
        await db.rollback()
        raise
