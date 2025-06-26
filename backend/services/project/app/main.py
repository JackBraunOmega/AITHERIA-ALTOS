"""
AITHERIA ALTOS - Project Service
===============================

Main application entry point for the Project microservice.
This service handles the management of research projects, including
project creation, updates, deletion, and searching.

Features:
- Project CRUD operations
- Project versioning and history tracking
- Team collaboration within projects
"""

import time
from contextlib import asynccontextmanager
import os
from typing import Any, Dict, List

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
import uvicorn

from app.api.v1.api import api_router
from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import async_session_maker, engine

# Setup logging
logger.remove()
logger.add(
    os.path.join("logs", "project_service.log"),
    rotation="20 MB",
    retention="1 week",
    level="INFO",
    backtrace=True,
    diagnose=True,
)
logger.add(lambda msg: print(msg, end=""), level="INFO", colorize=True)


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting Project Service...")
    
    # Initialize database
    try:
        logger.info("Initializing database...")
        await init_db(engine)
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
    
    logger.info("Project Service startup complete")
    yield
    
    # Shutdown
    logger.info("Shutting down Project Service...")
    # Close any connections or resources
    logger.info("Project Service shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="""
    AITHERIA ALTOS Project Service API.
    
    This service handles the management of research projects for the AITHERIA ALTOS platform.
    """,
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Request ID middleware
@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next):
    """Add a unique request ID to each request for tracing."""
    request_id = request.headers.get("X-Request-ID", f"req-{time.time()}")
    request.state.request_id = request_id
    
    # Add request ID to logger context
    with logger.contextualize(request_id=request_id):
        logger.debug(f"Request: {request.method} {request.url.path}")
        
        # Process the request and catch any exceptions
        try:
            start_time = time.time()
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # Add processing time and request ID headers to response
            response.headers["X-Process-Time"] = str(process_time)
            response.headers["X-Request-ID"] = request_id
            
            logger.debug(f"Response: {response.status_code} (took {process_time:.4f}s)")
            return response
        except Exception as e:
            logger.exception(f"Unhandled exception: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"},
            )

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        dict: Health status of the service and its dependencies
    """
    health_data = {
        "status": "healthy",
        "service": "project",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": time.time(),
        "dependencies": {
            "database": "healthy",  # This should be a real check in production
        }
    }
    
    # In a real implementation, we would check database connectivity
    try:
        # Perform a simple database query using async session
        from sqlalchemy import text  # local import to avoid unnecessary global dependency
        async with async_session_maker() as db:
            await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_data["status"] = "unhealthy"
        health_data["dependencies"]["database"] = "unhealthy"
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=health_data)
    
    return health_data

# Root endpoint with redirect to docs
@app.get("/", include_in_schema=False)
async def root():
    """Redirect root endpoint to API documentation."""
    return {"message": "Project Service API", "docs": "/docs"}

# Error handlers
@app.exception_handler(status.HTTP_404_NOT_FOUND)
async def not_found_handler(request: Request, exc):
    """Handle 404 Not Found errors."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "The requested resource was not found"},
    )

@app.exception_handler(status.HTTP_500_INTERNAL_SERVER_ERROR)
async def server_error_handler(request: Request, exc):
    """Handle 500 Internal Server Error."""
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )

# Main execution
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=settings.DEBUG,
        log_level="info",
    )
