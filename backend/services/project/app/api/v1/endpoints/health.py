"""
AITHERIA ALTOS - Project Service Health Endpoints
=================================================

This module implements health check endpoints for the Project service, providing
detailed information about the service's health and its dependencies.

These endpoints are used by monitoring systems, load balancers, and
orchestration platforms to determine the service's availability and readiness.
"""

import os
import platform
import time
from datetime import datetime
from typing import Any, Dict, Optional

import psutil
from fastapi import APIRouter, Depends, Response, status
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db

# Global variable to store service start time
SERVICE_START_TIME = time.time()

router = APIRouter()


@router.get("/", summary="Get service health status")
async def health_check(
    response: Response,
    db: AsyncSession = Depends(get_db),
    detailed: bool = False,
) -> Dict[str, Any]:
    """
    Get health status of the Project service and its dependencies.
    
    This endpoint provides information about the service's operational status,
    including database connectivity and system metrics.
    It's used by monitoring systems and load balancers to determine service health.
    
    Args:
        response: FastAPI response object to set status code
        db: Database session
        detailed: Whether to include detailed system metrics
        
    Returns:
        Health status information
    """
    health_data = {
        "status": "healthy",
        "service": "project",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    # Check database connection
    db_status = "healthy"
    db_details = {}
    try:
        # Execute a simple query to check database connectivity
        result = await db.execute(text("SELECT 1"))
        await result.fetchone()
        db_details["connected"] = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
        db_details["connected"] = False
        db_details["error"] = str(e)
        health_data["status"] = "unhealthy"
    
    health_data["dependencies"] = {
        "database": {
            "status": db_status,
            "details": db_details
        }
    }
    
    # Add uptime information
    uptime_seconds = time.time() - SERVICE_START_TIME
    health_data["uptime"] = {
        "seconds": int(uptime_seconds),
        "formatted": format_uptime(uptime_seconds)
    }
    
    # Add detailed system metrics if requested
    if detailed:
        health_data["system"] = get_system_metrics()
    
    # Set response status code based on health status
    if health_data["status"] != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    return health_data


@router.get("/liveness", summary="Liveness probe for container orchestration")
async def liveness_probe() -> Dict[str, str]:
    """
    Simple liveness probe for Kubernetes/container orchestration.
    
    This endpoint provides a lightweight check that the service is running
    and can respond to requests. It doesn't check dependencies like the database.
    
    Returns:
        Simple status message
    """
    return {"status": "alive"}


@router.get("/readiness", summary="Readiness probe for container orchestration")
async def readiness_probe(db: AsyncSession = Depends(get_db)) -> Dict[str, str]:
    """
    Readiness probe for Kubernetes/container orchestration.
    
    This endpoint checks if the service is ready to handle requests,
    including checking database connectivity.
    
    Args:
        db: Database session
        
    Returns:
        Readiness status message
    """
    try:
        # Check database connection
        result = await db.execute(text("SELECT 1"))
        await result.fetchone()
        
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {"status": "not ready", "reason": str(e)}


def format_uptime(seconds: float) -> str:
    """
    Format uptime in seconds to a human-readable string.
    
    Args:
        seconds: Uptime in seconds
        
    Returns:
        Formatted uptime string (e.g., "3 days, 2 hours, 1 minute, 30 seconds")
    """
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds > 0 or not parts:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    
    return ", ".join(parts)


def get_system_metrics() -> Dict[str, Any]:
    """
    Get system metrics like CPU, memory, and disk usage.
    
    Returns:
        Dictionary of system metrics
    """
    metrics = {
        "cpu": {
            "percent": psutil.cpu_percent(interval=0.1),
            "count": psutil.cpu_count(),
        },
        "memory": {
            "total": psutil.virtual_memory().total,
            "available": psutil.virtual_memory().available,
            "percent": psutil.virtual_memory().percent,
            "used": psutil.virtual_memory().used,
        },
        "disk": {
            "total": psutil.disk_usage('/').total,
            "free": psutil.disk_usage('/').free,
            "percent": psutil.disk_usage('/').percent,
            "used": psutil.disk_usage('/').used,
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "python": platform.python_version(),
        },
        "process": {
            "pid": os.getpid(),
            "memory_percent": psutil.Process(os.getpid()).memory_percent(),
            "cpu_percent": psutil.Process(os.getpid()).cpu_percent(interval=0.1),
            "threads": len(psutil.Process(os.getpid()).threads()),
        }
    }
    
    return metrics
