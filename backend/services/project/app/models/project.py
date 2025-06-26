"""
AITHERIA ALTOS - Project Service Project Model
============================================

This module defines the Project model for the Project service, which represents
research projects in the AITHERIA ALTOS platform. It includes fields for
project metadata, versioning, and access control.
"""

import uuid
from datetime import datetime
from typing import List, Optional
from enum import Enum

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


# Define enum values as strings for database compatibility
class ProjectStatus(str, Enum):
    """Enum for project status."""
    PLANNING = "planning"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    CANCELLED = "cancelled"


# Define enum values as strings for database compatibility
class ProjectVisibility(str, Enum):
    """Enum for project visibility."""
    PRIVATE = "private"  # Only owner and explicitly invited members
    ORGANIZATION = "organization"  # Visible to all members of the organization
    PUBLIC = "public"  # Visible to all platform users (read-only)


class Project(Base):
    """
    Project model representing research projects in the AITHERIA ALTOS platform.

    This model stores core information about a research project, including its
    status, ownership, versioning, and access control settings.
    """
    __tablename__ = "projects"

    # Basic identification and description
    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="Unique name of the research project"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed description of the project"
    )
    status: Mapped[str] = mapped_column(
        String(20), # Store enum value as string
        default=ProjectStatus.PLANNING.value,
        nullable=False,
        comment="Current status of the project (e.g., planning, active, completed)"
    )

    # Ownership and Organization
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="ID of the user who owns the project"
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="ID of the organization the project belongs to"
    )

    # Versioning
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="Current version number of the project"
    )
    previous_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),  # Self-referencing for version history
        nullable=True,
        comment="ID of the previous version of this project"
    )

    # Access Control
    visibility: Mapped[str] = mapped_column(
        String(20), # Store enum value as string
        default=ProjectVisibility.PRIVATE.value,
        nullable=False,
        comment="Visibility level of the project (private, organization, public)"
    )

    # Research-specific fields
    start_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Planned or actual start date of the project"
    )
    end_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Planned or actual end date of the project"
    )
    budget: Mapped[Optional[float]] = mapped_column(
        Numeric(15, 2),  # Up to 15 digits, 2 after decimal
        nullable=True,
        comment="Allocated budget for the project"
    )
    tags: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
        comment="Keywords or labels for categorizing the project"
    )
    objectives: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Key objectives of the research project"
    )
    hypotheses: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Hypotheses being tested in the project"
    )
    results_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Summary of the project's results or findings"
    )
    # NOTE:
    # ``metadata`` is **reserved** by SQLAlchemy’s Declarative API (it is the
    # MetaData collection for the whole SQL model).  Using it as an attribute
    # name causes ``InvalidRequestError`` at mapper configuration time.
    # We therefore expose the attribute as ``project_metadata`` while keeping
    # the underlying database column name **metadata** for backwards-compat.
    project_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata",  # DB column remains `metadata`
        JSONB,
        nullable=True,
        comment="Flexible JSONB field for additional project-specific metadata",
    )

    # Audit fields (inherited from Base, but adding specific user tracking)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ID of the user who initially created this project"
    )
    updated_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ID of the user who last updated this project"
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp for soft deletion"
    )
    # ------------------------------------------------------------------
    # NOTE: The fields above reference entities managed by the Auth service
    # (User, Organization).  In a micro-service architecture we cannot create
    # real SQL foreign-keys to tables that live in another DB, so we store the
    # UUIDs only.  Any look-ups must be resolved through inter-service calls.
    # ------------------------------------------------------------------

    # Self-referencing relationship for version history
    previous_version: Mapped[Optional["Project"]] = relationship(
        "Project",
        # SQLAlchemy will resolve this string after the class is mapped,
        # ensuring the correct column is used instead of Python's built-in `id`.
        primaryjoin="Project.previous_version_id == Project.id",
        remote_side="Project.id",
        back_populates="next_versions",
        lazy="joined"
    )
    next_versions: Mapped[List["Project"]] = relationship(
        "Project",
        primaryjoin="Project.id == Project.previous_version_id",
        back_populates="previous_version",
        lazy="noload"
    )

    # Placeholder for future relationships (e.g., tasks, team members, milestones)
    # team_members: Mapped[List["User"]] = relationship(
    #     "User",
    #     secondary="project_team_members", # Assuming an association table
    #     back_populates="projects",
    #     lazy="noload"
    # )
    # tasks: Mapped[List["Task"]] = relationship(
    #     "Task",
    #     back_populates="project",
    #     lazy="noload"
    # )
    # milestones: Mapped[List["Milestone"]] = relationship(
    #     "Milestone",
    #     back_populates="project",
    #     lazy="noload"
    # )

    def __repr__(self) -> str:
        """String representation of the Project model."""
        return f"<Project {self.name} (ID: {self.id})>"

    @property
    def is_active(self) -> bool:
        """Check if the project is active (not soft-deleted)."""
        return self.deleted_at is None

    @property
    def is_public(self) -> bool:
        """Check if the project is publicly visible."""
        return self.visibility == ProjectVisibility.PUBLIC.value

    @property
    def is_organization_visible(self) -> bool:
        """Check if the project is visible to the organization."""
        return self.visibility in [ProjectVisibility.ORGANIZATION.value, ProjectVisibility.PUBLIC.value]
