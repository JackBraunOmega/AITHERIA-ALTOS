"""
AITHERIA ALTOS - Auth Service Organization Endpoints
===================================================

This module implements the organization management endpoints for the Auth service, including:
- List organizations (with pagination and filtering)
- Get organization details
- Create new organizations (admin only)
- Update organization information (admin only)
- Delete organizations (admin only)
- Manage organization users (add/remove users)

These endpoints enforce appropriate authorization checks to ensure that
only authorized users (admins) can modify organization data.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import UUID4, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user, get_current_admin_user
from app.db.session import get_db
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
    OrganizationListResponse,
    OrganizationWithUsers,
)
from app.services.audit_service import create_audit_log
from app.services.organization_service import (
    create_organization,
    delete_organization,
    get_organization_by_id,
    get_organization_by_name,
    get_organizations,
    update_organization,
    add_user_to_organization,
    remove_user_from_organization,
)
from app.services.user_service import get_user_by_email, get_user_by_id

router = APIRouter()


@router.get("/", response_model=OrganizationListResponse)
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of organizations to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of organizations to return"),
    name: Optional[str] = Query(None, description="Filter by organization name (partial match)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_system: Optional[bool] = Query(None, description="Filter by system organization status"),
) -> Any:
    """
    Retrieve organizations with pagination and filtering.
    
    This endpoint returns a paginated list of organizations with optional filtering.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        skip: Number of organizations to skip (for pagination)
        limit: Maximum number of organizations to return
        name: Optional filter by organization name (partial match)
        is_active: Optional filter by active status
        is_system: Optional filter by system organization status
        
    Returns:
        Paginated list of organizations
    """
    # Get organizations with filtering
    organizations, total = await get_organizations(
        db, 
        skip=skip, 
        limit=limit, 
        name=name, 
        is_active=is_active,
        is_system=is_system
    )
    
    # Audit log for listing organizations
    await create_audit_log(
        db,
        action="list_organizations",
        resource_type="organization",
        user_id=current_user.id,
        status="success",
        details={"skip": skip, "limit": limit, "filters": {
            "name": name,
            "is_active": is_active,
            "is_system": is_system
        }}
    )
    
    return {
        "items": organizations,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{organization_id}", response_model=OrganizationWithUsers)
async def get_organization(
    organization_id: UUID4 = Path(..., description="The ID of the organization to get"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get a specific organization by ID.
    
    This endpoint returns detailed information about a specific organization,
    including its users.
    
    Args:
        organization_id: ID of the organization to get
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Organization details with users
        
    Raises:
        HTTPException: If organization is not found
    """
    # Get organization from database
    organization = await get_organization_by_id(db, organization_id=organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Check if user has permission to view this organization
    # Regular users can only view their own organization
    if not current_user.is_superuser and not current_user.has_role("admin"):
        if current_user.organization_id != organization.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to access this organization"
            )
    
    # Audit log for getting organization details
    await create_audit_log(
        db,
        action="get_organization",
        resource_type="organization",
        resource_id=str(organization_id),
        user_id=current_user.id,
        status="success"
    )
    
    return organization


@router.post("/", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_new_organization(
    organization_in: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),  # Only admins can create organizations
) -> Any:
    """
    Create a new organization.
    
    This endpoint creates a new organization with the provided information.
    Only admin users can create new organizations.
    
    Args:
        organization_in: Organization creation data
        db: Database session
        current_user: Current authenticated admin user
        
    Returns:
        Created organization data
        
    Raises:
        HTTPException: If an organization with the same name already exists
    """
    # Check if organization with this name already exists
    existing_organization = await get_organization_by_name(db, name=organization_in.name)
    if existing_organization:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organization with this name already exists"
        )
    
    # Create new organization
    try:
        organization = await create_organization(db, organization_in=organization_in)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Audit organization creation
    await create_audit_log(
        db,
        action="create_organization",
        resource_type="organization",
        resource_id=str(organization.id),
        user_id=current_user.id,
        status="success",
        details={"name": organization.name}
    )
    
    return organization


@router.put("/{organization_id}", response_model=OrganizationResponse)
async def update_organization_info(
    organization_id: UUID4 = Path(..., description="The ID of the organization to update"),
    organization_in: OrganizationUpdate = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),  # Only admins can update organizations
) -> Any:
    """
    Update an organization's information.
    
    This endpoint updates an organization's information with the provided data.
    Only admin users can update organizations.
    
    Args:
        organization_id: ID of the organization to update
        organization_in: Organization update data
        db: Database session
        current_user: Current authenticated admin user
        
    Returns:
        Updated organization data
        
    Raises:
        HTTPException: If organization is not found or is a system organization
    """
    # Get organization from database
    organization = await get_organization_by_id(db, organization_id=organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Prevent modification of system organizations
    if organization.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System organizations cannot be modified"
        )
    
    # If name is being changed, check for conflicts
    if organization_in.name and organization_in.name != organization.name:
        existing_organization = await get_organization_by_name(db, name=organization_in.name)
        if existing_organization:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An organization with this name already exists"
            )
    
    # Update organization
    updated_organization = await update_organization(db, organization=organization, organization_in=organization_in)
    
    # Audit organization update
    await create_audit_log(
        db,
        action="update_organization",
        resource_type="organization",
        resource_id=str(organization_id),
        user_id=current_user.id,
        status="success",
        details=organization_in.dict(exclude_unset=True)
    )
    
    return updated_organization


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization_record(
    organization_id: UUID4 = Path(..., description="The ID of the organization to delete"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),  # Only admins can delete organizations
) -> None:
    """
    Delete an organization.
    
    This endpoint deletes an organization from the system.
    Only admin users can delete organizations.
    
    Args:
        organization_id: ID of the organization to delete
        db: Database session
        current_user: Current authenticated admin user
        
    Raises:
        HTTPException: If organization is not found, is a system organization, or still has users
    """
    # Get organization from database
    organization = await get_organization_by_id(db, organization_id=organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Prevent deletion of system organizations
    if organization.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System organizations cannot be deleted"
        )
    
    # Check if organization has users
    if organization.users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete organization that still has users. Remove all users first."
        )
    
    # Delete organization
    await delete_organization(db, organization=organization)
    
    # Audit organization deletion
    await create_audit_log(
        db,
        action="delete_organization",
        resource_type="organization",
        resource_id=str(organization_id),
        user_id=current_user.id,
        status="success",
        details={"name": organization.name}
    )


@router.post("/{organization_id}/users", status_code=status.HTTP_200_OK)
async def add_user_to_organization_endpoint(
    organization_id: UUID4 = Path(..., description="The ID of the organization"),
    user_email: EmailStr = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),  # Only admins can add users to organizations
) -> Dict[str, str]:
    """
    Add a user to an organization.
    
    This endpoint adds a user to a specific organization.
    Only admin users can add users to organizations.
    
    Args:
        organization_id: ID of the organization
        user_email: Email of the user to add
        db: Database session
        current_user: Current authenticated admin user
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If organization or user is not found
    """
    # Get organization from database
    organization = await get_organization_by_id(db, organization_id=organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Get user from database
    user = await get_user_by_email(db, email=user_email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Add user to organization
    try:
        await add_user_to_organization(db, user=user, organization=organization)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Audit user addition to organization
    await create_audit_log(
        db,
        action="add_user_to_organization",
        resource_type="organization",
        resource_id=str(organization_id),
        user_id=current_user.id,
        status="success",
        details={"user_email": user_email}
    )
    
    return {"message": f"User {user_email} added to organization successfully"}


@router.delete("/{organization_id}/users/{user_id}", status_code=status.HTTP_200_OK)
async def remove_user_from_organization_endpoint(
    organization_id: UUID4 = Path(..., description="The ID of the organization"),
    user_id: UUID4 = Path(..., description="The ID of the user to remove"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),  # Only admins can remove users from organizations
) -> Dict[str, str]:
    """
    Remove a user from an organization.
    
    This endpoint removes a user from a specific organization.
    Only admin users can remove users from organizations.
    
    Args:
        organization_id: ID of the organization
        user_id: ID of the user to remove
        db: Database session
        current_user: Current authenticated admin user
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If organization or user is not found
    """
    # Get organization from database
    organization = await get_organization_by_id(db, organization_id=organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Get user from database
    user = await get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if user is in the organization
    if user.organization_id != organization.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a member of this organization"
        )
    
    # Remove user from organization
    try:
        await remove_user_from_organization(db, user=user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Audit user removal from organization
    await create_audit_log(
        db,
        action="remove_user_from_organization",
        resource_type="organization",
        resource_id=str(organization_id),
        user_id=current_user.id,
        status="success",
        details={"user_id": str(user_id)}
    )
    
    return {"message": f"User removed from organization successfully"}


@router.get("/{organization_id}/users", response_model=List[UUID4])
async def get_organization_users(
    organization_id: UUID4 = Path(..., description="The ID of the organization"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[UUID4]:
    """
    Get users in an organization.
    
    This endpoint returns the list of user IDs in an organization.
    
    Args:
        organization_id: ID of the organization
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of user IDs
        
    Raises:
        HTTPException: If organization is not found
    """
    # Get organization from database
    organization = await get_organization_by_id(db, organization_id=organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Check if user has permission to view this organization's users
    # Regular users can only view their own organization's users
    if not current_user.is_superuser and not current_user.has_role("admin"):
        if current_user.organization_id != organization.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to access this organization's users"
            )
    
    # Audit organization users retrieval
    await create_audit_log(
        db,
        action="get_organization_users",
        resource_type="organization",
        resource_id=str(organization_id),
        user_id=current_user.id,
        status="success"
    )
    
    return [user.id for user in organization.users]
