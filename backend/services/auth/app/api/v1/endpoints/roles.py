"""
AITHERIA ALTOS - Auth Service Role Endpoints
===========================================

This module implements the role management endpoints for the Auth service, including:
- List roles (with pagination and filtering)
- Get role details
- Create new roles (admin only)
- Update role information (admin only)
- Delete roles (admin only)
- Manage role permissions (admin only)

These endpoints enforce appropriate authorization checks to ensure that
only authorized users (admins) can modify role data.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user, get_current_admin_user
from app.db.session import get_db
from app.models.role import Role
from app.models.user import User
from app.schemas.role import (
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    RoleListResponse,
    RoleWithPermissions,
)
from app.services.audit_service import create_audit_log
from app.services.role_service import (
    create_role,
    delete_role,
    get_role_by_id,
    get_role_by_name,
    get_roles,
    update_role,
    add_permission_to_role,
    remove_permission_from_role,
)

router = APIRouter()


@router.get("/", response_model=RoleListResponse)
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of roles to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of roles to return"),
    name: Optional[str] = Query(None, description="Filter by role name (partial match)"),
    is_system: Optional[bool] = Query(None, description="Filter by system role status"),
) -> Any:
    """
    Retrieve roles with pagination and filtering.
    
    This endpoint returns a paginated list of roles with optional filtering.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        skip: Number of roles to skip (for pagination)
        limit: Maximum number of roles to return
        name: Optional filter by role name (partial match)
        is_system: Optional filter by system role status
        
    Returns:
        Paginated list of roles
    """
    # Get roles with filtering
    roles, total = await get_roles(
        db, 
        skip=skip, 
        limit=limit, 
        name=name, 
        is_system=is_system
    )
    
    # Audit log for listing roles
    await create_audit_log(
        db,
        action="list_roles",
        resource_type="role",
        user_id=current_user.id,
        status="success",
        details={"skip": skip, "limit": limit, "filters": {
            "name": name,
            "is_system": is_system
        }}
    )
    
    return {
        "items": roles,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{role_id}", response_model=RoleWithPermissions)
async def get_role(
    role_id: UUID4 = Path(..., description="The ID of the role to get"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get a specific role by ID.
    
    This endpoint returns detailed information about a specific role,
    including its permissions.
    
    Args:
        role_id: ID of the role to get
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Role details with permissions
        
    Raises:
        HTTPException: If role is not found
    """
    # Get role from database
    role = await get_role_by_id(db, role_id=role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Audit log for getting role details
    await create_audit_log(
        db,
        action="get_role",
        resource_type="role",
        resource_id=str(role_id),
        user_id=current_user.id,
        status="success"
    )
    
    return role


@router.post("/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_new_role(
    role_in: RoleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),  # Only admins can create roles
) -> Any:
    """
    Create a new role.
    
    This endpoint creates a new role with the provided information.
    Only admin users can create new roles.
    
    Args:
        role_in: Role creation data
        db: Database session
        current_user: Current authenticated admin user
        
    Returns:
        Created role data
        
    Raises:
        HTTPException: If a role with the same name already exists
    """
    # Check if role with this name already exists
    existing_role = await get_role_by_name(db, name=role_in.name)
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A role with this name already exists"
        )
    
    # Create new role
    try:
        role = await create_role(db, role_in=role_in)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Audit role creation
    await create_audit_log(
        db,
        action="create_role",
        resource_type="role",
        resource_id=str(role.id),
        user_id=current_user.id,
        status="success",
        details={"name": role.name}
    )
    
    return role


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role_info(
    role_id: UUID4 = Path(..., description="The ID of the role to update"),
    role_in: RoleUpdate = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),  # Only admins can update roles
) -> Any:
    """
    Update a role's information.
    
    This endpoint updates a role's information with the provided data.
    Only admin users can update roles.
    
    Args:
        role_id: ID of the role to update
        role_in: Role update data
        db: Database session
        current_user: Current authenticated admin user
        
    Returns:
        Updated role data
        
    Raises:
        HTTPException: If role is not found or is a system role
    """
    # Get role from database
    role = await get_role_by_id(db, role_id=role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Prevent modification of system roles
    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System roles cannot be modified"
        )
    
    # If name is being changed, check for conflicts
    if role_in.name and role_in.name != role.name:
        existing_role = await get_role_by_name(db, name=role_in.name)
        if existing_role:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A role with this name already exists"
            )
    
    # Update role
    updated_role = await update_role(db, role=role, role_in=role_in)
    
    # Audit role update
    await create_audit_log(
        db,
        action="update_role",
        resource_type="role",
        resource_id=str(role_id),
        user_id=current_user.id,
        status="success",
        details=role_in.dict(exclude_unset=True)
    )
    
    return updated_role


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role_record(
    role_id: UUID4 = Path(..., description="The ID of the role to delete"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),  # Only admins can delete roles
) -> None:
    """
    Delete a role.
    
    This endpoint deletes a role from the system.
    Only admin users can delete roles.
    
    Args:
        role_id: ID of the role to delete
        db: Database session
        current_user: Current authenticated admin user
        
    Raises:
        HTTPException: If role is not found or is a system role
    """
    # Get role from database
    role = await get_role_by_id(db, role_id=role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Prevent deletion of system roles
    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System roles cannot be deleted"
        )
    
    # Delete role
    await delete_role(db, role=role)
    
    # Audit role deletion
    await create_audit_log(
        db,
        action="delete_role",
        resource_type="role",
        resource_id=str(role_id),
        user_id=current_user.id,
        status="success",
        details={"name": role.name}
    )


@router.post("/{role_id}/permissions/{permission_name}", status_code=status.HTTP_200_OK)
async def assign_permission_to_role(
    role_id: UUID4 = Path(..., description="The ID of the role"),
    permission_name: str = Path(..., description="The name of the permission to assign"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),  # Only admins can assign permissions
) -> Dict[str, str]:
    """
    Assign a permission to a role.
    
    This endpoint assigns a specific permission to a role.
    Only admin users can assign permissions.
    
    Args:
        role_id: ID of the role
        permission_name: Name of the permission to assign
        db: Database session
        current_user: Current authenticated admin user
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If role or permission is not found, or role is a system role
    """
    # Get role from database
    role = await get_role_by_id(db, role_id=role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Prevent modification of system roles
    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System roles cannot be modified"
        )
    
    # Assign permission to role
    try:
        await add_permission_to_role(db, role=role, permission_name=permission_name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Audit permission assignment
    await create_audit_log(
        db,
        action="assign_permission",
        resource_type="role",
        resource_id=str(role_id),
        user_id=current_user.id,
        status="success",
        details={"permission": permission_name}
    )
    
    return {"message": f"Permission '{permission_name}' assigned to role successfully"}


@router.delete("/{role_id}/permissions/{permission_name}", status_code=status.HTTP_200_OK)
async def remove_permission_from_role_endpoint(
    role_id: UUID4 = Path(..., description="The ID of the role"),
    permission_name: str = Path(..., description="The name of the permission to remove"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),  # Only admins can remove permissions
) -> Dict[str, str]:
    """
    Remove a permission from a role.
    
    This endpoint removes a specific permission from a role.
    Only admin users can remove permissions.
    
    Args:
        role_id: ID of the role
        permission_name: Name of the permission to remove
        db: Database session
        current_user: Current authenticated admin user
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If role or permission is not found, or role is a system role
    """
    # Get role from database
    role = await get_role_by_id(db, role_id=role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Prevent modification of system roles
    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System roles cannot be modified"
        )
    
    # Remove permission from role
    try:
        await remove_permission_from_role(db, role=role, permission_name=permission_name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Audit permission removal
    await create_audit_log(
        db,
        action="remove_permission",
        resource_type="role",
        resource_id=str(role_id),
        user_id=current_user.id,
        status="success",
        details={"permission": permission_name}
    )
    
    return {"message": f"Permission '{permission_name}' removed from role successfully"}


@router.get("/{role_id}/permissions", response_model=List[str])
async def get_role_permissions(
    role_id: UUID4 = Path(..., description="The ID of the role"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[str]:
    """
    Get a role's permissions.
    
    This endpoint returns the list of permissions assigned to a role.
    
    Args:
        role_id: ID of the role
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of permission names
        
    Raises:
        HTTPException: If role is not found
    """
    # Get role from database
    role = await get_role_by_id(db, role_id=role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Audit role permissions retrieval
    await create_audit_log(
        db,
        action="get_role_permissions",
        resource_type="role",
        resource_id=str(role_id),
        user_id=current_user.id,
        status="success"
    )
    
    return [permission.name for permission in role.permissions]
