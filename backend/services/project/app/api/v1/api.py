"""
AITHERIA ALTOS - Project Service API Router
==========================================

This module defines the main API router for the Project service, organizing
all API endpoints into logical groups by feature. It serves as the central
point for registering and organizing all API routes in the service.

The router structure follows RESTful principles and groups endpoints by resource:
- /projects: Project management endpoints
- /health: Health check endpoint
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    projects,
    health,
)

# Create main API router
api_router = APIRouter()

# Include feature-specific routers with appropriate prefixes
api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
api_router.include_router(health.router, prefix="/health", tags=["Health"])

# Additional endpoints can be included here as the service grows
