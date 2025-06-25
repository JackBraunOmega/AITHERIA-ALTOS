"""
AITHERIA ALTOS - Auth Service Role Schemas
=========================================

This module defines Pydantic schemas for roles in the Auth service, including:
- Role creation
- Role updates
- Role responses (for API endpoints)
- Role list responses (paginated)
- Role responses with permission information

These schemas are used for request/response validation, serialization, and
documentation in the Auth service API.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, UUID4, validator

class RoleBase(BaseModel):
    """
    Base schema for role data.
    
    This schema defines the common fields for role schemas.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Role name")
    description: Optional[str] = Field(None, max_length=255, description="Role description")
    is_system: Optional[bool] = Field(None, description="Whether this is a system role (cannot be modified or deleted)")

class RoleCreate(RoleBase):
    """
    Schema for creating a new role.
    
    This schema is used for creating new roles in the system.
    """
    name: str = Field(..., min_length=1, max_length=100, description="Role name")
    permission_names: Optional[List[str]] = Field(default_factory=list, description="List of permission names to assign to the role")
    
    @validator('name')
    def name_format(cls, v):
        """Validate that role name is in a valid format."""
        if not v.isalnum() and not '_' in v:
            raise ValueError("Role name must contain only alphanumeric characters and underscores")
        return v.lower()  # Store role names in lowercase for consistency

class RoleUpdate(RoleBase):
    """
    Schema for updating an existing role.
    
    This schema is used for updating role information.
    It makes all fields optional to allow partial updates.
    """
    permission_names: Optional[List[str]] = Field(None, description="List of permission names to assign to the role")
    
    @validator('name')
    def name_format(cls, v):
        """Validate that role name is in a valid format if provided."""
        if v is not None:
            if not v.isalnum() and not '_' in v:
                raise ValueError("Role name must contain only alphanumeric characters and underscores")
            return v.lower()  # Store role names in lowercase for consistency
        return v

class RoleInDBBase(RoleBase):
    """
    Base schema for role data from the database.
    
    This schema includes all fields that are stored in the database,
    including system fields like ID and timestamps.
    """
    id: UUID4 = Field(..., description="Role ID")
    name: str = Field(..., description="Role name")
    is_system: bool = Field(..., description="Whether this is a system role")
    created_at: datetime = Field(..., description="When the role was created")
    updated_at: datetime = Field(..., description="When the role was last updated")
    
    class Config:
        orm_mode = True

class RoleResponse(RoleInDBBase):
    """
    Schema for role responses.
    
    This schema is used for API responses that include role data.
    """
    pass

class RoleWithPermissions(RoleResponse):
    """
    Schema for role responses with permission information.
    
    This schema extends the RoleResponse schema to include permission information,
    which is useful for endpoints that need to display role permissions.
    """
    permissions: List[str] = Field(default_factory=list, description="List of permission names assigned to the role")

class RoleListResponse(BaseModel):
    """
    Schema for paginated role list responses.
    
    This schema is used for the response of the list roles endpoint.
    """
    items: List[RoleResponse] = Field(..., description="List of roles")
    total: int = Field(..., description="Total number of roles matching the query")
    skip: int = Field(..., description="Number of roles skipped")
    limit: int = Field(..., description="Maximum number of roles returned")
