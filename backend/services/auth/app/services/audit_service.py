"""
AITHERIA ALTOS - Auth Service Audit Service
==========================================

This module provides functions for recording and querying audit logs in the Auth service.
Audit logs are crucial for compliance with FDA 21 CFR Part 11 and HIPAA regulations,
providing an immutable record of all system activities.

Features:
- Recording user actions with detailed context
- Querying audit logs with filtering and pagination
- Support for compliance reporting and forensic analysis
- Immutable audit trail for regulatory compliance
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import Depends
from loguru import logger
from pydantic import UUID4
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User


async def create_audit_log(
    db: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    user_id: Optional[UUID4] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    status: str = "success",
    error_message: Optional[str] = None,
) -> AuditLog:
    """
    Create an audit log entry.
    
    This function records a user action in the audit log, providing a detailed
    record of what happened, when, by whom, and with what result.
    
    Args:
        db: Database session
        action: Type of action performed (create, read, update, delete, login, etc.)
        resource_type: Type of resource affected (user, project, experiment, etc.)
        resource_id: Optional ID of the specific resource affected
        user_id: Optional ID of the user who performed the action
        ip_address: Optional IP address from which the action was performed
        user_agent: Optional user agent (browser/client) information
        details: Optional additional details about the action in JSON format
        status: Outcome of the action (success, failure, error)
        error_message: Optional error message if the action failed
        
    Returns:
        Created audit log entry
        
    Raises:
        ValueError: If audit log creation fails
    """
    try:
        # Create audit log entry
        audit_log = AuditLog(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            status=status,
            error_message=error_message,
        )
        
        # Save to database
        db.add(audit_log)
        await db.flush()
        
        logger.debug(
            f"Audit log created: {action} on {resource_type}"
            f"{f':{resource_id}' if resource_id else ''} by {user_id}"
        )
        
        return audit_log
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")
        # Don't raise exception for audit logs to avoid disrupting normal operation
        # But return None to indicate failure
        return None


async def get_audit_logs(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    user_id: Optional[UUID4] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    action: Optional[str] = None,
    status: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    ip_address: Optional[str] = None,
) -> Tuple[List[AuditLog], int]:
    """
    Get audit logs with filtering and pagination.
    
    This function retrieves audit logs from the database with various filtering options
    and pagination support.
    
    Args:
        db: Database session
        skip: Number of logs to skip (for pagination)
        limit: Maximum number of logs to return
        user_id: Optional filter by user ID
        resource_type: Optional filter by resource type
        resource_id: Optional filter by resource ID
        action: Optional filter by action type
        status: Optional filter by status
        start_time: Optional filter by start time
        end_time: Optional filter by end time
        ip_address: Optional filter by IP address
        
    Returns:
        Tuple of (list of audit logs, total count)
    """
    # Build query conditions
    conditions = []
    
    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    
    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type)
    
    if resource_id:
        conditions.append(AuditLog.resource_id == resource_id)
    
    if action:
        conditions.append(AuditLog.action == action)
    
    if status:
        conditions.append(AuditLog.status == status)
    
    if start_time:
        conditions.append(AuditLog.timestamp >= start_time)
    
    if end_time:
        conditions.append(AuditLog.timestamp <= end_time)
    
    if ip_address:
        conditions.append(AuditLog.ip_address == ip_address)
    
    # Get total count
    count_query = select(func.count()).select_from(AuditLog)
    if conditions:
        count_query = count_query.where(and_(*conditions))
    
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Get audit logs with pagination
    query = (
        select(AuditLog)
        .options(selectinload(AuditLog.user))
        .order_by(desc(AuditLog.timestamp))
        .offset(skip)
        .limit(limit)
    )
    
    if conditions:
        query = query.where(and_(*conditions))
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return logs, total


async def get_audit_log_by_id(
    db: AsyncSession,
    log_id: UUID4,
) -> Optional[AuditLog]:
    """
    Get a specific audit log entry by ID.
    
    Args:
        db: Database session
        log_id: ID of the audit log to retrieve
        
    Returns:
        Audit log if found, None otherwise
    """
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.id == log_id)
        .options(selectinload(AuditLog.user))
    )
    return result.scalars().first()


async def get_user_action_history(
    db: AsyncSession,
    user_id: UUID4,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[AuditLog], int]:
    """
    Get the action history for a specific user.
    
    This function retrieves all audit logs for a specific user,
    ordered by timestamp (most recent first).
    
    Args:
        db: Database session
        user_id: ID of the user
        skip: Number of logs to skip (for pagination)
        limit: Maximum number of logs to return
        
    Returns:
        Tuple of (list of audit logs, total count)
    """
    return await get_audit_logs(
        db=db,
        skip=skip,
        limit=limit,
        user_id=user_id,
    )


async def get_resource_action_history(
    db: AsyncSession,
    resource_type: str,
    resource_id: str,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[AuditLog], int]:
    """
    Get the action history for a specific resource.
    
    This function retrieves all audit logs for a specific resource,
    ordered by timestamp (most recent first).
    
    Args:
        db: Database session
        resource_type: Type of resource (user, project, experiment, etc.)
        resource_id: ID of the resource
        skip: Number of logs to skip (for pagination)
        limit: Maximum number of logs to return
        
    Returns:
        Tuple of (list of audit logs, total count)
    """
    return await get_audit_logs(
        db=db,
        skip=skip,
        limit=limit,
        resource_type=resource_type,
        resource_id=resource_id,
    )


async def get_action_summary(
    db: AsyncSession,
    start_time: datetime,
    end_time: datetime,
) -> Dict[str, int]:
    """
    Get a summary of actions performed in a time period.
    
    This function returns a count of each action type performed
    within the specified time period.
    
    Args:
        db: Database session
        start_time: Start of the time period
        end_time: End of the time period
        
    Returns:
        Dictionary mapping action types to counts
    """
    query = (
        select(AuditLog.action, func.count(AuditLog.id))
        .where(
            and_(
                AuditLog.timestamp >= start_time,
                AuditLog.timestamp <= end_time,
            )
        )
        .group_by(AuditLog.action)
    )
    
    result = await db.execute(query)
    summary = {action: count for action, count in result.all()}
    
    return summary


async def get_recent_failed_actions(
    db: AsyncSession,
    limit: int = 10,
) -> List[AuditLog]:
    """
    Get recent failed actions.
    
    This function retrieves the most recent failed actions,
    which is useful for monitoring and alerting.
    
    Args:
        db: Database session
        limit: Maximum number of logs to return
        
    Returns:
        List of failed audit logs
    """
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.status == "failure")
        .options(selectinload(AuditLog.user))
        .order_by(desc(AuditLog.timestamp))
        .limit(limit)
    )
    return result.scalars().all()


async def get_user_login_history(
    db: AsyncSession,
    user_id: UUID4,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[AuditLog], int]:
    """
    Get login history for a specific user.
    
    This function retrieves all login attempts (successful and failed)
    for a specific user.
    
    Args:
        db: Database session
        user_id: ID of the user
        skip: Number of logs to skip (for pagination)
        limit: Maximum number of logs to return
        
    Returns:
        Tuple of (list of audit logs, total count)
    """
    return await get_audit_logs(
        db=db,
        skip=skip,
        limit=limit,
        user_id=user_id,
        action=or_(AuditLog.action == "login_success", AuditLog.action == "login_failed"),
    )


async def search_audit_logs(
    db: AsyncSession,
    search_term: str,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[AuditLog], int]:
    """
    Search audit logs for a specific term.
    
    This function searches for audit logs that match the search term
    in various fields.
    
    Args:
        db: Database session
        search_term: Term to search for
        skip: Number of logs to skip (for pagination)
        limit: Maximum number of logs to return
        
    Returns:
        Tuple of (list of matching audit logs, total count)
    """
    # Build search condition
    search_condition = or_(
        AuditLog.action.ilike(f"%{search_term}%"),
        AuditLog.resource_type.ilike(f"%{search_term}%"),
        AuditLog.resource_id.ilike(f"%{search_term}%"),
        AuditLog.status.ilike(f"%{search_term}%"),
        AuditLog.error_message.ilike(f"%{search_term}%"),
    )
    
    # Get total count
    count_query = select(func.count()).select_from(AuditLog).where(search_condition)
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Get matching audit logs with pagination
    query = (
        select(AuditLog)
        .where(search_condition)
        .options(selectinload(AuditLog.user))
        .order_by(desc(AuditLog.timestamp))
        .offset(skip)
        .limit(limit)
    )
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return logs, total


async def export_audit_logs(
    db: AsyncSession,
    start_time: datetime,
    end_time: datetime,
    resource_type: Optional[str] = None,
    action: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Export audit logs for compliance reporting.
    
    This function retrieves audit logs within a time period for export
    to compliance reports or external systems.
    
    Args:
        db: Database session
        start_time: Start of the time period
        end_time: End of the time period
        resource_type: Optional filter by resource type
        action: Optional filter by action type
        
    Returns:
        List of audit logs as dictionaries
    """
    # Build query conditions
    conditions = [
        AuditLog.timestamp >= start_time,
        AuditLog.timestamp <= end_time,
    ]
    
    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type)
    
    if action:
        conditions.append(AuditLog.action == action)
    
    # Get audit logs
    query = (
        select(AuditLog)
        .where(and_(*conditions))
        .options(selectinload(AuditLog.user))
        .order_by(AuditLog.timestamp)
    )
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    # Convert to dictionaries for export
    export_data = []
    for log in logs:
        log_dict = log.to_dict()
        
        # Add user information if available
        if log.user:
            log_dict["user_email"] = log.user.email
            log_dict["user_name"] = log.user.full_name
        
        export_data.append(log_dict)
    
    return export_data


async def get_compliance_report(
    db: AsyncSession,
    start_time: datetime,
    end_time: datetime,
) -> Dict[str, Any]:
    """
    Generate a compliance report for FDA 21 CFR Part 11 and HIPAA.
    
    This function generates a summary report of audit logs for compliance purposes,
    including counts of different action types, user activities, and system events.
    
    Args:
        db: Database session
        start_time: Start of the reporting period
        end_time: End of the reporting period
        
    Returns:
        Dictionary containing compliance report data
    """
    # Get all audit logs in the period
    logs, total = await get_audit_logs(
        db=db,
        skip=0,
        limit=10000,  # Large limit to get all logs
        start_time=start_time,
        end_time=end_time,
    )
    
    # Count actions by type
    action_counts = {}
    for log in logs:
        action_counts[log.action] = action_counts.get(log.action, 0) + 1
    
    # Count actions by resource type
    resource_counts = {}
    for log in logs:
        resource_counts[log.resource_type] = resource_counts.get(log.resource_type, 0) + 1
    
    # Count actions by status
    status_counts = {}
    for log in logs:
        status_counts[log.status] = status_counts.get(log.status, 0) + 1
    
    # Count actions by user
    user_counts = {}
    for log in logs:
        if log.user_id:
            user_id_str = str(log.user_id)
            user_counts[user_id_str] = user_counts.get(user_id_str, 0) + 1
    
    # Generate report
    report = {
        "period_start": start_time.isoformat(),
        "period_end": end_time.isoformat(),
        "total_events": total,
        "action_counts": action_counts,
        "resource_counts": resource_counts,
        "status_counts": status_counts,
        "user_counts": user_counts,
        "failed_actions": len([log for log in logs if log.status == "failure"]),
        "system_events": len([log for log in logs if log.user_id is None]),
    }
    
    return report
