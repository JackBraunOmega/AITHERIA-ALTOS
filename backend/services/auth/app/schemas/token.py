"""
AITHERIA ALTOS - Auth Service Token Schemas
==========================================

This module defines Pydantic schemas for tokens in the Auth service, including:
- JWT tokens for authentication (access and refresh tokens)
- API tokens for programmatic access
- Token payload validation and decoding
- Token creation and response models

These schemas are used for request/response validation, serialization, and
documentation in the Auth service API.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from jose import jwt, JWTError
from pydantic import BaseModel, Field, UUID4, validator, root_validator

from app.core.config import settings


class Token(BaseModel):
    """
    OAuth2 token response schema.
    
    This schema is used for the response of the login and token refresh endpoints.
    It follows the OAuth2 standard for token responses.
    """
    access_token: str = Field(..., description="JWT access token")
    refresh_token: Optional[str] = Field(None, description="JWT refresh token")
    token_type: str = Field("bearer", description="Token type (always 'bearer')")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class TokenPayload(BaseModel):
    """
    JWT token payload schema.
    
    This schema is used for validating and decoding JWT tokens.
    It represents the payload (claims) of a JWT token.
    """
    sub: str = Field(..., description="Subject (usually user email)")
    exp: int = Field(..., description="Expiration time (Unix timestamp)")
    iat: Optional[int] = Field(None, description="Issued at time (Unix timestamp)")
    nbf: Optional[int] = Field(None, description="Not valid before time (Unix timestamp)")
    type: Optional[str] = Field(None, description="Token type (access_token or refresh_token)")
    scopes: List[str] = Field(default_factory=list, description="Permission scopes")
    user_id: Optional[str] = Field(None, description="User ID")
    is_superuser: Optional[bool] = Field(None, description="Whether the user is a superuser")
    purpose: Optional[str] = Field(None, description="Token purpose (e.g., password_reset)")
    
    @classmethod
    def validate_token(cls, token: str) -> "TokenPayload":
        """
        Validate and decode a JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            TokenPayload instance with decoded token data
            
        Raises:
            ValueError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token, 
                settings.JWT_SECRET_KEY, 
                algorithms=[settings.ALGORITHM]
            )
            return cls(**payload)
        except JWTError as e:
            raise ValueError(f"Invalid token: {e}")
    
    @classmethod
    def validate_refresh_token(cls, token: str) -> "TokenPayload":
        """
        Validate and decode a refresh token.
        
        This method checks that the token is a valid refresh token.
        
        Args:
            token: JWT refresh token string
            
        Returns:
            TokenPayload instance with decoded token data
            
        Raises:
            ValueError: If token is invalid, expired, or not a refresh token
        """
        try:
            payload = cls.validate_token(token)
            
            # Check if token is a refresh token
            if payload.type != "refresh_token":
                raise ValueError("Token is not a refresh token")
            
            return payload
        except ValueError as e:
            raise ValueError(f"Invalid refresh token: {e}")


class TokenData(BaseModel):
    """
    Schema for token data extracted from JWT tokens.
    
    This schema represents the subset of JWT payload fields that the
    application needs to store or propagate after the token has been
    validated.  It intentionally mirrors a subset of ``TokenPayload`` but is
    used in places where Pydantic models (rather than raw dicts) are
    preferred—e.g., request dependencies, background tasks, or service
    helpers.
    """

    sub: str = Field(..., description="Subject (usually user email)")
    scopes: List[str] = Field(
        default_factory=list, description="Permission scopes contained in the token"
    )
    exp: Optional[int] = Field(
        None, description="Expiration time of the token (Unix timestamp)"
    )
    user_id: Optional[str] = Field(None, description="User ID associated with token")
    is_superuser: Optional[bool] = Field(
        False, description="Whether the user is a super-user"
    )


class APITokenBase(BaseModel):
    """
    Base schema for API tokens.
    
    This schema defines the common fields for API token schemas.
    """
    name: str = Field(..., min_length=1, max_length=255, description="Human-readable name for the token")
    description: Optional[str] = Field(None, description="Description of the token's purpose")
    scopes: Optional[str] = Field(None, description="Space-separated list of permission scopes")
    expires_at: Optional[datetime] = Field(None, description="When the token expires (null = no expiration)")


class APITokenCreate(APITokenBase):
    """
    Schema for creating a new API token.
    
    This schema is used for the request body of the create API token endpoint.
    """
    user_id: Optional[UUID4] = Field(None, description="User ID (admin only, defaults to current user)")
    
    @validator('scopes')
    def validate_scopes(cls, v):
        """Validate that scopes are properly formatted."""
        if v is not None:
            # Check that scopes are space-separated
            scopes = v.split()
            return ' '.join(scopes)
        return v


class APITokenResponse(APITokenBase):
    """
    Schema for API token responses.
    
    This schema is used for the response of API token endpoints.
    It includes all fields from the database model except the hashed token value.
    """
    id: UUID4 = Field(..., description="Token ID")
    user_id: UUID4 = Field(..., description="User ID")
    is_active: bool = Field(..., description="Whether the token is active")
    last_used_at: Optional[datetime] = Field(None, description="When the token was last used")
    created_at: datetime = Field(..., description="When the token was created")
    updated_at: datetime = Field(..., description="When the token was last updated")
    
    class Config:
        orm_mode = True


class APITokenListResponse(BaseModel):
    """
    Schema for paginated API token responses.
    
    This schema is used for the response of the list API tokens endpoint.
    """
    items: List[APITokenResponse] = Field(..., description="List of API tokens")
    total: int = Field(..., description="Total number of tokens matching the query")
    skip: int = Field(..., description="Number of tokens skipped")
    limit: int = Field(..., description="Maximum number of tokens returned")
