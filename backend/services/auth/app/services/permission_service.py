"""
AITHERIA ALTOS - Auth Service Permission Service
===============================================

This module provides functions for managing permissions in the Auth service, including:
- Permission CRUD operations (create, read, update, delete)
- Permission search and filtering
- Permission validation and checking

These functions are used by the API endpoints to interact with permission data
in a consistent and secure manner.
"""

from typing import List, Optional, Tuple, Any

from loguru import logger
from pydantic import UUID4
from sqlalchemy import select, func, and_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.permission import Permission
from app.schemas.permission import PermissionCreate, PermissionUpdate


async def get_permission_by_id(
    db: AsyncSession,
    permission_id: UUID4,
) -> Optional[Permission]:
    """
    Get a permission by ID.

    Args:
        db: Database session
        permission_id: Permission ID to look up

    Returns:
        Permission if found, None otherwise
    """
    result = await db.execute(
        select(Permission).where(Permission.id == permission_id)
    )
    return result.scalars().first()


async def get_permission_by_name(
    db: AsyncSession,
    name: str,
) -> Optional[Permission]:
    """
    Get a permission by name.

    Args:
        db: Database session
        name: Permission name to look up

    Returns:
        Permission if found, None otherwise
    """
    result = await db.execute(
        select(Permission).where(func.lower(Permission.name) == func.lower(name))
    )
    return result.scalars().first()


async def get_permissions(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    name: Optional[str] = None,
    resource: Optional[str] = None,
    action: Optional[str] = None,
) -> Tuple[List[Permission], int]:
    """
    Get permissions with filtering and pagination.

    Args:
        db: Database session
        skip: Number of permissions to skip (for pagination)
        limit: Maximum number of permissions to return
        name: Optional filter by permission name (partial match)
        resource: Optional filter by resource
        action: Optional filter by action

    Returns:
        Tuple of (list of permissions, total count)
    """
    # Build query conditions
    conditions = []

    if name:
        conditions.append(Permission.name.ilike(f"%{name}%"))

    if resource:
        conditions.append(Permission.resource.ilike(f"%{resource}%"))

    if action:
        conditions.append(Permission.action.ilike(f"%{action}%"))

    # Get total count
    count_query = select(func.count()).select_from(Permission)
    if conditions:
        count_query = count_query.where(and_(*conditions))

    result = await db.execute(count_query)
    total = result.scalar()

    # Get permissions with pagination
    query = (
        select(Permission)
        .where(and_(*conditions))
        .order_by(Permission.name)
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)
    permissions = result.scalars().all()

    return permissions, total


async def create_permission(
    db: AsyncSession,
    permission_in: PermissionCreate,
) -> Permission:
    """
    Create a new permission.

    Args:
        db: Database session
        permission_in: Permission creation data

    Returns:
        Created permission

    Raises:
        ValueError: If permission creation fails or permission with same name exists
    """
    existing_permission = await get_permission_by_name(db, name=permission_in.name)
    if existing_permission:
        raise ValueError(f"Permission with name '{permission_in.name}' already exists")

    try:
        permission = Permission(
            name=permission_in.name,
            resource=permission_in.resource,
            action=permission_in.action,
            description=permission_in.description,
            is_system=permission_in.is_system
        )

        db.add(permission)
        await db.commit()
        await db.refresh(permission)

        logger.info(f"Permission created: {permission.name}")
        return permission
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Failed to create permission: {e}")
        raise ValueError(f"Failed to create permission: {e}")


async def update_permission(
    db: AsyncSession,
    permission: Permission,
    permission_in: PermissionUpdate,
) -> Permission:
    """
    Update a permission.

    Args:
        db: Database session
        permission: Permission to update
        permission_in: Permission update data

    Returns:
        Updated permission

    Raises:
        ValueError: If permission update fails or permission is a system permission
    """
    if permission.is_system:
        raise ValueError("System permissions cannot be modified")

    try:
        update_data = permission_in.dict(exclude_unset=True)

        # Handle name change separately to check for conflicts
        if "name" in update_data and update_data["name"] != permission.name:
            existing_permission = await get_permission_by_name(db, name=update_data["name"])
            if existing_permission and existing_permission.id != permission.id:
                raise ValueError(f"Permission with name '{update_data['name']}' already exists")

        # Update permission attributes
        for field, value in update_data.items():
            setattr(permission, field, value)

        db.add(permission)
        await db.commit()
        await db.refresh(permission)

        logger.info(f"Permission updated: {permission.name}")
        return permission
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Failed to update permission: {e}")
        raise ValueError(f"Failed to update permission: {e}")


async def delete_permission(
    db: AsyncSession,
    permission: Permission,
) -> None:
    """
    Delete a permission.

    Args:
        db: Database session
        permission: Permission to delete

    Raises:
        ValueError: If permission deletion fails or permission is a system permission
    """
    if permission.is_system:
        raise ValueError("System permissions cannot be deleted")

    try:
        await db.delete(permission)
        await db.commit()

        logger.info(f"Permission deleted: {permission.name}")
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Failed to delete permission: {e}")
        raise ValueError(f"Failed to delete permission: {e}")


async def check_user_has_permission(
    db: AsyncSession,
    user_id: UUID4,
    permission_name: str,
) -> bool:
    """
    Check if a user has a specific permission.

    Args:
        db: Database session
        user_id: User ID to check
        permission_name: Name of the permission to check for

    Returns:
        True if user has the permission, False otherwise
    """
    from app.models.user import User
    from app.models.role import Role
    
    # Query to check if user has the permission through any of their roles
    result = await db.execute(
        select(User)
        .join(User.roles)
        .join(Role.permissions)
        .where(
            User.id == user_id,
            func.lower(Permission.name) == func.lower(permission_name)
        )
    )
    
    user = result.scalars().first()
    return user is not None


async def check_user_has_resource_action(
    db: AsyncSession,
    user_id: UUID4,
    resource: str,
    action: str,
) -> bool:
    """
    Check if a user has permission to perform an action on a resource.

    Args:
        db: Database session
        user_id: User ID to check
        resource: Resource to check access for
        action: Action to check permission for

    Returns:
        True if user has permission, False otherwise
    """
    from app.models.user import User
    from app.models.role import Role
    
    # Query to check if user has the permission through any of their roles
    result = await db.execute(
        select(User)
        .join(User.roles)
        .join(Role.permissions)
        .where(
            User.id == user_id,
            Permission.resource == resource,
            Permission.action == action
        )
    )
    
    user = result.scalars().first()
    return user is not None


async def get_user_permissions(
    db: AsyncSession,
    user_id: UUID4,
) -> List[Permission]:
    """
    Get all permissions for a user.

    Args:
        db: Database session
        user_id: User ID to get permissions for

    Returns:
        List of permissions
    """
    from app.models.user import User
    from app.models.role import Role
    
    # Query to get all permissions for a user through their roles
    result = await db.execute(
        select(Permission)
        .join(Permission.roles)
        .join(Role.users)
        .where(User.id == user_id)
        .distinct()
    )
    
    return result.scalars().all()


async def create_default_permissions(
    db: AsyncSession,
) -> List[Permission]:
    """
    Create default system permissions if they don't exist.

    Args:
        db: Database session

    Returns:
        List of created permissions
    """
    default_permissions = [
        # User management permissions
        {"name": "users:read", "resource": "users", "action": "read", "description": "Can view user details", "is_system": True},
        {"name": "users:create", "resource": "users", "action": "create", "description": "Can create new users", "is_system": True},
        {"name": "users:update", "resource": "users", "action": "update", "description": "Can update user details", "is_system": True},
        {"name": "users:delete", "resource": "users", "action": "delete", "description": "Can delete users", "is_system": True},
        
        # Role management permissions
        {"name": "roles:read", "resource": "roles", "action": "read", "description": "Can view roles", "is_system": True},
        {"name": "roles:create", "resource": "roles", "action": "create", "description": "Can create new roles", "is_system": True},
        {"name": "roles:update", "resource": "roles", "action": "update", "description": "Can update roles", "is_system": True},
        {"name": "roles:delete", "resource": "roles", "action": "delete", "description": "Can delete roles", "is_system": True},
        
        # Permission management permissions
        {"name": "permissions:read", "resource": "permissions", "action": "read", "description": "Can view permissions", "is_system": True},
        {"name": "permissions:create", "resource": "permissions", "action": "create", "description": "Can create new permissions", "is_system": True},
        {"name": "permissions:update", "resource": "permissions", "action": "update", "description": "Can update permissions", "is_system": True},
        {"name": "permissions:delete", "resource": "permissions", "action": "delete", "description": "Can delete permissions", "is_system": True},
        
        # Organization management permissions
        {"name": "organizations:read", "resource": "organizations", "action": "read", "description": "Can view organizations", "is_system": True},
        {"name": "organizations:create", "resource": "organizations", "action": "create", "description": "Can create new organizations", "is_system": True},
        {"name": "organizations:update", "resource": "organizations", "action": "update", "description": "Can update organizations", "is_system": True},
        {"name": "organizations:delete", "resource": "organizations", "action": "delete", "description": "Can delete organizations", "is_system": True},
        
        # API token management permissions
        {"name": "tokens:read", "resource": "tokens", "action": "read", "description": "Can view API tokens", "is_system": True},
        {"name": "tokens:create", "resource": "tokens", "action": "create", "description": "Can create new API tokens", "is_system": True},
        {"name": "tokens:delete", "resource": "tokens", "action": "delete", "description": "Can delete API tokens", "is_system": True},
        
        # Audit log permissions
        {"name": "audit:read", "resource": "audit", "action": "read", "description": "Can view audit logs", "is_system": True},
        
        # Admin permissions
        {"name": "admin:access", "resource": "admin", "action": "access", "description": "Can access admin features", "is_system": True},
        {"name": "admin:settings", "resource": "admin", "action": "settings", "description": "Can modify system settings", "is_system": True},
    ]
    
    created_permissions = []
    
    for perm_data in default_permissions:
        # Check if permission already exists
        existing = await get_permission_by_name(db, name=perm_data["name"])
        if not existing:
            # Create permission if it doesn't exist
            permission = Permission(**perm_data)
            db.add(permission)
            created_permissions.append(permission)
            logger.info(f"Created default permission: {permission.name}")
    
    if created_permissions:
        await db.commit()
        
    return created_permissions
