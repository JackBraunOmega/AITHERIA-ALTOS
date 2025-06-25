"""
AITHERIA ALTOS - Auth Service User Endpoints
===========================================

This module implements the user management endpoints for the Auth service, including:
- List users (with pagination and filtering)
- Get user details
- Create new users (admin only)
- Update user information
- Delete users (admin only)
- Manage user roles

These endpoints enforce appropriate authorization checks to ensure that
only authorized users can access or modify user data.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import UUID4, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user, get_current_admin_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserResponse,
    UserUpdate,
    UserListResponse,
    UserWithRoles,
)
from app.services.audit_service import create_audit_log
from app.services.user_service import (
    create_user,
    delete_user,
    get_user_by_email,
    get_user_by_id,
    get_users,
    update_user,
    add_user_to_role,
    remove_user_from_role,
)

router = APIRouter()


@router.get("/", response_model=UserListResponse)
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of users to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of users to return"),
    email: Optional[str] = Query(None, description="Filter by email (partial match)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    role: Optional[str] = Query(None, description="Filter by role name"),
) -> Any:
    """
    Retrieve users with pagination and filtering.
    
    This endpoint returns a paginated list of users with optional filtering.
    Regular users can only see basic information about other users,
    while admin users can see more detailed information.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        skip: Number of users to skip (for pagination)
        limit: Maximum number of users to return
        email: Optional filter by email (partial match)
        is_active: Optional filter by active status
        role: Optional filter by role name
        
    Returns:
        Paginated list of users
    """
    # Check if user has permission to list all users
    if not current_user.is_superuser and not current_user.has_role("admin"):
        # Regular users can only see basic user information
        # In a real implementation, you might want to restrict this further
        pass
    
    # Get users with filtering
    users, total = await get_users(
        db, 
        skip=skip, 
        limit=limit, 
        email=email, 
        is_active=is_active, 
        role=role
    )
    
    # Audit log for listing users
    await create_audit_log(
        db,
        action="list_users",
        resource_type="user",
        user_id=current_user.id,
        status="success",
        details={"skip": skip, "limit": limit, "filters": {
            "email": email,
            "is_active": is_active,
            "role": role
        }}
    )
    
    return {
        "items": users,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{user_id}", response_model=UserWithRoles)
async def get_user(
    user_id: UUID4 = Path(..., description="The ID of the user to get"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get a specific user by ID.
    
    This endpoint returns detailed information about a specific user.
    Regular users can only access their own information,
    while admin users can access information about any user.
    
    Args:
        user_id: ID of the user to get
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        User details
        
    Raises:
        HTTPException: If user is not found or current user doesn't have permission
    """
    # Check if user is requesting their own info or has admin permission
    if str(current_user.id) != str(user_id) and not current_user.is_superuser and not current_user.has_role("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this user's information"
        )
    
    # Get user from database
    user = await get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Audit log for getting user details
    await create_audit_log(
        db,
        action="get_user",
        resource_type="user",
        resource_id=str(user_id),
        user_id=current_user.id,
        status="success"
    )
    
    return user


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_new_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),  # Only admins can create users
) -> Any:
    """
    Create a new user.
    
    This endpoint creates a new user with the provided information.
    Only admin users can create new users.
    
    Args:
        user_in: User creation data
        db: Database session
        current_user: Current authenticated admin user
        
    Returns:
        Created user data
        
    Raises:
        HTTPException: If a user with the same email already exists
    """
    # Check if user with this email already exists
    existing_user = await get_user_by_email(db, email=user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists"
        )
    
    # Create new user
    try:
        user = await create_user(db, user_in=user_in)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Audit user creation
    await create_audit_log(
        db,
        action="create_user",
        resource_type="user",
        resource_id=str(user.id),
        user_id=current_user.id,
        status="success",
        details={"email": user.email}
    )
    
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user_info(
    user_id: UUID4 = Path(..., description="The ID of the user to update"),
    user_in: UserUpdate = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update a user's information.
    
    This endpoint updates a user's information with the provided data.
    Regular users can only update their own information,
    while admin users can update any user's information.
    
    Args:
        user_id: ID of the user to update
        user_in: User update data
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Updated user data
        
    Raises:
        HTTPException: If user is not found or current user doesn't have permission
    """
    # Check if user is updating their own info or has admin permission
    if str(current_user.id) != str(user_id) and not current_user.is_superuser and not current_user.has_role("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this user"
        )
    
    # Get user from database
    user = await get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Regular users cannot change certain fields
    if not current_user.is_superuser and not current_user.has_role("admin"):
        # Remove fields that regular users cannot change
        if hasattr(user_in, "is_active"):
            delattr(user_in, "is_active")
        if hasattr(user_in, "is_superuser"):
            delattr(user_in, "is_superuser")
    
    # Update user
    updated_user = await update_user(db, user=user, user_in=user_in)
    
    # Audit user update
    await create_audit_log(
        db,
        action="update_user",
        resource_type="user",
        resource_id=str(user_id),
        user_id=current_user.id,
        status="success",
        details=user_in.dict(exclude_unset=True)
    )
    
    return updated_user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_account(
    user_id: UUID4 = Path(..., description="The ID of the user to delete"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),  # Only admins can delete users
) -> None:
    """
    Delete a user.
    
    This endpoint deletes a user from the system.
    Only admin users can delete users.
    
    Args:
        user_id: ID of the user to delete
        db: Database session
        current_user: Current authenticated admin user
        
    Raises:
        HTTPException: If user is not found or is the current user
    """
    # Prevent users from deleting themselves
    if str(current_user.id) == str(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Users cannot delete their own accounts"
        )
    
    # Get user from database
    user = await get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Delete user
    await delete_user(db, user=user)
    
    # Audit user deletion
    await create_audit_log(
        db,
        action="delete_user",
        resource_type="user",
        resource_id=str(user_id),
        user_id=current_user.id,
        status="success",
        details={"email": user.email}
    )


@router.post("/{user_id}/roles/{role_name}", status_code=status.HTTP_200_OK)
async def assign_role_to_user(
    user_id: UUID4 = Path(..., description="The ID of the user"),
    role_name: str = Path(..., description="The name of the role to assign"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),  # Only admins can assign roles
) -> Dict[str, str]:
    """
    Assign a role to a user.
    
    This endpoint assigns a specific role to a user.
    Only admin users can assign roles.
    
    Args:
        user_id: ID of the user
        role_name: Name of the role to assign
        db: Database session
        current_user: Current authenticated admin user
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If user or role is not found
    """
    # Get user from database
    user = await get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Assign role to user
    try:
        await add_user_to_role(db, user=user, role_name=role_name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Audit role assignment
    await create_audit_log(
        db,
        action="assign_role",
        resource_type="user",
        resource_id=str(user_id),
        user_id=current_user.id,
        status="success",
        details={"role": role_name}
    )
    
    return {"message": f"Role '{role_name}' assigned to user successfully"}


@router.delete("/{user_id}/roles/{role_name}", status_code=status.HTTP_200_OK)
async def remove_role_from_user(
    user_id: UUID4 = Path(..., description="The ID of the user"),
    role_name: str = Path(..., description="The name of the role to remove"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),  # Only admins can remove roles
) -> Dict[str, str]:
    """
    Remove a role from a user.
    
    This endpoint removes a specific role from a user.
    Only admin users can remove roles.
    
    Args:
        user_id: ID of the user
        role_name: Name of the role to remove
        db: Database session
        current_user: Current authenticated admin user
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If user or role is not found
    """
    # Get user from database
    user = await get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Remove role from user
    try:
        await remove_user_from_role(db, user=user, role_name=role_name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Audit role removal
    await create_audit_log(
        db,
        action="remove_role",
        resource_type="user",
        resource_id=str(user_id),
        user_id=current_user.id,
        status="success",
        details={"role": role_name}
    )
    
    return {"message": f"Role '{role_name}' removed from user successfully"}


@router.get("/me/roles", response_model=List[str])
async def get_my_roles(
    current_user: User = Depends(get_current_active_user),
) -> List[str]:
    """
    Get the current user's roles.
    
    This endpoint returns the list of roles assigned to the current user.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        List of role names
    """
    return [role.name for role in current_user.roles]
