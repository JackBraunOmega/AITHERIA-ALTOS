"""
AITHERIA ALTOS - Auth Service Token Service
==========================================

This module provides functions for managing tokens in the Auth service, including:
- Token blocklist management (adding tokens to a blocklist, checking if a token is blacklisted)
- API token generation and validation
- Querying API tokens with pagination and filtering
- Creating, updating, and deleting API tokens

The token blocklist is stored in Redis for fast lookups and automatic expiration.
API tokens are stored in the database for persistence and auditability.
"""

import secrets
import string
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union

from fastapi import Depends, HTTPException, status
from loguru import logger
from passlib.context import CryptContext
from pydantic import UUID4
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.session import get_db
from app.models.api_token import APIToken
from app.schemas.token import APITokenCreate
from app.services.redis_service import get_redis_client

# Password context for hashing API tokens
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Prefix for token blocklist keys in Redis
TOKEN_BLOCKLIST_PREFIX = "token:blocklist:"

# API token prefix for distinguishing from other tokens
API_TOKEN_PREFIX = "at_"
API_TOKEN_LENGTH = 32  # Length of the token in characters (excluding prefix)


async def add_token_to_blocklist(token: str, expiry: Optional[int] = None) -> None:
    """
    Add a token to the blocklist.
    
    Blacklisted tokens are stored in Redis with an expiration time matching
    the token's original expiry time. This ensures that the blocklist doesn't
    grow indefinitely with expired tokens.
    
    Args:
        token: JWT token to blacklist
        expiry: Token expiry timestamp (Unix time). If None, a default expiry is used.
    """
    try:
        redis = await get_redis_client()
        
        # Generate a key for the blocklisted token
        # We use a hash of the token rather than the token itself for storage efficiency
        token_hash = pwd_context.hash(token)
        key = f"{TOKEN_BLOCKLIST_PREFIX}{token_hash}"
        
        # Calculate TTL (time to live) for the Redis key
        if expiry:
            # Convert expiry timestamp to seconds from now
            now = datetime.now().timestamp()
            ttl = max(1, int(expiry - now))  # Ensure at least 1 second TTL
        else:
            # Default TTL if no expiry provided (24 hours)
            ttl = 86400  # 24 hours in seconds
        
        # Store in Redis with expiration
        await redis.set(key, "1", ex=ttl)
        logger.debug(f"Token added to blocklist with TTL of {ttl} seconds")
    except Exception as e:
        logger.error(f"Failed to add token to blocklist: {e}")
        # In production, consider whether to raise this exception or handle silently
        # For now, we'll raise it to ensure proper error handling during development
        raise


async def is_token_blacklisted(token: str) -> bool:
    """
    Check if a token is in the blocklist.
    
    Args:
        token: JWT token to check
        
    Returns:
        True if the token is blacklisted, False otherwise
    """
    try:
        redis = await get_redis_client()
        
        # Generate the same key format used when blacklisting
        token_hash = pwd_context.hash(token)
        key = f"{TOKEN_BLOCKLIST_PREFIX}{token_hash}"
        
        # Check if the key exists in Redis
        exists = await redis.exists(key)
        return bool(exists)
    except Exception as e:
        logger.error(f"Failed to check token blocklist: {e}")
        # If we can't check the blocklist, assume the token is not blacklisted
        # This is a trade-off between security and availability
        return False


def generate_api_token() -> str:
    """
    Generate a secure random API token.
    
    The token consists of a prefix to identify it as an API token,
    followed by a random string of characters.
    
    Returns:
        Secure random API token string
    """
    # Define the character set for the token
    # We exclude easily confused characters like 0/O and 1/l/I
    alphabet = string.ascii_letters + string.digits
    alphabet = alphabet.replace('0', '').replace('O', '').replace('1', '').replace('l', '').replace('I', '')
    
    # Generate a random string
    random_part = ''.join(secrets.choice(alphabet) for _ in range(API_TOKEN_LENGTH))
    
    # Combine with prefix
    token = f"{API_TOKEN_PREFIX}{random_part}"
    
    return token


def hash_api_token(token: str) -> str:
    """
    Hash an API token for secure storage.
    
    Args:
        token: Raw API token
        
    Returns:
        Hashed API token
    """
    return pwd_context.hash(token)


def verify_api_token(token: str, hashed_token: str) -> bool:
    """
    Verify an API token against a hash.
    
    Args:
        token: Raw API token to verify
        hashed_token: Hashed token to compare against
        
    Returns:
        True if the token matches the hash, False otherwise
    """
    return pwd_context.verify(token, hashed_token)


async def create_api_token(
    db: AsyncSession,
    token_in: APITokenCreate,
    user_id: UUID4
) -> Tuple[APIToken, str]:
    """
    Create a new API token.
    
    This function generates a new API token, hashes it for storage,
    and creates a record in the database.
    
    Args:
        db: Database session
        token_in: API token creation data
        user_id: ID of the user who owns the token
        
    Returns:
        Tuple of (created token object, raw token string)
        
    Raises:
        ValueError: If token creation fails
    """
    # Generate a new token
    raw_token = generate_api_token()
    
    # Hash the token for storage
    hashed_token = hash_api_token(raw_token)
    
    # Create token record
    token = APIToken(
        name=token_in.name,
        description=token_in.description,
        token=hashed_token,
        scopes=token_in.scopes,
        user_id=user_id,
        expires_at=token_in.expires_at,
        is_active=True
    )
    
    # Save to database
    try:
        db.add(token)
        await db.commit()
        await db.refresh(token)
        
        logger.info(f"API token created for user {user_id}: {token.name}")
        return token, raw_token
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create API token: {e}")
        raise ValueError(f"Failed to create API token: {e}")


async def delete_api_token(
    db: AsyncSession,
    token: APIToken
) -> None:
    """
    Delete an API token.
    
    This function removes an API token from the database.
    
    Args:
        db: Database session
        token: API token to delete
        
    Raises:
        ValueError: If token deletion fails
    """
    try:
        await db.delete(token)
        await db.commit()
        
        logger.info(f"API token deleted: {token.name}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete API token: {e}")
        raise ValueError(f"Failed to delete API token: {e}")


async def get_api_token_by_id(
    db: AsyncSession,
    token_id: UUID4
) -> Optional[APIToken]:
    """
    Get an API token by ID.
    
    Args:
        db: Database session
        token_id: ID of the token to get
        
    Returns:
        API token if found, None otherwise
    """
    result = await db.execute(
        select(APIToken)
        .where(APIToken.id == token_id)
        .options(selectinload(APIToken.user))
    )
    return result.scalars().first()


async def get_api_token_by_token(
    db: AsyncSession,
    token: str
) -> Optional[APIToken]:
    """
    Get an API token by its raw token value.
    
    This function is used for token authentication.
    
    Args:
        db: Database session
        token: Raw API token
        
    Returns:
        API token if found and valid, None otherwise
    """
    # Get all tokens (inefficient but necessary since we can't query by hash directly)
    result = await db.execute(
        select(APIToken)
        .where(APIToken.is_active == True)
        .options(selectinload(APIToken.user))
    )
    
    tokens = result.scalars().all()
    
    # Check each token
    for db_token in tokens:
        if verify_api_token(token, db_token.token):
            # Check if token is expired
            if db_token.expires_at and db_token.expires_at < datetime.utcnow():
                logger.info(f"API token expired: {db_token.name}")
                return None
            
            # Update last used timestamp
            db_token.last_used_at = datetime.utcnow()
            db.add(db_token)
            await db.commit()
            await db.refresh(db_token)
            
            return db_token
    
    return None


async def get_user_api_tokens(
    db: AsyncSession,
    user_id: UUID4,
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None
) -> Tuple[List[APIToken], int]:
    """
    Get API tokens for a specific user with pagination and filtering.
    
    Args:
        db: Database session
        user_id: ID of the user
        skip: Number of tokens to skip (for pagination)
        limit: Maximum number of tokens to return
        is_active: Optional filter by active status
        
    Returns:
        Tuple of (list of API tokens, total count)
    """
    # Build query conditions
    conditions = [APIToken.user_id == user_id]
    
    if is_active is not None:
        conditions.append(APIToken.is_active == is_active)
    
    # Get total count
    count_query = select(func.count()).select_from(APIToken).where(and_(*conditions))
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Get tokens with pagination
    query = (
        select(APIToken)
        .where(and_(*conditions))
        .options(selectinload(APIToken.user))
        .order_by(APIToken.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    
    result = await db.execute(query)
    tokens = result.scalars().all()
    
    return tokens, total


async def get_all_api_tokens(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None
) -> Tuple[List[APIToken], int]:
    """
    Get all API tokens with pagination and filtering.
    
    This function is typically used by administrators to view all tokens
    across all users.
    
    Args:
        db: Database session
        skip: Number of tokens to skip (for pagination)
        limit: Maximum number of tokens to return
        is_active: Optional filter by active status
        
    Returns:
        Tuple of (list of API tokens, total count)
    """
    # Build query conditions
    conditions = []
    
    if is_active is not None:
        conditions.append(APIToken.is_active == is_active)
    
    # Get total count
    count_query = select(func.count()).select_from(APIToken)
    if conditions:
        count_query = count_query.where(and_(*conditions))
    
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Get tokens with pagination
    query = (
        select(APIToken)
        .options(selectinload(APIToken.user))
        .order_by(APIToken.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    
    if conditions:
        query = query.where(and_(*conditions))
    
    result = await db.execute(query)
    tokens = result.scalars().all()
    
    return tokens, total


async def validate_api_token_authentication(
    db: AsyncSession,
    token: str
) -> Optional[APIToken]:
    """
    Validate an API token for authentication.
    
    This function is used in the authentication process to validate
    an API token and return the associated token object if valid.
    
    Args:
        db: Database session
        token: Raw API token
        
    Returns:
        API token if valid, None otherwise
    """
    # Check if token has the correct prefix
    if not token.startswith(API_TOKEN_PREFIX):
        return None
    
    # Get token from database and validate
    api_token = await get_api_token_by_token(db, token)
    
    if not api_token:
        return None
    
    # Check if token is active
    if not api_token.is_active:
        logger.info(f"Attempt to use inactive API token: {api_token.name}")
        return None
    
    # Check if token is expired
    if api_token.expires_at and api_token.expires_at < datetime.utcnow():
        logger.info(f"Attempt to use expired API token: {api_token.name}")
        # Update token status to inactive
        api_token.is_active = False
        db.add(api_token)
        await db.commit()
        return None
    
    # Check if user is active
    if not api_token.user.is_active:
        logger.info(f"Attempt to use API token for inactive user: {api_token.user.email}")
        return None
    
    return api_token
