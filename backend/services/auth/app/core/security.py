"""
AITHERIA ALTOS - Auth Service Security Module
============================================

This module provides security utilities for the Auth service, including:
- Password hashing and verification
- JWT token generation and validation
- OAuth2 authentication schemes
- User authentication and authorization

Usage:
    from app.core.security import (
        get_password_hash,
        verify_password,
        create_access_token,
        get_current_user,
    )
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.token import TokenData
from app.services.user_service import get_user_by_email

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    scopes={
        "user": "Read information about the current user.",
        "admin": "Full access to user management and system settings.",
        "lab": "Access to laboratory resources and experiments.",
        "project": "Access to project management features.",
    },
)


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password to hash
        
    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against
        
    Returns:
        True if the password matches the hash, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: Union[str, Any],
    scopes: list[str] = None,
    expires_delta: Optional[timedelta] = None,
    additional_data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a JWT access token.
    
    Args:
        subject: Subject of the token (typically user ID)
        scopes: List of permission scopes to include in the token
        expires_delta: Optional expiration time, defaults to settings value
        additional_data: Optional additional data to include in the token
        
    Returns:
        JWT token string
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + settings.access_token_expires
    
    # Base payload
    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.utcnow(),
        "nbf": datetime.utcnow(),
        "type": "access_token",
    }
    
    # Add scopes if provided
    if scopes:
        payload["scopes"] = scopes
    
    # Add additional data if provided
    if additional_data:
        for key, value in additional_data.items():
            if key not in payload:  # Don't override existing keys
                payload[key] = value
    
    # Encode the JWT token
    encoded_jwt = jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def create_refresh_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT refresh token.
    
    Args:
        subject: Subject of the token (typically user ID)
        expires_delta: Optional expiration time, defaults to settings value
        
    Returns:
        JWT refresh token string
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + settings.refresh_token_expires
    
    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh_token",
    }
    
    encoded_jwt = jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


async def get_current_user(
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get the current authenticated user from a JWT token.
    
    This dependency can be used in FastAPI route functions to require
    authentication and get the current user.
    
    Args:
        security_scopes: Security scopes required for the endpoint
        token: JWT token from the Authorization header
        db: Database session
        
    Returns:
        User model instance for the authenticated user
        
    Raises:
        HTTPException: If authentication fails or user lacks required permissions
    """
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": authenticate_value},
    )
    
    try:
        # Decode and validate the JWT token
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        
        # Extract user ID from token
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        
        # Extract token data
        token_scopes = payload.get("scopes", [])
        token_data = TokenData(scopes=token_scopes, user_id=user_id)
    except (JWTError, ValidationError):
        raise credentials_exception
    
    # Get user from database
    user = await get_user_by_email(db, email=token_data.user_id)
    if user is None:
        raise credentials_exception
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    
    # Check required scopes
    for scope in security_scopes.scopes:
        if scope not in token_data.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": authenticate_value},
            )
    
    return user


async def get_current_active_user(
    current_user: User = Security(get_current_user, scopes=["user"])
) -> User:
    """
    Get the current active user.
    
    This dependency builds on get_current_user and adds a check that the user is active.
    
    Args:
        current_user: User from get_current_user dependency
        
    Returns:
        User model instance for the authenticated active user
        
    Raises:
        HTTPException: If the user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


async def get_current_admin_user(
    current_user: User = Security(get_current_user, scopes=["admin"])
) -> User:
    """
    Get the current admin user.
    
    This dependency requires the user to have admin scope.
    
    Args:
        current_user: User from get_current_user dependency with admin scope
        
    Returns:
        User model instance for the authenticated admin user
    """
    return current_user


def validate_token(token: str) -> Dict[str, Any]:
    """
    Validate a JWT token without checking database.
    
    This is useful for lightweight token validation in the API gateway.
    
    Args:
        token: JWT token string
        
    Returns:
        Dictionary of token payload data
        
    Raises:
        ValueError: If token is invalid
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}")
