"""
AITHERIA ALTOS - Auth Service Role Service
=========================================

This module provides functions for managing roles in the Auth service, including:
- Role CRUD operations (create, read, update, delete)
- Role search and filtering
- Permission assignment and management for roles

These functions are used by the API endpoints to interact with the role data
in a consistent and secure manner.
"""

from typing import List, Optional, Tuple, Any

from loguru import logger
from pydantic import UUID4
from sqlalchemy import select, func, and_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.role import Role
from app.models.permission import Permission
from app.schemas.role import RoleCreate, RoleUpdate


async def get_role_by_id(
    db: AsyncSession,
    role_id: UUID4,
) -> Optional[Role]:
    """
    Get a role by ID.

    Args:
        db: Database session
        role_id: Role ID to look up

    Returns:
        Role if found, None otherwise
    """
    result = await db.execute(
        select(Role)
        .where(Role.id == role_id)
        .options(selectinload(Role.permissions))
    )
    return result.scalars().first()


async def get_role_by_name(
    db: AsyncSession,
    name: str,
) -> Optional[Role]:
    """
    Get a role by name.

    Args:
        db: Database session
        name: Role name to look up

    Returns:
        Role if found, None otherwise
    """
    result = await db.execute(
        select(Role)
        .where(func.lower(Role.name) == func.lower(name))
        .options(selectinload(Role.permissions))
    )
    return result.scalars().first()


async def get_roles(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    name: Optional[str] = None,
    is_system: Optional[bool] = None,
) -> Tuple[List[Role], int]:
    """
    Get roles with filtering and pagination.

    Args:
        db: Database session
        skip: Number of roles to skip (for pagination)
        limit: Maximum number of roles to return
        name: Optional filter by role name (partial match)
        is_system: Optional filter by system role status

    Returns:
        Tuple of (list of roles, total count)
    """
    # Build query conditions
    conditions = []

    if name:
        conditions.append(Role.name.ilike(f"%{name}%"))

    if is_system is not None:
        conditions.append(Role.is_system == is_system)

    # Get total count
    count_query = select(func.count()).select_from(Role)
    if conditions:
        count_query = count_query.where(and_(*conditions))

    result = await db.execute(count_query)
    total = result.scalar()

    # Get roles with pagination
    query = (
        select(Role)
        .options(selectinload(Role.permissions))
        .where(and_(*conditions))
        .order_by(Role.name)
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)
    roles = result.scalars().all()

    return roles, total


async def create_role(
    db: AsyncSession,
    role_in: RoleCreate,
) -> Role:
    """
    Create a new role.

    Args:
        db: Database session
        role_in: Role creation data

    Returns:
        Created role

    Raises:
        ValueError: If role creation fails or role with same name exists
    """
    existing_role = await get_role_by_name(db, name=role_in.name)
    if existing_role:
        raise ValueError(f"Role with name '{role_in.name}' already exists")

    try:
        role = Role(
            name=role_in.name,
            description=role_in.description,
            is_system=role_in.is_system
        )

        # Add permissions if provided
        if role_in.permission_names:
            permissions = []
            for perm_name in role_in.permission_names:
                permission = await db.execute(select(Permission).where(Permission.name == perm_name))
                permission = permission.scalars().first()
                if not permission:
                    raise ValueError(f"Permission '{perm_name}' not found")
                permissions.append(permission)
            role.permissions = permissions

        db.add(role)
        await db.commit()
        await db.refresh(role)

        logger.info(f"Role created: {role.name}")
        return role
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Failed to create role: {e}")
        raise ValueError(f"Failed to create role: {e}")


async def update_role(
    db: AsyncSession,
    role: Role,
    role_in: RoleUpdate,
) -> Role:
    """
    Update a role.

    Args:
        db: Database session
        role: Role to update
        role_in: Role update data

    Returns:
        Updated role

    Raises:
        ValueError: If role update fails or role is a system role
    """
    if role.is_system:
        raise ValueError("System roles cannot be modified")

    try:
        update_data = role_in.dict(exclude_unset=True)

        # Handle name change separately to check for conflicts
        if "name" in update_data and update_data["name"] != role.name:
            existing_role = await get_role_by_name(db, name=update_data["name"])
            if existing_role and existing_role.id != role.id:
                raise ValueError(f"Role with name '{update_data['name']}' already exists")

        # Update role attributes
        for field, value in update_data.items():
            if field != "permission_names":
                setattr(role, field, value)

        # Update permissions if provided
        if "permission_names" in update_data and update_data["permission_names"] is not None:
            permissions = []
            for perm_name in update_data["permission_names"]:
                permission = await db.execute(select(Permission).where(Permission.name == perm_name))
                permission = permission.scalars().first()
                if not permission:
                    raise ValueError(f"Permission '{perm_name}' not found")
                permissions.append(permission)
            role.permissions = permissions

        db.add(role)
        await db.commit()
        await db.refresh(role)

        logger.info(f"Role updated: {role.name}")
        return role
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Failed to update role: {e}")
        raise ValueError(f"Failed to update role: {e}")


async def delete_role(
    db: AsyncSession,
    role: Role,
) -> None:
    """
    Delete a role.

    Args:
        db: Database session
        role: Role to delete

    Raises:
        ValueError: If role deletion fails or role is a system role
    """
    if role.is_system:
        raise ValueError("System roles cannot be deleted")

    try:
        await db.delete(role)
        await db.commit()

        logger.info(f"Role deleted: {role.name}")
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Failed to delete role: {e}")
        raise ValueError(f"Failed to delete role: {e}")


async def add_permission_to_role(
    db: AsyncSession,
    role: Role,
    permission_name: str,
) -> Role:
    """
    Add a permission to a role.

    Args:
        db: Database session
        role: Role to update
        permission_name: Name of the permission to add

    Returns:
        Updated role

    Raises:
        ValueError: If permission not found or role is a system role
    """
    if role.is_system:
        raise ValueError("System roles cannot be modified")

    try:
        result = await db.execute(select(Permission).where(Permission.name == permission_name))
        permission = result.scalars().first()

        if not permission:
            raise ValueError(f"Permission '{permission_name}' not found")

        if permission in role.permissions:
            return role  # Already has permission

        role.permissions.append(permission)
        db.add(role)
        await db.commit()
        await db.refresh(role)

        logger.info(f"Permission '{permission_name}' added to role '{role.name}'")
        return role
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Failed to add permission to role: {e}")
        raise ValueError(f"Failed to add permission to role: {e}")


async def remove_permission_from_role(
    db: AsyncSession,
    role: Role,
    permission_name: str,
) -> Role:
    """
    Remove a permission from a role.

    Args:
        db: Database session
        role: Role to update
        permission_name: Name of the permission to remove

    Returns:
        Updated role

    Raises:
        ValueError: If permission not found or role is a system role
    """
    if role.is_system:
        raise ValueError("System roles cannot be modified")

    try:
        result = await db.execute(select(Permission).where(Permission.name == permission_name))
        permission = result.scalars().first()

        if not permission:
            raise ValueError(f"Permission '{permission_name}' not found")

        if permission not in role.permissions:
            return role  # Does not have permission

        role.permissions.remove(permission)
        db.add(role)
        await db.commit()
        await db.refresh(role)

        logger.info(f"Permission '{permission_name}' removed from role '{role.name}'")
        return role
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Failed to remove permission from role: {e}")
        raise ValueError(f"Failed to remove permission from role: {e}")


async def get_role_permissions(
    db: AsyncSession,
    role: Role,
) -> List[str]:
    """
    Get all permission names for a given role.

    Args:
        db: Database session
        role: Role to get permissions for

    Returns:
        List of permission names
    """
    # Ensure permissions are loaded
    await db.refresh(role, attribute_names=["permissions"])
    return [permission.name for permission in role.permissions]


async def check_user_has_role(
    db: AsyncSession,
    user_id: UUID4,
    role_name: str,
) -> bool:
    """
    Check if a user has a specific role.

    Args:
        db: Database session
        user_id: User ID to check
        role_name: Name of the role to check for

    Returns:
        True if user has the role, False otherwise
    """
    from app.models.user import User
    
    # Query to check if user has the role
    result = await db.execute(
        select(User)
        .join(User.roles)
        .where(
            User.id == user_id,
            func.lower(Role.name) == func.lower(role_name)
        )
    )
    
    user = result.scalars().first()
    return user is not None
