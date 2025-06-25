"""
AITHERIA ALTOS - Auth Service Permission Schemas
===============================================

This module defines Pydantic schemas for permissions in the Auth service, including:
- Permission creation
- Permission updates
- Permission responses (for API endpoints)
- Permission list responses (paginated)

These schemas are used for request/response validation, serialization, and
documentation in the Auth service API.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, UUID4, validator


class PermissionBase(BaseModel):
    """
    Base schema for permission data.
    
    This schema defines the common fields for permission schemas.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Permission name")
    description: Optional[str] = Field(None, max_length=255, description="Permission description")
    is_system: Optional[bool] = Field(None, description="Whether this is a system permission (cannot be modified or deleted)")


class PermissionCreate(PermissionBase):
    """
    Schema for creating a new permission.
    
    This schema is used for creating new permissions in the system.
    """
    name: str = Field(..., min_length=1, max_length=100, description="Permission name")
    
    @validator('name')
    def name_format(cls, v):
        """Validate that permission name is in a valid format."""
        if not ':' in v:
            raise ValueError("Permission name must be in format 'resource:action' (e.g., 'user:read')")
        
        resource, action = v.split(':', 1)
        if not resource or not action:
            raise ValueError("Permission name must have both resource and action parts")
        
        if not all(c.isalnum() or c == '_' for c in resource) or not all(c.isalnum() or c == '_' for c in action):
            raise ValueError("Permission resource and action must contain only alphanumeric characters and underscores")
        
        return v.lower()  # Store permission names in lowercase for consistency


class PermissionUpdate(PermissionBase):
    """
    Schema for updating an existing permission.
    
    This schema is used for updating permission information.
    It makes all fields optional to allow partial updates.
    """
    @validator('name')
    def name_format(cls, v):
        """Validate that permission name is in a valid format if provided."""
        if v is not None:
            if not ':' in v:
                raise ValueError("Permission name must be in format 'resource:action' (e.g., 'user:read')")
            
            resource, action = v.split(':', 1)
            if not resource or not action:
                raise ValueError("Permission name must have both resource and action parts")
            
            if not all(c.isalnum() or c == '_' for c in resource) or not all(c.isalnum() or c == '_' for c in action):
                raise ValueError("Permission resource and action must contain only alphanumeric characters and underscores")
            
            return v.lower()  # Store permission names in lowercase for consistency
        return v


class PermissionInDBBase(PermissionBase):
    """
    Base schema for permission data from the database.
    
    This schema includes all fields that are stored in the database,
    including system fields like ID and timestamps.
    """
    id: UUID4 = Field(..., description="Permission ID")
    name: str = Field(..., description="Permission name")
    is_system: bool = Field(..., description="Whether this is a system permission")
    created_at: datetime = Field(..., description="When the permission was created")
    updated_at: datetime = Field(..., description="When the permission was last updated")
    
    class Config:
        orm_mode = True


class PermissionResponse(PermissionInDBBase):
    """
    Schema for permission responses.
    
    This schema is used for API responses that include permission data.
    """
    pass


class PermissionListResponse(BaseModel):
    """
    Schema for paginated permission list responses.
    
    This schema is used for the response of the list permissions endpoint.
    """
    items: List[PermissionResponse] = Field(..., description="List of permissions")
    total: int = Field(..., description="Total number of permissions matching the query")
    skip: int = Field(..., description="Number of permissions skipped")
    limit: int = Field(..., description="Maximum number of permissions returned")
