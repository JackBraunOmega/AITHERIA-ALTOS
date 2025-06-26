"""
AITHERIA ALTOS - Auth Service Organization Service
=================================================

This module provides functions for managing organizations in the Auth service, including:
- Organization CRUD operations (create, read, update, delete)
- Organization search and filtering
- Member management (adding/removing users)
- Handling organization settings and metadata

These functions are used by the API endpoints to interact with the organization data
in a consistent and secure manner.
"""

from typing import List, Optional, Tuple, Any

from loguru import logger
from pydantic import UUID4, EmailStr
from sqlalchemy import select, func, and_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.organization import Organization
from app.models.user import User  # Import User model for member management
from app.schemas.organization import OrganizationCreate, OrganizationUpdate


async def get_organization_by_id(
    db: AsyncSession,
    org_id: UUID4,
) -> Optional[Organization]:
    """
    Get an organization by ID.

    Args:
        db: Database session
        org_id: Organization ID to look up

    Returns:
        Organization if found, None otherwise
    """
    result = await db.execute(
        select(Organization)
        .where(Organization.id == org_id)
        .options(selectinload(Organization.users))
    )
    return result.scalars().first()


async def get_organization_by_name(
    db: AsyncSession,
    name: str,
) -> Optional[Organization]:
    """
    Get an organization by name.

    Args:
        db: Database session
        name: Organization name to look up

    Returns:
        Organization if found, None otherwise
    """
    result = await db.execute(
        select(Organization)
        .where(func.lower(Organization.name) == func.lower(name))
        .options(selectinload(Organization.users))
    )
    return result.scalars().first()


async def get_organizations(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    name: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_system: Optional[bool] = None,
) -> Tuple[List[Organization], int]:
    """
    Get organizations with filtering and pagination.

    Args:
        db: Database session
        skip: Number of organizations to skip (for pagination)
        limit: Maximum number of organizations to return
        name: Optional filter by organization name (partial match)
        is_active: Optional filter by active status
        is_system: Optional filter by system organization status

    Returns:
        Tuple of (list of organizations, total count)
    """
    # Build query conditions
    conditions = []

    if name:
        conditions.append(Organization.name.ilike(f"%{name}%"))

    if is_active is not None:
        conditions.append(Organization.is_active == is_active)

    if is_system is not None:
        conditions.append(Organization.is_system == is_system)

    # Get total count
    count_query = select(func.count()).select_from(Organization)
    if conditions:
        count_query = count_query.where(and_(*conditions))

    result = await db.execute(count_query)
    total = result.scalar()

    # Get organizations with pagination
    query = (
        select(Organization)
        .options(selectinload(Organization.users))
        .where(and_(*conditions))
        .order_by(Organization.name)
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)
    organizations = result.scalars().all()

    return organizations, total


async def create_organization(
    db: AsyncSession,
    organization_in: OrganizationCreate,
) -> Organization:
    """
    Create a new organization.

    Args:
        db: Database session
        organization_in: Organization creation data

    Returns:
        Created organization

    Raises:
        ValueError: If organization creation fails or organization with same name exists
    """
    existing_organization = await get_organization_by_name(db, name=organization_in.name)
    if existing_organization:
        raise ValueError(f"Organization with name '{organization_in.name}' already exists")

    try:
        organization = Organization(
            name=organization_in.name,
            description=organization_in.description,
            is_active=organization_in.is_active,
            is_system=organization_in.is_system,
            email=organization_in.email,
            website=organization_in.website,
        )

        db.add(organization)
        await db.commit()
        await db.refresh(organization)

        logger.info(f"Organization created: {organization.name}")
        return organization
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Failed to create organization: {e}")
        raise ValueError(f"Failed to create organization: {e}")


async def update_organization(
    db: AsyncSession,
    organization: Organization,
    organization_in: OrganizationUpdate,
) -> Organization:
    """
    Update an organization.

    Args:
        db: Database session
        organization: Organization to update
        organization_in: Organization update data

    Returns:
        Updated organization

    Raises:
        ValueError: If organization update fails or organization is a system organization
    """
    if organization.is_system:
        raise ValueError("System organizations cannot be modified")

    try:
        update_data = organization_in.dict(exclude_unset=True)

        # Handle name change separately to check for conflicts
        if "name" in update_data and update_data["name"] != organization.name:
            existing_organization = await get_organization_by_name(db, name=update_data["name"])
            if existing_organization and existing_organization.id != organization.id:
                raise ValueError(f"Organization with name '{update_data['name']}' already exists")

        # Update organization attributes
        for field, value in update_data.items():
            setattr(organization, field, value)

        db.add(organization)
        await db.commit()
        await db.refresh(organization)

        logger.info(f"Organization updated: {organization.name}")
        return organization
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Failed to update organization: {e}")
        raise ValueError(f"Failed to update organization: {e}")


async def delete_organization(
    db: AsyncSession,
    organization: Organization,
) -> None:
    """
    Delete an organization.

    Args:
        db: Database session
        organization: Organization to delete

    Raises:
        ValueError: If organization deletion fails, is a system organization, or has associated users
    """
    if organization.is_system:
        raise ValueError("System organizations cannot be deleted")

    # Check for associated users
    if organization.users:
        raise ValueError("Cannot delete organization with associated users. Please reassign or delete users first.")

    try:
        await db.delete(organization)
        await db.commit()

        logger.info(f"Organization deleted: {organization.name}")
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Failed to delete organization: {e}")
        raise ValueError(f"Failed to delete organization: {e}")


async def add_user_to_organization(
    db: AsyncSession,
    user: User,
    organization: Organization,
) -> User:
    """
    Add a user to an organization.

    Args:
        db: Database session
        user: User to add
        organization: Organization to add the user to

    Returns:
        Updated user object

    Raises:
        ValueError: If user is already in the organization
    """
    if user.organization_id == organization.id:
        raise ValueError(f"User '{user.email}' is already a member of organization '{organization.name}'")

    try:
        user.organization_id = organization.id
        db.add(user)
        await db.commit()
        await db.refresh(user)

        logger.info(f"User '{user.email}' added to organization '{organization.name}'")
        return user
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Failed to add user to organization: {e}")
        raise ValueError(f"Failed to add user to organization: {e}")


async def remove_user_from_organization(
    db: AsyncSession,
    user: User,
) -> User:
    """
    Remove a user from their current organization.

    Args:
        db: Database session
        user: User to remove from organization

    Returns:
        Updated user object

    Raises:
        ValueError: If user is not currently in an organization
    """
    if user.organization_id is None:
        raise ValueError(f"User '{user.email}' is not currently assigned to an organization.")

    try:
        user.organization_id = None
        db.add(user)
        await db.commit()
        await db.refresh(user)

        logger.info(f"User '{user.email}' removed from organization")
        return user
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Failed to remove user from organization: {e}")
        raise ValueError(f"Failed to remove user from organization: {e}")


async def get_organization_users(
    db: AsyncSession,
    organization: Organization,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[User], int]:
    """
    Get users belonging to a specific organization with pagination.

    Args:
        db: Database session
        organization: The organization to get users for
        skip: Number of users to skip (for pagination)
        limit: Maximum number of users to return

    Returns:
        Tuple of (list of users, total count)
    """
    # Ensure users are loaded
    await db.refresh(organization, attribute_names=["users"])

    # Apply pagination manually since users are already loaded via relationship
    users = organization.users[skip : skip + limit]
    total = len(organization.users)

    return users, total
