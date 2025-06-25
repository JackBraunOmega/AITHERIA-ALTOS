"""
AITHERIA ALTOS - Auth Service User Schemas
=========================================

This module defines Pydantic schemas for users in the Auth service, including:
- User creation (registration)
- User updates
- User responses (for API endpoints)
- User list responses (paginated)

These schemas include validation for email, password strength, and other fields,
and are used for request/response validation, serialization, and documentation
in the Auth service API.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, EmailStr, Field, UUID4, validator, root_validator
import re

from app.core.config import settings


class UserBase(BaseModel):
    """
    Base schema for user data.
    
    This schema defines the common fields for user schemas.
    """
    email: Optional[EmailStr] = Field(None, description="User email address")
    first_name: Optional[str] = Field(None, min_length=1, max_length=100, description="User first name")
    last_name: Optional[str] = Field(None, min_length=1, max_length=100, description="User last name")
    is_active: Optional[bool] = Field(None, description="Whether the user account is active")
    is_verified: Optional[bool] = Field(None, description="Whether the user email is verified")
    auth_provider: Optional[str] = Field(None, description="Authentication provider (email, google, orcid, etc.)")


class UserCreate(UserBase):
    """
    Schema for creating a new user.
    
    This schema is used for user registration and admin user creation.
    It includes password validation for security.
    """
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=100, description="User password")
    is_active: bool = Field(True, description="Whether the user account is active")
    is_superuser: Optional[bool] = Field(False, description="Whether the user is a superuser (admin only)")
    is_verified: Optional[bool] = Field(False, description="Whether the user email is verified")
    organization_id: Optional[UUID4] = Field(None, description="Organization ID")
    
    @validator('password')
    def password_strength(cls, v):
        """
        Validate password strength.
        
        Password must:
        - Be at least 8 characters long
        - Contain at least one uppercase letter
        - Contain at least one lowercase letter
        - Contain at least one digit
        - Contain at least one special character
        """
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        # Check for uppercase letter
        if not re.search(r'[A-Z]', v):
            raise ValueError("Password must contain at least one uppercase letter")
        
        # Check for lowercase letter
        if not re.search(r'[a-z]', v):
            raise ValueError("Password must contain at least one lowercase letter")
        
        # Check for digit
        if not re.search(r'\d', v):
            raise ValueError("Password must contain at least one digit")
        
        # Check for special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError("Password must contain at least one special character")
        
        return v


class UserUpdate(UserBase):
    """
    Schema for updating an existing user.
    
    This schema is used for updating user information.
    It makes all fields optional to allow partial updates.
    """
    password: Optional[str] = Field(None, min_length=8, max_length=100, description="User password")
    is_superuser: Optional[bool] = Field(None, description="Whether the user is a superuser (admin only)")
    organization_id: Optional[UUID4] = Field(None, description="Organization ID")
    
    @validator('password')
    def password_strength(cls, v):
        """Validate password strength if password is provided."""
        if v is not None:
            # Reuse validation from UserCreate
            return UserCreate.password_strength(v)
        return v


class UserInDBBase(UserBase):
    """
    Base schema for user data from the database.
    
    This schema includes all fields that are stored in the database,
    including system fields like ID and timestamps.
    """
    id: UUID4 = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email address")
    is_active: bool = Field(..., description="Whether the user account is active")
    is_superuser: bool = Field(..., description="Whether the user is a superuser")
    is_verified: bool = Field(..., description="Whether the user email is verified")
    created_at: datetime = Field(..., description="When the user was created")
    updated_at: datetime = Field(..., description="When the user was last updated")
    last_login_at: Optional[datetime] = Field(None, description="When the user last logged in")
    auth_provider: str = Field(..., description="Authentication provider (email, google, orcid, etc.)")
    organization_id: Optional[UUID4] = Field(None, description="Organization ID")
    mfa_enabled: bool = Field(..., description="Whether multi-factor authentication is enabled")
    
    class Config:
        orm_mode = True


class UserInDB(UserInDBBase):
    """
    Schema for user data from the database including the hashed password.
    
    This schema is used internally and should never be exposed in API responses.
    """
    hashed_password: str = Field(..., description="Hashed user password")


class UserResponse(UserInDBBase):
    """
    Schema for user responses.
    
    This schema is used for API responses that include user data.
    It excludes sensitive information like the hashed password.
    """
    pass


class UserWithRoles(UserResponse):
    """
    Schema for user responses with role information.
    
    This schema extends the UserResponse schema to include role information,
    which is useful for endpoints that need to display user permissions.
    """
    roles: List[str] = Field(default_factory=list, description="List of role names assigned to the user")


class UserListResponse(BaseModel):
    """
    Schema for paginated user list responses.
    
    This schema is used for the response of the list users endpoint.
    """
    items: List[UserResponse] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users matching the query")
    skip: int = Field(..., description="Number of users skipped")
    limit: int = Field(..., description="Maximum number of users returned")


class UserWithPermissions(UserWithRoles):
    """
    Schema for user responses with role and permission information.
    
    This schema extends the UserWithRoles schema to include detailed permission information,
    which is useful for authorization checks and admin interfaces.
    """
    permissions: List[str] = Field(default_factory=list, description="List of permissions granted through roles")
