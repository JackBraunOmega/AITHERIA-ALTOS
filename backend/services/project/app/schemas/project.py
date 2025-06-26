"""
AITHERIA ALTOS - Project Service Project Schemas
===============================================

This module defines Pydantic schemas for projects in the Project service, including:
- Project creation
- Project updates
- Project responses (for API endpoints)
- Project list responses (paginated)

These schemas include validation for project fields and are used for request/response validation, serialization, and documentation
in the Project service API.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, UUID4, validator

from app.models.project import ProjectStatus, ProjectVisibility


class ProjectBase(BaseModel):
    """
    Base schema for project data.

    This schema defines the common fields for project schemas.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Unique name of the research project")
    description: Optional[str] = Field(None, max_length=1000, description="Detailed description of the project")
    status: Optional[ProjectStatus] = Field(None, description="Current status of the project")
    owner_id: Optional[UUID4] = Field(None, description="ID of the user who owns the project")
    organization_id: Optional[UUID4] = Field(None, description="ID of the organization the project belongs to")
    version: Optional[int] = Field(None, ge=1, description="Current version number of the project")
    previous_version_id: Optional[UUID4] = Field(None, description="ID of the previous version of this project")
    visibility: Optional[ProjectVisibility] = Field(None, description="Visibility level of the project")
    start_date: Optional[datetime] = Field(None, description="Planned or actual start date of the project")
    end_date: Optional[datetime] = Field(None, description="Planned or actual end date of the project")
    budget: Optional[float] = Field(None, ge=0, description="Allocated budget for the project")
    tags: Optional[List[str]] = Field(None, description="Keywords or labels for categorizing the project")
    objectives: Optional[str] = Field(None, description="Key objectives of the research project")
    hypotheses: Optional[str] = Field(None, description="Hypotheses being tested in the project")
    results_summary: Optional[str] = Field(None, description="Summary of the project's results or findings")
    # `metadata` is no longer a reserved attribute in our SQLAlchemy model (column
    # name explicitly set to `"metadata"`).  We therefore expose it with the same
    # name in the API schema and remove the alias indirection.
    project_metadata: Optional[Dict[str, Any]] = Field(
        None,
        alias="metadata",  # Expose as 'metadata' in API but use 'project_metadata' in code
        description="Flexible JSONB field for additional project-specific metadata",
    )

    @validator('name')
    def name_not_empty(cls, v):
        """Validate that project name is not empty."""
        if v is not None and not v.strip():
            raise ValueError("Project name cannot be empty")
        return v


class ProjectCreate(ProjectBase):
    """
    Schema for creating a new project.

    This schema is used for creating new projects in the system.
    """
    name: str = Field(..., min_length=1, max_length=255, description="Unique name of the research project")
    owner_id: UUID4 = Field(..., description="ID of the user who owns the project")
    organization_id: UUID4 = Field(..., description="ID of the organization the project belongs to")


class ProjectUpdate(ProjectBase):
    """
    Schema for updating an existing project.

    This schema is used for updating project information.
    It makes all fields optional to allow partial updates.
    """
    pass


class ProjectInDBBase(ProjectBase):
    """
    Base schema for project data from the database.

    This schema includes all fields that are stored in the database,
    including system fields like ID and timestamps.
    """
    id: UUID4 = Field(..., description="Project ID")
    created_at: datetime = Field(..., description="When the project was created")
    updated_at: datetime = Field(..., description="When the project was last updated")
    created_by_id: Optional[UUID4] = Field(None, description="ID of the user who initially created this project")
    updated_by_id: Optional[UUID4] = Field(None, description="ID of the user who last updated this project")
    deleted_at: Optional[datetime] = Field(None, description="Timestamp for soft deletion")

    class Config:
        from_attributes = True  # Use from_attributes instead of orm_mode for Pydantic V2


class ProjectResponse(ProjectInDBBase):
    """
    Schema for project responses.

    This schema is used for API responses that include project data.
    It excludes sensitive information.
    """
    pass


class ProjectListResponse(BaseModel):
    """
    Schema for paginated project list responses.

    This schema is used for the response of the list projects endpoint.
    """
    items: List[ProjectResponse] = Field(..., description="List of projects")
    total: int = Field(..., description="Total number of projects matching the query")
    skip: int = Field(..., description="Number of projects skipped")
    limit: int = Field(..., description="Maximum number of projects returned")
