"""
AITHERIA ALTOS - Auth Service User Service
=========================================

This module provides functions for managing users in the Auth service, including:
- User CRUD operations (create, read, update, delete)
- User authentication and password management
- User search and filtering
- Role assignment and management
- Organization membership management

These functions are used by the API endpoints to interact with the user data
in a consistent and secure manner.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Union

from fastapi import Depends, HTTPException, status
from loguru import logger
from pydantic import UUID4, EmailStr
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.core.config import settings
from app.core.password import get_password_hash, verify_password
from app.db.session import get_db
from app.models.user import User
from app.models.role import Role
from app.models.organization import Organization
from app.schemas.user import UserCreate, UserUpdate


async def get_user_by_email(
    db: AsyncSession,
    email: str,
) -> Optional[User]:
    """
    Get a user by email.
    
    Args:
        db: Database session
        email: Email address to look up
        
    Returns:
        User if found, None otherwise
    """
    result = await db.execute(
        select(User)
        .where(User.email == email)
        .options(
            selectinload(User.roles),
            selectinload(User.organization)
        )
    )
    return result.scalars().first()


async def get_user_by_id(
    db: AsyncSession,
    user_id: UUID4,
) -> Optional[User]:
    """
    Get a user by ID.
    
    Args:
        db: Database session
        user_id: User ID to look up
        
    Returns:
        User if found, None otherwise
    """
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.roles),
            selectinload(User.organization)
        )
    )
    return result.scalars().first()


async def get_users(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    email: Optional[str] = None,
    is_active: Optional[bool] = None,
    role: Optional[str] = None,
    organization_id: Optional[UUID4] = None,
) -> Tuple[List[User], int]:
    """
    Get users with filtering and pagination.
    
    Args:
        db: Database session
        skip: Number of users to skip (for pagination)
        limit: Maximum number of users to return
        email: Optional filter by email (partial match)
        is_active: Optional filter by active status
        role: Optional filter by role name
        organization_id: Optional filter by organization ID
        
    Returns:
        Tuple of (list of users, total count)
    """
    # Build query conditions
    conditions = []
    
    if email:
        conditions.append(User.email.ilike(f"%{email}%"))
    
    if is_active is not None:
        conditions.append(User.is_active == is_active)
    
    if organization_id:
        conditions.append(User.organization_id == organization_id)
    
    # Base query
    base_query = select(User).options(
        selectinload(User.roles),
        selectinload(User.organization)
    )
    
    # Apply conditions
    if conditions:
        base_query = base_query.where(and_(*conditions))
    
    # Handle role filter separately as it requires a join
    if role:
        base_query = base_query.join(User.roles).where(Role.name == role)
    
    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Get users with pagination
    query = base_query.order_by(User.email).offset(skip).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()
    
    return users, total


async def create_user(
    db: AsyncSession,
    user_in: UserCreate,
) -> User:
    """
    Create a new user.
    
    Args:
        db: Database session
        user_in: User creation data
        
    Returns:
        Created user
        
    Raises:
        ValueError: If user creation fails
    """
    try:
        # Hash the password
        hashed_password = get_password_hash(user_in.password)
        
        # Create user object
        user = User(
            email=user_in.email,
            hashed_password=hashed_password,
            first_name=user_in.first_name,
            last_name=user_in.last_name,
            is_active=user_in.is_active,
            is_superuser=user_in.is_superuser,
            is_verified=user_in.is_verified,
            auth_provider=user_in.auth_provider or "email",
            organization_id=user_in.organization_id,
        )
        
        # Save to database
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"User created: {user.email}")
        return user
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create user: {e}")
        raise ValueError(f"Failed to create user: {e}")


async def update_user(
    db: AsyncSession,
    user: User,
    user_in: UserUpdate,
) -> User:
    """
    Update a user.
    
    Args:
        db: Database session
        user: User to update
        user_in: User update data
        
    Returns:
        Updated user
        
    Raises:
        ValueError: If user update fails
    """
    try:
        # Update user attributes
        update_data = user_in.dict(exclude_unset=True)
        
        # Handle password separately
        if "password" in update_data:
            hashed_password = get_password_hash(update_data["password"])
            update_data["hashed_password"] = hashed_password
            update_data["password_changed_at"] = datetime.utcnow()
            del update_data["password"]
        
        # Update user object
        for field, value in update_data.items():
            setattr(user, field, value)
        
        # Save to database
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"User updated: {user.email}")
        return user
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update user: {e}")
        raise ValueError(f"Failed to update user: {e}")


async def delete_user(
    db: AsyncSession,
    user: User,
) -> None:
    """
    Delete a user.
    
    Args:
        db: Database session
        user: User to delete
        
    Raises:
        ValueError: If user deletion fails
    """
    try:
        # Soft delete by setting deleted_at timestamp
        user.deleted_at = datetime.utcnow()
        user.is_active = False
        
        # Save to database
        db.add(user)
        await db.commit()
        
        logger.info(f"User deleted: {user.email}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete user: {e}")
        raise ValueError(f"Failed to delete user: {e}")


async def hard_delete_user(
    db: AsyncSession,
    user: User,
) -> None:
    """
    Permanently delete a user from the database.
    
    This function should be used with caution, as it permanently removes
    the user from the database. In most cases, soft deletion using delete_user()
    is preferred.
    
    Args:
        db: Database session
        user: User to delete
        
    Raises:
        ValueError: If user deletion fails
    """
    try:
        # Remove user from database
        await db.delete(user)
        await db.commit()
        
        logger.info(f"User permanently deleted: {user.email}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to permanently delete user: {e}")
        raise ValueError(f"Failed to permanently delete user: {e}")


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> Optional[User]:
    """
    Authenticate a user with email and password.
    
    Args:
        db: Database session
        email: User email
        password: User password
        
    Returns:
        Authenticated user if successful, None otherwise
    """
    # Get user by email
    user = await get_user_by_email(db, email=email)
    
    # Check if user exists and password is correct
    if not user or not verify_password(password, user.hashed_password):
        return None
    
    # Check if user is active
    if not user.is_active:
        return None
    
    return user


async def update_user_password(
    db: AsyncSession,
    user: User,
    new_password: str,
) -> User:
    """
    Update a user's password.
    
    Args:
        db: Database session
        user: User to update
        new_password: New password
        
    Returns:
        Updated user
        
    Raises:
        ValueError: If password update fails
    """
    try:
        # Hash the new password
        hashed_password = get_password_hash(new_password)
        
        # Update user
        user.hashed_password = hashed_password
        user.password_changed_at = datetime.utcnow()
        
        # Reset failed login attempts
        user.failed_login_attempts = 0
        user.locked_until = None
        
        # Save to database
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"Password updated for user: {user.email}")
        return user
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update password: {e}")
        raise ValueError(f"Failed to update password: {e}")


async def update_user_last_login(
    db: AsyncSession,
    user: User,
    ip_address: Optional[str] = None,
) -> User:
    """
    Update a user's last login information.
    
    Args:
        db: Database session
        user: User to update
        ip_address: Optional IP address of the login
        
    Returns:
        Updated user
    """
    try:
        # Update user
        user.last_login_at = datetime.utcnow()
        user.last_login_ip = ip_address
        user.failed_login_attempts = 0
        user.locked_until = None
        
        # Save to database
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        return user
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update last login: {e}")
        # Don't raise exception for login tracking to avoid disrupting authentication
        return user


async def increment_failed_login(
    db: AsyncSession,
    user: User,
) -> User:
    """
    Increment a user's failed login attempts and lock account if necessary.
    
    Args:
        db: Database session
        user: User to update
        
    Returns:
        Updated user
    """
    try:
        # Increment failed login attempts
        user.failed_login_attempts += 1
        
        # Lock account if too many failed attempts
        if user.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
            lock_duration = settings.ACCOUNT_LOCKOUT_MINUTES
            user.locked_until = datetime.utcnow() + timedelta(minutes=lock_duration)
            logger.warning(f"User account locked due to too many failed login attempts: {user.email}")
        
        # Save to database
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        return user
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to increment failed login: {e}")
        # Don't raise exception for login tracking to avoid disrupting authentication
        return user


async def add_user_to_role(
    db: AsyncSession,
    user: User,
    role_name: str,
) -> User:
    """
    Add a user to a role.
    
    Args:
        db: Database session
        user: User to update
        role_name: Name of the role to add
        
    Returns:
        Updated user
        
    Raises:
        ValueError: If role not found or assignment fails
    """
    try:
        # Get role by name
        result = await db.execute(select(Role).where(Role.name == role_name))
        role = result.scalars().first()
        
        if not role:
            raise ValueError(f"Role not found: {role_name}")
        
        # Check if user already has this role
        if any(r.id == role.id for r in user.roles):
            # User already has this role, nothing to do
            return user
        
        # Add role to user
        user.roles.append(role)
        
        # Save to database
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"Role {role_name} assigned to user: {user.email}")
        return user
    except ValueError as e:
        # Re-raise ValueError for specific error messages
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to add user to role: {e}")
        raise ValueError(f"Failed to add user to role: {e}")


async def remove_user_from_role(
    db: AsyncSession,
    user: User,
    role_name: str,
) -> User:
    """
    Remove a user from a role.
    
    Args:
        db: Database session
        user: User to update
        role_name: Name of the role to remove
        
    Returns:
        Updated user
        
    Raises:
        ValueError: If role not found or removal fails
    """
    try:
        # Get role by name
        result = await db.execute(select(Role).where(Role.name == role_name))
        role = result.scalars().first()
        
        if not role:
            raise ValueError(f"Role not found: {role_name}")
        
        # Check if user has this role
        if not any(r.id == role.id for r in user.roles):
            # User doesn't have this role, nothing to do
            return user
        
        # Remove role from user
        user.roles = [r for r in user.roles if r.id != role.id]
        
        # Save to database
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"Role {role_name} removed from user: {user.email}")
        return user
    except ValueError as e:
        # Re-raise ValueError for specific error messages
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to remove user from role: {e}")
        raise ValueError(f"Failed to remove user from role: {e}")


async def get_user_permissions(
    db: AsyncSession,
    user: User,
) -> List[str]:
    """
    Get all permissions for a user through their roles.
    
    Args:
        db: Database session
        user: User to get permissions for
        
    Returns:
        List of permission names
    """
    # Get user with roles and permissions
    result = await db.execute(
        select(User)
        .where(User.id == user.id)
        .options(
            selectinload(User.roles).selectinload(Role.permissions)
        )
    )
    user_with_permissions = result.scalars().first()
    
    if not user_with_permissions:
        return []
    
    # Collect all permissions from all roles
    permissions = set()
    for role in user_with_permissions.roles:
        for permission in role.permissions:
            permissions.add(permission.name)
    
    return list(permissions)


async def check_user_has_permission(
    db: AsyncSession,
    user: User,
    permission_name: str,
) -> bool:
    """
    Check if a user has a specific permission.
    
    Args:
        db: Database session
        user: User to check
        permission_name: Name of the permission to check
        
    Returns:
        True if user has the permission, False otherwise
    """
    # Superusers have all permissions
    if user.is_superuser:
        return True
    
    # Get user permissions
    permissions = await get_user_permissions(db, user)
    
    # Check if permission is in the list
    return permission_name in permissions


async def check_user_has_role(
    db: AsyncSession,
    user: User,
    role_name: str,
) -> bool:
    """
    Check if a user has a specific role.
    
    Args:
        db: Database session
        user: User to check
        role_name: Name of the role to check
        
    Returns:
        True if user has the role, False otherwise
    """
    # Get user with roles
    result = await db.execute(
        select(User)
        .where(User.id == user.id)
        .options(selectinload(User.roles))
    )
    user_with_roles = result.scalars().first()
    
    if not user_with_roles:
        return False
    
    # Check if role is in the list
    return any(role.name == role_name for role in user_with_roles.roles)


async def get_users_by_role(
    db: AsyncSession,
    role_name: str,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[User], int]:
    """
    Get all users with a specific role.
    
    Args:
        db: Database session
        role_name: Name of the role to filter by
        skip: Number of users to skip (for pagination)
        limit: Maximum number of users to return
        
    Returns:
        Tuple of (list of users, total count)
    """
    # Build query to get users with the specified role
    query = (
        select(User)
        .join(User.roles)
        .where(Role.name == role_name)
        .options(
            selectinload(User.roles),
            selectinload(User.organization)
        )
    )
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Get users with pagination
    query = query.order_by(User.email).offset(skip).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()
    
    return users, total


async def search_users(
    db: AsyncSession,
    search_term: str,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[User], int]:
    """
    Search for users by email, first name, or last name.
    
    Args:
        db: Database session
        search_term: Term to search for
        skip: Number of users to skip (for pagination)
        limit: Maximum number of users to return
        
    Returns:
        Tuple of (list of matching users, total count)
    """
    # Build search condition
    search_condition = or_(
        User.email.ilike(f"%{search_term}%"),
        User.first_name.ilike(f"%{search_term}%"),
        User.last_name.ilike(f"%{search_term}%"),
    )
    
    # Get total count
    count_query = select(func.count()).select_from(User).where(search_condition)
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Get matching users with pagination
    query = (
        select(User)
        .where(search_condition)
        .options(
            selectinload(User.roles),
            selectinload(User.organization)
        )
        .order_by(User.email)
        .offset(skip)
        .limit(limit)
    )
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return users, total


async def verify_user_email(
    db: AsyncSession,
    user: User,
) -> User:
    """
    Mark a user's email as verified.
    
    Args:
        db: Database session
        user: User to update
        
    Returns:
        Updated user
        
    Raises:
        ValueError: If verification fails
    """
    try:
        # Update user
        user.is_verified = True
        
        # Save to database
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"Email verified for user: {user.email}")
        return user
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to verify user email: {e}")
        raise ValueError(f"Failed to verify user email: {e}")


async def activate_user(
    db: AsyncSession,
    user: User,
) -> User:
    """
    Activate a user account.
    
    Args:
        db: Database session
        user: User to activate
        
    Returns:
        Updated user
        
    Raises:
        ValueError: If activation fails
    """
    try:
        # Update user
        user.is_active = True
        
        # Save to database
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"User activated: {user.email}")
        return user
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to activate user: {e}")
        raise ValueError(f"Failed to activate user: {e}")


async def deactivate_user(
    db: AsyncSession,
    user: User,
) -> User:
    """
    Deactivate a user account.
    
    Args:
        db: Database session
        user: User to deactivate
        
    Returns:
        Updated user
        
    Raises:
        ValueError: If deactivation fails
    """
    try:
        # Update user
        user.is_active = False
        
        # Save to database
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"User deactivated: {user.email}")
        return user
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to deactivate user: {e}")
        raise ValueError(f"Failed to deactivate user: {e}")


async def change_user_organization(
    db: AsyncSession,
    user: User,
    organization_id: Optional[UUID4],
) -> User:
    """
    Change a user's organization.
    
    Args:
        db: Database session
        user: User to update
        organization_id: ID of the new organization, or None to remove from organization
        
    Returns:
        Updated user
        
    Raises:
        ValueError: If organization change fails
    """
    try:
        # Check if organization exists if provided
        if organization_id:
            result = await db.execute(
                select(Organization).where(Organization.id == organization_id)
            )
            organization = result.scalars().first()
            
            if not organization:
                raise ValueError(f"Organization not found: {organization_id}")
        
        # Update user
        user.organization_id = organization_id
        
        # Save to database
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"Organization changed for user: {user.email}")
        return user
    except ValueError as e:
        # Re-raise ValueError for specific error messages
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to change user organization: {e}")
        raise ValueError(f"Failed to change user organization: {e}")


async def get_inactive_users(
    db: AsyncSession,
    days_inactive: int,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[User], int]:
    """
    Get users who haven't logged in for a specified number of days.
    
    Args:
        db: Database session
        days_inactive: Number of days of inactivity
        skip: Number of users to skip (for pagination)
        limit: Maximum number of users to return
        
    Returns:
        Tuple of (list of inactive users, total count)
    """
    # Calculate cutoff date
    cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)
    
    # Build query conditions
    conditions = [
        or_(
            User.last_login_at < cutoff_date,
            User.last_login_at.is_(None)
        ),
        User.is_active == True,
    ]
    
    # Get total count
    count_query = select(func.count()).select_from(User).where(and_(*conditions))
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Get inactive users with pagination
    query = (
        select(User)
        .where(and_(*conditions))
        .options(
            selectinload(User.roles),
            selectinload(User.organization)
        )
        .order_by(User.email)
        .offset(skip)
        .limit(limit)
    )
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return users, total


async def get_recently_active_users(
    db: AsyncSession,
    days: int,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[User], int]:
    """
    Get users who have logged in within a specified number of days.
    
    Args:
        db: Database session
        days: Number of days to look back
        skip: Number of users to skip (for pagination)
        limit: Maximum number of users to return
        
    Returns:
        Tuple of (list of active users, total count)
    """
    # Calculate cutoff date
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Build query conditions
    conditions = [
        User.last_login_at >= cutoff_date,
        User.is_active == True,
    ]
    
    # Get total count
    count_query = select(func.count()).select_from(User).where(and_(*conditions))
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Get active users with pagination
    query = (
        select(User)
        .where(and_(*conditions))
        .options(
            selectinload(User.roles),
            selectinload(User.organization)
        )
        .order_by(desc(User.last_login_at))
        .offset(skip)
        .limit(limit)
    )
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return users, total


async def get_user_stats(db: AsyncSession) -> Dict[str, Any]:
    """
    Get statistics about users in the system.
    
    Args:
        db: Database session
        
    Returns:
        Dictionary of user statistics
    """
    # Total users
    result = await db.execute(select(func.count()).select_from(User))
    total_users = result.scalar()
    
    # Active users
    result = await db.execute(
        select(func.count()).select_from(User).where(User.is_active == True)
    )
    active_users = result.scalar()
    
    # Verified users
    result = await db.execute(
        select(func.count()).select_from(User).where(User.is_verified == True)
    )
    verified_users = result.scalar()
    
    # Users by authentication provider
    result = await db.execute(
        select(User.auth_provider, func.count())
        .group_by(User.auth_provider)
    )
    auth_providers = {provider: count for provider, count in result.all()}
    
    # Users by organization
    result = await db.execute(
        select(User.organization_id, func.count())
        .group_by(User.organization_id)
    )
    organizations = {str(org_id) if org_id else "none": count for org_id, count in result.all()}
    
    # Recently created users (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    result = await db.execute(
        select(func.count())
        .select_from(User)
        .where(User.created_at >= thirty_days_ago)
    )
    recent_users = result.scalar()
    
    # Return statistics
    return {
        "total_users": total_users,
        "active_users": active_users,
        "verified_users": verified_users,
        "auth_providers": auth_providers,
        "organizations": organizations,
        "recent_users": recent_users,
    }
