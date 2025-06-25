"""
AITHERIA ALTOS - Auth Service Authentication Endpoints
=====================================================

This module implements the authentication endpoints for the Auth service, including:
- Login with email/password
- User registration
- Token refresh
- Logout
- Password change

These endpoints follow OAuth 2.0 standards and use JWT tokens for authentication.
"""

from datetime import timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from loguru import logger
from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_current_active_user,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.token import Token, TokenPayload
from app.schemas.user import UserCreate, UserResponse
from app.services.audit_service import create_audit_log
from app.services.token_service import (
    add_token_to_blocklist,
    is_token_blacklisted,
)
from app.services.user_service import (
    create_user,
    get_user_by_email,
    update_user_last_login,
    update_user_password,
)

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    user_agent: Optional[str] = None,
    client_ip: Optional[str] = None,
) -> Any:
    """
    OAuth2 compatible token login, returns an access token and refresh token.
    
    This endpoint authenticates a user with their email and password,
    and returns JWT tokens for API access.
    
    Args:
        response: FastAPI response object for setting cookies
        form_data: OAuth2 form with username (email) and password
        db: Database session
        user_agent: User agent string from request headers
        client_ip: Client IP address
    
    Returns:
        Token object containing access_token, refresh_token, and token_type
    
    Raises:
        HTTPException: If authentication fails
    """
    # Get user by email (username in OAuth2 form is the email)
    user = await get_user_by_email(db, email=form_data.username)
    
    # Check if user exists and password is correct
    if not user or not verify_password(form_data.password, user.hashed_password):
        # Audit failed login attempt
        if user:
            await create_audit_log(
                db,
                action="login_failed",
                resource_type="user",
                resource_id=str(user.id),
                user_id=user.id,
                ip_address=client_ip,
                user_agent=user_agent,
                status="failure",
                details={"reason": "Invalid password"}
            )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.is_active:
        # Audit login attempt on inactive account
        await create_audit_log(
            db,
            action="login_failed",
            resource_type="user",
            resource_id=str(user.id),
            user_id=user.id,
            ip_address=client_ip,
            user_agent=user_agent,
            status="failure",
            details={"reason": "Inactive account"}
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user account",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if account is locked
    if user.is_locked:
        # Audit login attempt on locked account
        await create_audit_log(
            db,
            action="login_failed",
            resource_type="user",
            resource_id=str(user.id),
            user_id=user.id,
            ip_address=client_ip,
            user_agent=user_agent,
            status="failure",
            details={"reason": "Account locked"}
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is temporarily locked. Please try again later.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Generate token scopes based on user roles
    scopes = ["user"]  # Base scope for all authenticated users
    
    # Add role-based scopes
    for role in user.roles:
        scopes.append(role.name)
    
    # Create access and refresh tokens
    access_token = create_access_token(
        subject=user.email,
        scopes=scopes,
        additional_data={
            "user_id": str(user.id),
            "is_superuser": user.is_superuser,
        }
    )
    
    refresh_token = create_refresh_token(subject=user.email)
    
    # Update user's last login information
    await update_user_last_login(
        db, 
        user=user, 
        ip_address=client_ip
    )
    
    # Audit successful login
    await create_audit_log(
        db,
        action="login_success",
        resource_type="user",
        resource_id=str(user.id),
        user_id=user.id,
        ip_address=client_ip,
        user_agent=user_agent,
        status="success"
    )
    
    # Set refresh token as HTTP-only cookie if configured
    if settings.USE_REFRESH_TOKEN_COOKIE:
        cookie_max_age = int(settings.refresh_token_expires.total_seconds())
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=settings.SESSION_COOKIE_SECURE,
            samesite=settings.SESSION_COOKIE_SAMESITE,
            max_age=cookie_max_age,
            path="/api/v1/auth/refresh"
        )
        
        # Don't include refresh token in response body if using cookie
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
    
    # Return both tokens in response body
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Any:
    """
    Register a new user.
    
    This endpoint creates a new user account with the provided information.
    
    Args:
        user_in: User creation data
        db: Database session
        client_ip: Client IP address
        user_agent: User agent string from request headers
    
    Returns:
        Created user data
    
    Raises:
        HTTPException: If user with the same email already exists or validation fails
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
    
    # Audit user registration
    await create_audit_log(
        db,
        action="user_register",
        resource_type="user",
        resource_id=str(user.id),
        user_id=user.id,
        ip_address=client_ip,
        user_agent=user_agent,
        status="success"
    )
    
    return user


@router.post("/refresh", response_model=Token)
async def refresh_token(
    response: Response,
    refresh_token: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Any:
    """
    Refresh access token.
    
    This endpoint issues a new access token using a valid refresh token.
    
    Args:
        response: FastAPI response object for setting cookies
        refresh_token: Refresh token from previous authentication
        db: Database session
        client_ip: Client IP address
        user_agent: User agent string from request headers
    
    Returns:
        New Token object with fresh access_token and refresh_token
    
    Raises:
        HTTPException: If refresh token is invalid or blacklisted
    """
    try:
        # Check if token is blacklisted
        if await is_token_blacklisted(refresh_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Validate the refresh token
        payload = TokenPayload.validate_refresh_token(refresh_token)
        
        # Get user from database
        user = await get_user_by_email(db, email=payload.sub)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Inactive user",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Generate token scopes based on user roles
        scopes = ["user"]  # Base scope for all authenticated users
        
        # Add role-based scopes
        for role in user.roles:
            scopes.append(role.name)
        
        # Create new access and refresh tokens
        new_access_token = create_access_token(
            subject=user.email,
            scopes=scopes,
            additional_data={
                "user_id": str(user.id),
                "is_superuser": user.is_superuser,
            }
        )
        
        new_refresh_token = create_refresh_token(subject=user.email)
        
        # Blacklist the old refresh token
        await add_token_to_blocklist(refresh_token, payload.exp)
        
        # Audit token refresh
        await create_audit_log(
            db,
            action="token_refresh",
            resource_type="user",
            resource_id=str(user.id),
            user_id=user.id,
            ip_address=client_ip,
            user_agent=user_agent,
            status="success"
        )
        
        # Set refresh token as HTTP-only cookie if configured
        if settings.USE_REFRESH_TOKEN_COOKIE:
            cookie_max_age = int(settings.refresh_token_expires.total_seconds())
            response.set_cookie(
                key="refresh_token",
                value=new_refresh_token,
                httponly=True,
                secure=settings.SESSION_COOKIE_SECURE,
                samesite=settings.SESSION_COOKIE_SAMESITE,
                max_age=cookie_max_age,
                path="/api/v1/auth/refresh"
            )
            
            # Don't include refresh token in response body if using cookie
            return {
                "access_token": new_access_token,
                "token_type": "bearer",
                "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
            }
        
        # Return both tokens in response body
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
        
    except (ValueError, HTTPException) as e:
        if isinstance(e, HTTPException):
            raise e
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: str = Body(None, embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, str]:
    """
    Logout the current user.
    
    This endpoint invalidates the user's refresh token and clears any cookies.
    
    Args:
        response: FastAPI response object for clearing cookies
        refresh_token: Optional refresh token to invalidate
        current_user: Current authenticated user
        db: Database session
        client_ip: Client IP address
        user_agent: User agent string from request headers
    
    Returns:
        Success message
    """
    # Blacklist the refresh token if provided
    if refresh_token:
        try:
            # Validate the token first
            payload = TokenPayload.validate_refresh_token(refresh_token)
            
            # Add to blocklist
            await add_token_to_blocklist(refresh_token, payload.exp)
        except ValueError:
            # If token is invalid, we don't need to blacklist it
            pass
    
    # Clear refresh token cookie if it exists
    if settings.USE_REFRESH_TOKEN_COOKIE:
        response.delete_cookie(
            key="refresh_token",
            path="/api/v1/auth/refresh"
        )
    
    # Audit logout
    await create_audit_log(
        db,
        action="logout",
        resource_type="user",
        resource_id=str(current_user.id),
        user_id=current_user.id,
        ip_address=client_ip,
        user_agent=user_agent,
        status="success"
    )
    
    return {"message": "Successfully logged out"}


@router.post("/change-password")
async def change_password(
    current_password: str = Body(..., embed=True),
    new_password: str = Body(..., embed=True),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, str]:
    """
    Change the current user's password.
    
    This endpoint allows a user to change their password by providing their
    current password and a new password.
    
    Args:
        current_password: User's current password
        new_password: New password to set
        current_user: Current authenticated user
        db: Database session
        client_ip: Client IP address
        user_agent: User agent string from request headers
    
    Returns:
        Success message
    
    Raises:
        HTTPException: If current password is incorrect or new password is invalid
    """
    # Verify current password
    if not verify_password(current_password, current_user.hashed_password):
        # Audit failed password change
        await create_audit_log(
            db,
            action="change_password_failed",
            resource_type="user",
            resource_id=str(current_user.id),
            user_id=current_user.id,
            ip_address=client_ip,
            user_agent=user_agent,
            status="failure",
            details={"reason": "Incorrect current password"}
        )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    # Validate new password
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters long"
        )
    
    # Update password
    await update_user_password(db, user=current_user, new_password=new_password)
    
    # Audit password change
    await create_audit_log(
        db,
        action="change_password",
        resource_type="user",
        resource_id=str(current_user.id),
        user_id=current_user.id,
        ip_address=client_ip,
        user_agent=user_agent,
        status="success"
    )
    
    return {"message": "Password changed successfully"}


@router.post("/forgot-password")
async def forgot_password(
    email: EmailStr = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, str]:
    """
    Initiate password reset process.
    
    This endpoint sends a password reset link to the user's email.
    
    Args:
        email: Email address of the user
        db: Database session
        client_ip: Client IP address
        user_agent: User agent string from request headers
    
    Returns:
        Success message (always returns success for security reasons)
    """
    # Find user by email
    user = await get_user_by_email(db, email=email)
    
    # If user exists, generate reset token and send email
    if user and user.is_active:
        # Generate password reset token
        reset_token = create_access_token(
            subject=user.email,
            expires_delta=timedelta(hours=24),  # 24-hour expiry for reset tokens
            additional_data={"purpose": "password_reset"}
        )
        
        # In a real implementation, send an email with the reset link
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        
        # TODO: Implement email sending functionality
        logger.info(f"Password reset link for {email}: {reset_link}")
        
        # Audit password reset request
        await create_audit_log(
            db,
            action="forgot_password",
            resource_type="user",
            resource_id=str(user.id),
            user_id=user.id,
            ip_address=client_ip,
            user_agent=user_agent,
            status="success"
        )
    
    # Always return success to prevent email enumeration
    return {"message": "If your email is registered, you will receive a password reset link"}


@router.post("/reset-password")
async def reset_password(
    token: str = Body(..., embed=True),
    new_password: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, str]:
    """
    Reset password using a reset token.
    
    This endpoint allows a user to set a new password using a valid reset token.
    
    Args:
        token: Password reset token from email
        new_password: New password to set
        db: Database session
        client_ip: Client IP address
        user_agent: User agent string from request headers
    
    Returns:
        Success message
    
    Raises:
        HTTPException: If token is invalid or new password is invalid
    """
    try:
        # Validate the reset token
        payload = TokenPayload.validate_token(token)
        
        # Check if token is for password reset
        if payload.get("purpose") != "password_reset":
            raise ValueError("Invalid token purpose")
        
        # Get user from database
        user = await get_user_by_email(db, email=payload.sub)
        if not user or not user.is_active:
            raise ValueError("User not found or inactive")
        
        # Validate new password
        if len(new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be at least 8 characters long"
            )
        
        # Update password
        await update_user_password(db, user=user, new_password=new_password)
        
        # Audit password reset
        await create_audit_log(
            db,
            action="reset_password",
            resource_type="user",
            resource_id=str(user.id),
            user_id=user.id,
            ip_address=client_ip,
            user_agent=user_agent,
            status="success"
        )
        
        return {"message": "Password reset successfully"}
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token"
        )


@router.get("/me", response_model=UserResponse)
async def read_current_user(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get current user information.
    
    This endpoint returns information about the currently authenticated user.
    
    Args:
        current_user: Current authenticated user
    
    Returns:
        Current user data
    """
    return current_user
