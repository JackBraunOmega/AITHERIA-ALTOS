"""
AITHERIA ALTOS - Auth Service Organization Schemas
=================================================

This module defines Pydantic schemas for organizations in the Auth service, including:
- Organization creation
- Organization updates
- Organization responses (for API endpoints)
- Organization list responses (paginated)
- Organization responses with user information

These schemas are used for request/response validation, serialization, and
documentation in the Auth service API.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, EmailStr, Field, UUID4, validator, AnyHttpUrl


class OrganizationBase(BaseModel):
    """
    Base schema for organization data.
    
    This schema defines the common fields for organization schemas.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Organization name")
    description: Optional[str] = Field(None, max_length=1000, description="Organization description")
    is_active: Optional[bool] = Field(None, description="Whether the organization is active")
    email: Optional[EmailStr] = Field(None, description="Organization contact email")
    website: Optional[str] = Field(None, max_length=255, description="Organization website URL")
    
    @validator('website')
    def validate_website(cls, v):
        """Validate website URL format if provided."""
        if v is not None:
            if not v.startswith(('http://', 'https://')):
                v = 'https://' + v
        return v


class OrganizationCreate(OrganizationBase):
    """
    Schema for creating a new organization.
    
    This schema is used for creating new organizations in the system.
    """
    name: str = Field(..., min_length=1, max_length=255, description="Organization name")
    is_active: bool = Field(True, description="Whether the organization is active")
    is_system: Optional[bool] = Field(False, description="Whether this is a system organization (admin only)")
    
    @validator('name')
    def name_not_empty(cls, v):
        """Validate that organization name is not empty."""
        if not v.strip():
            raise ValueError("Organization name cannot be empty")
        return v


class OrganizationUpdate(OrganizationBase):
    """
    Schema for updating an existing organization.
    
    This schema is used for updating organization information.
    It makes all fields optional to allow partial updates.
    """
    pass


class OrganizationInDBBase(OrganizationBase):
    """
    Base schema for organization data from the database.
    
    This schema includes all fields that are stored in the database,
    including system fields like ID and timestamps.
    """
    id: UUID4 = Field(..., description="Organization ID")
    name: str = Field(..., description="Organization name")
    is_active: bool = Field(..., description="Whether the organization is active")
    is_system: bool = Field(..., description="Whether this is a system organization")
    created_at: datetime = Field(..., description="When the organization was created")
    updated_at: datetime = Field(..., description="When the organization was last updated")
    
    class Config:
        orm_mode = True


class OrganizationResponse(OrganizationInDBBase):
    """
    Schema for organization responses.
    
    This schema is used for API responses that include organization data.
    """
    pass


class UserBrief(BaseModel):
    """
    Brief schema for user data in organization responses.
    
    This schema includes only the essential user information needed
    when listing users in an organization.
    """
    id: UUID4 = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email address")
    first_name: Optional[str] = Field(None, description="User first name")
    last_name: Optional[str] = Field(None, description="User last name")
    is_active: bool = Field(..., description="Whether the user account is active")
    
    class Config:
        orm_mode = True


class OrganizationWithUsers(OrganizationResponse):
    """
    Schema for organization responses with user information.
    
    This schema extends the OrganizationResponse schema to include user information,
    which is useful for endpoints that need to display organization members.
    """
    users: List[UserBrief] = Field(default_factory=list, description="List of users in the organization")


class OrganizationListResponse(BaseModel):
    """
    Schema for paginated organization list responses.
    
    This schema is used for the response of the list organizations endpoint.
    """
    items: List[OrganizationResponse] = Field(..., description="List of organizations")
    total: int = Field(..., description="Total number of organizations matching the query")
    skip: int = Field(..., description="Number of organizations skipped")
    limit: int = Field(..., description="Maximum number of organizations returned")
