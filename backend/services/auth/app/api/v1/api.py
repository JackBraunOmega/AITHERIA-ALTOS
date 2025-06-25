"""
AITHERIA ALTOS - Auth Service API Router
=======================================

This module defines the main API router for the Auth service, organizing
all API endpoints into logical groups by feature. It serves as the central
point for registering and organizing all API routes in the service.

The router structure follows RESTful principles and groups endpoints by resource:
- /auth: Authentication endpoints (login, register, refresh token)
- /users: User management endpoints
- /roles: Role management endpoints
- /permissions: Permission management endpoints
- /organizations: Organization management endpoints
- /tokens: API token management endpoints
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    users,
    roles,
    permissions,
    organizations,
    tokens,
    health,
)

# Create main API router
api_router = APIRouter()

# Include feature-specific routers with appropriate prefixes
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(roles.router, prefix="/roles", tags=["Roles"])
api_router.include_router(permissions.router, prefix="/permissions", tags=["Permissions"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["Organizations"])
api_router.include_router(tokens.router, prefix="/tokens", tags=["API Tokens"])
api_router.include_router(health.router, prefix="/health", tags=["Health"])

# Additional endpoints can be included here as the service grows
