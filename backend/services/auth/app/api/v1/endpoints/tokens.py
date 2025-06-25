"""
AITHERIA ALTOS - Auth Service API Token Endpoints
================================================

This module implements the API token management endpoints for the Auth service, including:
- List API tokens (with pagination and filtering)
- Get API token details
- Create new API tokens
- Revoke (delete) API tokens

API tokens allow users to authenticate with the API programmatically without
using their username and password. They are useful for integrations, scripts,
and automated workflows.

These endpoints enforce appropriate authorization checks to ensure that
users can only manage their own tokens, while admins can manage any user's tokens.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_current_active_user, get_current_admin_user
from app.db.session import get_db
from app.models.api_token import APIToken
from app.models.user import User
from app.schemas.token import (
    APITokenCreate,
    APITokenResponse,
    APITokenListResponse,
)
from app.services.audit_service import create_audit_log
from app.services.token_service import (
    create_api_token,
    delete_api_token,
    get_api_token_by_id,
    get_user_api_tokens,
    get_all_api_tokens,
)

router = APIRouter()


@router.get("/", response_model=APITokenListResponse)
async def list_api_tokens(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of tokens to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of tokens to return"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    user_id: Optional[UUID4] = Query(None, description="Filter by user ID (admin only)"),
) -> Any:
    """
    Retrieve API tokens with pagination and filtering.
    
    This endpoint returns a paginated list of API tokens with optional filtering.
    Regular users can only see their own tokens, while admin users can see all tokens
    or filter by user ID.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        skip: Number of tokens to skip (for pagination)
        limit: Maximum number of tokens to return
        is_active: Optional filter by active status
        user_id: Optional filter by user ID (admin only)
        
    Returns:
        Paginated list of API tokens
    """
    # Check if user is requesting tokens for another user
    if user_id and user_id != current_user.id:
        # Only admins can view other users' tokens
        if not current_user.is_superuser and not current_user.has_role("admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to access other users' tokens"
            )
        
        # Get tokens for the specified user
        tokens, total = await get_user_api_tokens(
            db, 
            user_id=user_id, 
            skip=skip, 
            limit=limit, 
            is_active=is_active
        )
    elif current_user.is_superuser or current_user.has_role("admin"):
        # Admins can view all tokens if no user_id is specified
        if user_id is None:
            tokens, total = await get_all_api_tokens(
                db, 
                skip=skip, 
                limit=limit, 
                is_active=is_active
            )
        else:
            # Get admin's own tokens if user_id matches their ID
            tokens, total = await get_user_api_tokens(
                db, 
                user_id=current_user.id, 
                skip=skip, 
                limit=limit, 
                is_active=is_active
            )
    else:
        # Regular users can only view their own tokens
        tokens, total = await get_user_api_tokens(
            db, 
            user_id=current_user.id, 
            skip=skip, 
            limit=limit, 
            is_active=is_active
        )
    
    # Audit log for listing API tokens
    await create_audit_log(
        db,
        action="list_api_tokens",
        resource_type="api_token",
        user_id=current_user.id,
        status="success",
        details={
            "skip": skip, 
            "limit": limit, 
            "filters": {
                "is_active": is_active,
                "user_id": str(user_id) if user_id else None
            }
        }
    )
    
    return {
        "items": tokens,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{token_id}", response_model=APITokenResponse)
async def get_api_token(
    token_id: UUID4 = Path(..., description="The ID of the API token to get"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get a specific API token by ID.
    
    This endpoint returns detailed information about a specific API token.
    Users can only access their own tokens, while admin users can access any token.
    
    Args:
        token_id: ID of the API token to get
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        API token details
        
    Raises:
        HTTPException: If token is not found or user doesn't have permission
    """
    # Get token from database
    token = await get_api_token_by_id(db, token_id=token_id)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API token not found"
        )
    
    # Check if user has permission to view this token
    if token.user_id != current_user.id and not current_user.is_superuser and not current_user.has_role("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this token"
        )
    
    # Audit log for getting token details
    await create_audit_log(
        db,
        action="get_api_token",
        resource_type="api_token",
        resource_id=str(token_id),
        user_id=current_user.id,
        status="success"
    )
    
    return token


@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_new_api_token(
    token_in: APITokenCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create a new API token.
    
    This endpoint creates a new API token with the provided information.
    Users can only create tokens for themselves, while admin users can create tokens for any user.
    
    Args:
        token_in: API token creation data
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Created API token data with the raw token value (shown only once)
        
    Raises:
        HTTPException: If user doesn't have permission to create a token for another user
    """
    # Check if user is creating a token for another user
    target_user_id = token_in.user_id if token_in.user_id else current_user.id
    
    if target_user_id != current_user.id:
        # Only admins can create tokens for other users
        if not current_user.is_superuser and not current_user.has_role("admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to create tokens for other users"
            )
    
    # Set default expiration if not provided
    if not token_in.expires_at and settings.API_TOKEN_DEFAULT_EXPIRY_DAYS > 0:
        token_in.expires_at = datetime.utcnow() + timedelta(days=settings.API_TOKEN_DEFAULT_EXPIRY_DAYS)
    
    # Create new API token
    try:
        token, raw_token = await create_api_token(
            db, 
            token_in=token_in, 
            user_id=target_user_id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Audit token creation
    await create_audit_log(
        db,
        action="create_api_token",
        resource_type="api_token",
        resource_id=str(token.id),
        user_id=current_user.id,
        status="success",
        details={
            "name": token.name,
            "for_user_id": str(target_user_id),
            "expires_at": token.expires_at.isoformat() if token.expires_at else None
        }
    )
    
    # Return token details with the raw token value
    # This is the only time the raw token will be shown
    return {
        "token": token,
        "raw_token": raw_token,
        "message": "Store this token securely. It will not be shown again."
    }


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_token(
    token_id: UUID4 = Path(..., description="The ID of the API token to revoke"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """
    Revoke (delete) an API token.
    
    This endpoint revokes a specific API token, making it unusable for authentication.
    Users can only revoke their own tokens, while admin users can revoke any token.
    
    Args:
        token_id: ID of the API token to revoke
        db: Database session
        current_user: Current authenticated user
        
    Raises:
        HTTPException: If token is not found or user doesn't have permission
    """
    # Get token from database
    token = await get_api_token_by_id(db, token_id=token_id)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API token not found"
        )
    
    # Check if user has permission to revoke this token
    if token.user_id != current_user.id and not current_user.is_superuser and not current_user.has_role("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to revoke this token"
        )
    
    # Delete token
    await delete_api_token(db, token=token)
    
    # Audit token revocation
    await create_audit_log(
        db,
        action="revoke_api_token",
        resource_type="api_token",
        resource_id=str(token_id),
        user_id=current_user.id,
        status="success",
        details={"name": token.name}
    )


@router.post("/{token_id}/deactivate", response_model=APITokenResponse)
async def deactivate_api_token(
    token_id: UUID4 = Path(..., description="The ID of the API token to deactivate"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Deactivate an API token.
    
    This endpoint deactivates a specific API token without deleting it.
    Deactivated tokens cannot be used for authentication but can be reactivated later.
    Users can only deactivate their own tokens, while admin users can deactivate any token.
    
    Args:
        token_id: ID of the API token to deactivate
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Updated API token data
        
    Raises:
        HTTPException: If token is not found or user doesn't have permission
    """
    # Get token from database
    token = await get_api_token_by_id(db, token_id=token_id)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API token not found"
        )
    
    # Check if user has permission to deactivate this token
    if token.user_id != current_user.id and not current_user.is_superuser and not current_user.has_role("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to deactivate this token"
        )
    
    # Check if token is already inactive
    if not token.is_active:
        return token
    
    # Deactivate token
    token.is_active = False
    db.add(token)
    await db.commit()
    await db.refresh(token)
    
    # Audit token deactivation
    await create_audit_log(
        db,
        action="deactivate_api_token",
        resource_type="api_token",
        resource_id=str(token_id),
        user_id=current_user.id,
        status="success",
        details={"name": token.name}
    )
    
    return token


@router.post("/{token_id}/activate", response_model=APITokenResponse)
async def activate_api_token(
    token_id: UUID4 = Path(..., description="The ID of the API token to activate"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Activate an API token.
    
    This endpoint activates a specific API token that was previously deactivated.
    Users can only activate their own tokens, while admin users can activate any token.
    
    Args:
        token_id: ID of the API token to activate
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Updated API token data
        
    Raises:
        HTTPException: If token is not found or user doesn't have permission
    """
    # Get token from database
    token = await get_api_token_by_id(db, token_id=token_id)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API token not found"
        )
    
    # Check if user has permission to activate this token
    if token.user_id != current_user.id and not current_user.is_superuser and not current_user.has_role("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to activate this token"
        )
    
    # Check if token is already active
    if token.is_active:
        return token
    
    # Check if token is expired
    if token.is_expired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot activate an expired token"
        )
    
    # Activate token
    token.is_active = True
    db.add(token)
    await db.commit()
    await db.refresh(token)
    
    # Audit token activation
    await create_audit_log(
        db,
        action="activate_api_token",
        resource_type="api_token",
        resource_id=str(token_id),
        user_id=current_user.id,
        status="success",
        details={"name": token.name}
    )
    
    return token
