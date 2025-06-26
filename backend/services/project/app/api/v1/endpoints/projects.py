"""
AITHERIA ALTOS - Project Service Project Endpoints
=================================================

This module implements the project management endpoints for the Project service, including:
- List projects (with filtering and pagination)
- Get project details
- Create new projects
- Update project information
- Delete projects (soft delete)

These endpoints enforce appropriate authorization checks to ensure that
only authorized users can access or modify project data.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import UUID4
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.project import Project, ProjectStatus, ProjectVisibility
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
)

router = APIRouter()


@router.get("/", response_model=ProjectListResponse)
async def list_projects(
    db: AsyncSession = Depends(get_db),
    # current_user: User = Depends(get_current_active_user), # Assuming authentication from Auth service
    skip: int = Query(0, ge=0, description="Number of projects to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of projects to return"),
    name: Optional[str] = Query(None, description="Filter by project name (partial match)"),
    owner_id: Optional[UUID4] = Query(None, description="Filter by owner ID"),
    organization_id: Optional[UUID4] = Query(None, description="Filter by organization ID"),
    status: Optional[ProjectStatus] = Query(None, description="Filter by project status"),
    visibility: Optional[ProjectVisibility] = Query(None, description="Filter by project visibility"),
) -> Any:
    """
    Retrieve projects with pagination and filtering.

    This endpoint returns a paginated list of projects with optional filtering.
    Access control will be implemented based on user roles and project visibility.

    Args:
        db: Database session
        skip: Number of projects to skip (for pagination)
        limit: Maximum number of projects to return
        name: Optional filter by project name (partial match)
        owner_id: Optional filter by owner ID
        organization_id: Optional filter by organization ID
        status: Optional filter by project status
        visibility: Optional filter by project visibility

    Returns:
        Paginated list of projects
    """
    # TODO: Implement proper authorization based on current_user and project visibility
    # For now, it lists all projects, but in a real scenario, it would filter based on user permissions.

    # Build query conditions
    conditions = [Project.deleted_at == None]  # Only include non-deleted projects

    if name:
        conditions.append(Project.name.ilike(f"%{name}%"))
    if owner_id:
        conditions.append(Project.owner_id == owner_id)
    if organization_id:
        conditions.append(Project.organization_id == organization_id)
    if status:
        # Compare against the string value stored in the DB
        conditions.append(Project.status == status.value)
    if visibility:
        # Compare against the string value stored in the DB
        conditions.append(Project.visibility == visibility.value)

    # Get total count
    count_query = select(func.count()).select_from(Project).where(and_(*conditions))
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get projects with pagination
    query = (
        select(Project)
        .where(and_(*conditions))
        .order_by(Project.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)
    projects = result.scalars().all()

    return {
        "items": projects,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    # current_user: User = Depends(get_current_active_user), # Assuming authentication from Auth service
) -> Any:
    """
    Create a new project.

    This endpoint creates a new project with the provided information.
    The creating user will be set as the owner.

    Args:
        project_in: Project creation data
        db: Database session

    Returns:
        Created project data

    Raises:
        HTTPException: If a project with the same name already exists or validation fails
    """
    # TODO: Implement proper authorization (e.g., only authenticated users can create projects)
    # For now, it allows creation, but in a real scenario, it would check user permissions.

    # Check if a project with the same name already exists
    existing_project_query = select(Project).where(
        and_(
            func.lower(Project.name) == func.lower(project_in.name),
            Project.deleted_at == None,
        )
    )
    existing_project_result = await db.execute(existing_project_query)
    existing_project = existing_project_result.scalar_one_or_none()

    if existing_project:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with name '{project_in.name}' already exists",
        )

    # Create new project
    project = Project(**project_in.model_dump(exclude_unset=True))
    
    # Set created_by_id and updated_by_id from current_user if available
    # project.created_by_id = current_user.id
    # project.updated_by_id = current_user.id

    db.add(project)
    await db.commit()
    await db.refresh(project)

    return project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID4 = Path(..., description="The ID of the project to get"),
    db: AsyncSession = Depends(get_db),
    # current_user: User = Depends(get_current_active_user), # Assuming authentication from Auth service
) -> Any:
    """
    Get a specific project by ID.

    This endpoint returns detailed information about a specific project.
    Access control will be implemented based on user roles and project visibility.

    Args:
        project_id: ID of the project to get
        db: Database session

    Returns:
        Project details

    Raises:
        HTTPException: If project is not found or current user doesn't have permission
    """
    # Query for the project
    query = select(Project).where(
        and_(
            Project.id == project_id,
            Project.deleted_at == None,
        )
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )

    # TODO: Implement proper authorization based on current_user and project visibility
    # if not project.is_public and project.owner_id != current_user.id and \
    #    (project.visibility == ProjectVisibility.ORGANIZATION and project.organization_id != current_user.organization_id):
    #    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions to access this project")

    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID4 = Path(..., description="The ID of the project to update"),
    project_in: ProjectUpdate = Body(...),
    db: AsyncSession = Depends(get_db),
    # current_user: User = Depends(get_current_active_user), # Assuming authentication from Auth service
) -> Any:
    """
    Update a project's information.

    This endpoint updates a project's information with the provided data.
    Only project owners or authorized users can update projects.

    Args:
        project_id: ID of the project to update
        project_in: Project update data
        db: Database session

    Returns:
        Updated project data

    Raises:
        HTTPException: If project is not found or current user doesn't have permission
    """
    # Query for the project
    query = select(Project).where(
        and_(
            Project.id == project_id,
            Project.deleted_at == None,
        )
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )

    # TODO: Implement proper authorization (e.g., only owner or admin can update)
    # if project.owner_id != current_user.id and not current_user.is_superuser:
    #    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions to update this project")

    # Check if name is being updated and if it conflicts with an existing project
    if project_in.name and project_in.name != project.name:
        existing_project_query = select(Project).where(
            and_(
                func.lower(Project.name) == func.lower(project_in.name),
                Project.id != project_id,
                Project.deleted_at == None,
            )
        )
        existing_project_result = await db.execute(existing_project_query)
        existing_project = existing_project_result.scalar_one_or_none()

        if existing_project:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project with name '{project_in.name}' already exists",
            )

    # Update project attributes
    update_data = project_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    # Set updated_by_id from current_user if available
    # project.updated_by_id = current_user.id

    db.add(project)
    await db.commit()
    await db.refresh(project)

    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID4 = Path(..., description="The ID of the project to delete (soft delete)"),
    db: AsyncSession = Depends(get_db),
    # current_user: User = Depends(get_current_active_user), # Assuming authentication from Auth service
) -> None:
    """
    Delete a project (soft delete).

    This endpoint performs a soft delete on a project, marking it as deleted
    without removing it from the database. Only project owners or authorized users can delete projects.

    Args:
        project_id: ID of the project to delete
        db: Database session

    Raises:
        HTTPException: If project is not found or current user doesn't have permission
    """
    # Query for the project
    query = select(Project).where(
        and_(
            Project.id == project_id,
            Project.deleted_at == None,
        )
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )

    # TODO: Implement proper authorization (e.g., only owner or admin can delete)
    # if project.owner_id != current_user.id and not current_user.is_superuser:
    #    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions to delete this project")

    # Perform soft delete
    from datetime import datetime
    project.deleted_at = datetime.now()
    
    # Set updated_by_id from current_user if available
    # project.updated_by_id = current_user.id

    db.add(project)
    await db.commit()
