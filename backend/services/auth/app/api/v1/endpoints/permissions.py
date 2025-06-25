"""
AITHERIA ALTOS - Auth Service Permission Endpoints
================================================

This module implements the permission management endpoints for the Auth service, including:
- List permissions (with pagination and filtering)
- Get permission details
- Create new permissions (admin only)
- Update permission information (admin only)
- Delete permissions (admin only)

These endpoints enforce appropriate authorization checks to ensure that
only authorized users (admins) can modify permission data.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user, get_current_admin_user
from app.db.session import get_db
from app.models.permission import Permission
from app.models.user import User
from app.schemas.permission import (
    PermissionCreate,
    PermissionResponse,
    PermissionUpdate,
    PermissionListResponse,
)
from app.services.audit_service import create_audit_log
from app.services.permission_service import (
    create_permission,
    delete_permission,
    get_permission_by_id,
    get_permission_by_name,
    get_permissions,
    update_permission,
)

router = APIRouter()


@router.get("/", response_model=PermissionListResponse)
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of permissions to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of permissions to return"),
    name: Optional[str] = Query(None, description="Filter by permission name (partial match)"),
    is_system: Optional[bool] = Query(None, description="Filter by system permission status"),
) -> Any:
    """
    Retrieve permissions with pagination and filtering.
    
    This endpoint returns a paginated list of permissions with optional filtering.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        skip: Number of permissions to skip (for pagination)
        limit: Maximum number of permissions to return
        name: Optional filter by permission name (partial match)
        is_system: Optional filter by system permission status
        
    Returns:
        Paginated list of permissions
    """
    # Get permissions with filtering
    permissions, total = await get_permissions(
        db, 
        skip=skip, 
        limit=limit, 
        name=name, 
        is_system=is_system
    )
    
    # Audit log for listing permissions
    await create_audit_log(
        db,
        action="list_permissions",
        resource_type="permission",
        user_id=current_user.id,
        status="success",
        details={"skip": skip, "limit": limit, "filters": {
            "name": name,
            "is_system": is_system
        }}
    )
    
    return {
        "items": permissions,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{permission_id}", response_model=PermissionResponse)
async def get_permission(
    permission_id: UUID4 = Path(..., description="The ID of the permission to get"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get a specific permission by ID.
    
    This endpoint returns detailed information about a specific permission.
    
    Args:
        permission_id: ID of the permission to get
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Permission details
        
    Raises:
        HTTPException: If permission is not found
    """
    # Get permission from database
    permission = await get_permission_by_id(db, permission_id=permission_id)
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found"
        )
    
    # Audit log for getting permission details
    await create_audit_log(
        db,
        action="get_permission",
        resource_type="permission",
        resource_id=str(permission_id),
        user_id=current_user.id,
        status="success"
    )
    
    return permission


@router.post("/", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
async def create_new_permission(
    permission_in: PermissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),  # Only admins can create permissions
) -> Any:
    """
    Create a new permission.
    
    This endpoint creates a new permission with the provided information.
    Only admin users can create new permissions.
    
    Args:
        permission_in: Permission creation data
        db: Database session
        current_user: Current authenticated admin user
        
    Returns:
        Created permission data
        
    Raises:
        HTTPException: If a permission with the same name already exists
    """
    # Check if permission with this name already exists
    existing_permission = await get_permission_by_name(db, name=permission_in.name)
    if existing_permission:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A permission with this name already exists"
        )
    
    # Create new permission
    try:
        permission = await create_permission(db, permission_in=permission_in)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Audit permission creation
    await create_audit_log(
        db,
        action="create_permission",
        resource_type="permission",
        resource_id=str(permission.id),
        user_id=current_user.id,
        status="success",
        details={"name": permission.name}
    )
    
    return permission


@router.put("/{permission_id}", response_model=PermissionResponse)
async def update_permission_info(
    permission_id: UUID4 = Path(..., description="The ID of the permission to update"),
    permission_in: PermissionUpdate = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),  # Only admins can update permissions
) -> Any:
    """
    Update a permission's information.
    
    This endpoint updates a permission's information with the provided data.
    Only admin users can update permissions.
    
    Args:
        permission_id: ID of the permission to update
        permission_in: Permission update data
        db: Database session
        current_user: Current authenticated admin user
        
    Returns:
        Updated permission data
        
    Raises:
        HTTPException: If permission is not found or is a system permission
    """
    # Get permission from database
    permission = await get_permission_by_id(db, permission_id=permission_id)
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found"
        )
    
    # Prevent modification of system permissions
    if permission.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System permissions cannot be modified"
        )
    
    # If name is being changed, check for conflicts
    if permission_in.name and permission_in.name != permission.name:
        existing_permission = await get_permission_by_name(db, name=permission_in.name)
        if existing_permission:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A permission with this name already exists"
            )
    
    # Update permission
    updated_permission = await update_permission(db, permission=permission, permission_in=permission_in)
    
    # Audit permission update
    await create_audit_log(
        db,
        action="update_permission",
        resource_type="permission",
        resource_id=str(permission_id),
        user_id=current_user.id,
        status="success",
        details=permission_in.dict(exclude_unset=True)
    )
    
    return updated_permission


@router.delete("/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_permission_record(
    permission_id: UUID4 = Path(..., description="The ID of the permission to delete"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),  # Only admins can delete permissions
) -> None:
    """
    Delete a permission.
    
    This endpoint deletes a permission from the system.
    Only admin users can delete permissions.
    
    Args:
        permission_id: ID of the permission to delete
        db: Database session
        current_user: Current authenticated admin user
        
    Raises:
        HTTPException: If permission is not found or is a system permission
    """
    # Get permission from database
    permission = await get_permission_by_id(db, permission_id=permission_id)
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found"
        )
    
    # Prevent deletion of system permissions
    if permission.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System permissions cannot be deleted"
        )
    
    # Delete permission
    await delete_permission(db, permission=permission)
    
    # Audit permission deletion
    await create_audit_log(
        db,
        action="delete_permission",
        resource_type="permission",
        resource_id=str(permission_id),
        user_id=current_user.id,
        status="success",
        details={"name": permission.name}
    )


@router.get("/by-name/{permission_name}", response_model=PermissionResponse)
async def get_permission_by_name_endpoint(
    permission_name: str = Path(..., description="The name of the permission to get"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get a specific permission by name.
    
    This endpoint returns detailed information about a specific permission.
    
    Args:
        permission_name: Name of the permission to get
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Permission details
        
    Raises:
        HTTPException: If permission is not found
    """
    # Get permission from database
    permission = await get_permission_by_name(db, name=permission_name)
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found"
        )
    
    # Audit log for getting permission details
    await create_audit_log(
        db,
        action="get_permission_by_name",
        resource_type="permission",
        resource_id=str(permission.id),
        user_id=current_user.id,
        status="success",
        details={"name": permission_name}
    )
    
    return permission
