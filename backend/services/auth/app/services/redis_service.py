"""
AITHERIA ALTOS - Auth Service Redis Service
==========================================

This module provides functions for interacting with Redis in the Auth service, including:
- Establishing and managing Redis connections
- Connection pooling for efficient Redis usage
- Health checks for Redis connectivity
- Helper functions for common Redis operations
- Specialized functions for token management and rate limiting

Redis is used for:
- Token blocklisting (storing revoked tokens)
- Rate limiting
- Session storage
- Caching frequently accessed data
"""

import asyncio
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from contextlib import asynccontextmanager

import aioredis
from aioredis import Redis
from loguru import logger

from app.core.config import settings

# Global Redis connection pool
_redis_pool: Optional[Redis] = None


async def get_redis_client() -> Redis:
    """
    Get a Redis client from the connection pool.
    
    This function creates a Redis connection pool if one doesn't exist,
    or returns the existing pool. This ensures efficient reuse of connections.
    
    Returns:
        Redis client from the connection pool
        
    Raises:
        ConnectionError: If Redis connection fails
    """
    global _redis_pool
    
    if _redis_pool is None:
        try:
            # Create Redis connection pool
            _redis_pool = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                pool_size=settings.REDIS_POOL_SIZE,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )
            logger.info(f"Connected to Redis at {settings.REDIS_URL}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise ConnectionError(f"Failed to connect to Redis: {e}")
    
    return _redis_pool


@asynccontextmanager
async def redis_client() -> Redis:
    """
    Context manager for getting a Redis client.
    
    This function provides a Redis client that is automatically
    released back to the pool when the context exits.
    
    Yields:
        Redis client from the connection pool
        
    Example:
        async with redis_client() as redis:
            await redis.set("key", "value")
    """
    client = await get_redis_client()
    try:
        yield client
    except Exception as e:
        logger.error(f"Redis operation failed: {e}")
        raise


async def close_redis_connections() -> None:
    """
    Close all Redis connections.
    
    This function should be called when the application is shutting down.
    """
    global _redis_pool
    
    if _redis_pool is not None:
        logger.info("Closing Redis connections...")
        await _redis_pool.close()
        _redis_pool = None
        logger.info("Redis connections closed")


async def check_redis_connection() -> bool:
    """
    Check if Redis connection is working.
    
    This function is used for health checks to verify that the Redis
    connection is working properly.
    
    Returns:
        True if connection is working, False otherwise
    """
    try:
        redis = await get_redis_client()
        await redis.ping()
        return True
    except Exception as e:
        logger.error(f"Redis connection check failed: {e}")
        return False


async def set_with_expiry(key: str, value: Any, expiry_seconds: int) -> bool:
    """
    Set a key-value pair with expiration.
    
    Args:
        key: Redis key
        value: Value to store
        expiry_seconds: Time to live in seconds
        
    Returns:
        True if successful, False otherwise
    """
    try:
        redis = await get_redis_client()
        await redis.set(key, value, ex=expiry_seconds)
        return True
    except Exception as e:
        logger.error(f"Failed to set Redis key {key}: {e}")
        return False


async def get_value(key: str) -> Optional[str]:
    """
    Get a value from Redis.
    
    Args:
        key: Redis key
        
    Returns:
        Value if key exists, None otherwise
    """
    try:
        redis = await get_redis_client()
        return await redis.get(key)
    except Exception as e:
        logger.error(f"Failed to get Redis key {key}: {e}")
        return None


async def delete_key(key: str) -> bool:
    """
    Delete a key from Redis.
    
    Args:
        key: Redis key
        
    Returns:
        True if key was deleted, False otherwise
    """
    try:
        redis = await get_redis_client()
        result = await redis.delete(key)
        return result > 0
    except Exception as e:
        logger.error(f"Failed to delete Redis key {key}: {e}")
        return False


async def key_exists(key: str) -> bool:
    """
    Check if a key exists in Redis.
    
    Args:
        key: Redis key
        
    Returns:
        True if key exists, False otherwise
    """
    try:
        redis = await get_redis_client()
        return bool(await redis.exists(key))
    except Exception as e:
        logger.error(f"Failed to check if Redis key {key} exists: {e}")
        return False


async def increment_counter(key: str, expiry_seconds: Optional[int] = None) -> int:
    """
    Increment a counter in Redis.
    
    This function is useful for rate limiting and counting events.
    
    Args:
        key: Redis key
        expiry_seconds: Optional time to live in seconds
        
    Returns:
        New counter value
    """
    try:
        redis = await get_redis_client()
        value = await redis.incr(key)
        
        # Set expiry if provided and key is new (value == 1)
        if expiry_seconds is not None and value == 1:
            await redis.expire(key, expiry_seconds)
        
        return value
    except Exception as e:
        logger.error(f"Failed to increment Redis counter {key}: {e}")
        return 0


async def add_to_set(key: str, *values: str, expiry_seconds: Optional[int] = None) -> int:
    """
    Add values to a Redis set.
    
    Args:
        key: Redis key
        values: Values to add to the set
        expiry_seconds: Optional time to live in seconds
        
    Returns:
        Number of values added to the set
    """
    try:
        redis = await get_redis_client()
        result = await redis.sadd(key, *values)
        
        # Set expiry if provided
        if expiry_seconds is not None:
            await redis.expire(key, expiry_seconds)
        
        return result
    except Exception as e:
        logger.error(f"Failed to add values to Redis set {key}: {e}")
        return 0


async def is_member_of_set(key: str, value: str) -> bool:
    """
    Check if a value is a member of a Redis set.
    
    Args:
        key: Redis key
        value: Value to check
        
    Returns:
        True if value is a member of the set, False otherwise
    """
    try:
        redis = await get_redis_client()
        return bool(await redis.sismember(key, value))
    except Exception as e:
        logger.error(f"Failed to check if value is member of Redis set {key}: {e}")
        return False


async def get_set_members(key: str) -> Set[str]:
    """
    Get all members of a Redis set.
    
    Args:
        key: Redis key
        
    Returns:
        Set of members
    """
    try:
        redis = await get_redis_client()
        result = await redis.smembers(key)
        return result
    except Exception as e:
        logger.error(f"Failed to get members of Redis set {key}: {e}")
        return set()


async def add_to_sorted_set(key: str, score: float, value: str, expiry_seconds: Optional[int] = None) -> int:
    """
    Add a value to a Redis sorted set with a score.
    
    Args:
        key: Redis key
        score: Score for sorting
        value: Value to add
        expiry_seconds: Optional time to live in seconds
        
    Returns:
        Number of values added to the sorted set
    """
    try:
        redis = await get_redis_client()
        result = await redis.zadd(key, {value: score})
        
        # Set expiry if provided
        if expiry_seconds is not None:
            await redis.expire(key, expiry_seconds)
        
        return result
    except Exception as e:
        logger.error(f"Failed to add value to Redis sorted set {key}: {e}")
        return 0


async def get_sorted_set_range(key: str, start: int = 0, end: int = -1, desc: bool = False) -> List[str]:
    """
    Get a range of values from a Redis sorted set.
    
    Args:
        key: Redis key
        start: Start index
        end: End index (-1 means all elements)
        desc: Whether to sort in descending order
        
    Returns:
        List of values in the specified range
    """
    try:
        redis = await get_redis_client()
        if desc:
            result = await redis.zrevrange(key, start, end)
        else:
            result = await redis.zrange(key, start, end)
        return result
    except Exception as e:
        logger.error(f"Failed to get range from Redis sorted set {key}: {e}")
        return []


async def set_hash_field(key: str, field: str, value: str, expiry_seconds: Optional[int] = None) -> bool:
    """
    Set a field in a Redis hash.
    
    Args:
        key: Redis key
        field: Hash field
        value: Value to set
        expiry_seconds: Optional time to live in seconds
        
    Returns:
        True if successful, False otherwise
    """
    try:
        redis = await get_redis_client()
        await redis.hset(key, field, value)
        
        # Set expiry if provided
        if expiry_seconds is not None:
            await redis.expire(key, expiry_seconds)
        
        return True
    except Exception as e:
        logger.error(f"Failed to set field {field} in Redis hash {key}: {e}")
        return False


async def get_hash_field(key: str, field: str) -> Optional[str]:
    """
    Get a field from a Redis hash.
    
    Args:
        key: Redis key
        field: Hash field
        
    Returns:
        Field value if it exists, None otherwise
    """
    try:
        redis = await get_redis_client()
        return await redis.hget(key, field)
    except Exception as e:
        logger.error(f"Failed to get field {field} from Redis hash {key}: {e}")
        return None


async def get_hash_all(key: str) -> Dict[str, str]:
    """
    Get all fields and values from a Redis hash.
    
    Args:
        key: Redis key
        
    Returns:
        Dictionary of field-value pairs
    """
    try:
        redis = await get_redis_client()
        result = await redis.hgetall(key)
        return result
    except Exception as e:
        logger.error(f"Failed to get all fields from Redis hash {key}: {e}")
        return {}


async def set_rate_limit(key: str, limit: int, period: int) -> Tuple[int, bool]:
    """
    Implement rate limiting using Redis.
    
    This function increments a counter for the given key and checks if
    the rate limit has been exceeded.
    
    Args:
        key: Redis key (usually includes user ID or IP)
        limit: Maximum number of requests allowed
        period: Time period in seconds
        
    Returns:
        Tuple of (current count, whether limit is exceeded)
    """
    try:
        redis = await get_redis_client()
        current = await redis.incr(key)
        
        # Set expiry if this is a new key
        if current == 1:
            await redis.expire(key, period)
        
        # Get remaining TTL
        ttl = await redis.ttl(key)
        if ttl < 0:
            # Key exists but has no TTL, set it
            await redis.expire(key, period)
        
        return current, current > limit
    except Exception as e:
        logger.error(f"Failed to check rate limit for {key}: {e}")
        # If Redis fails, don't rate limit
        return 0, False


async def get_rate_limit_remaining(key: str, limit: int) -> Tuple[int, int]:
    """
    Get remaining requests and reset time for rate limiting.
    
    Args:
        key: Redis key
        limit: Maximum number of requests allowed
        
    Returns:
        Tuple of (remaining requests, seconds until reset)
    """
    try:
        redis = await get_redis_client()
        
        # Get current count
        count = await redis.get(key)
        current = int(count) if count else 0
        
        # Get TTL
        ttl = await redis.ttl(key)
        if ttl < 0:
            # Key doesn't exist or has no TTL
            return limit, 0
        
        remaining = max(0, limit - current)
        return remaining, ttl
    except Exception as e:
        logger.error(f"Failed to get rate limit info for {key}: {e}")
        # If Redis fails, assume no rate limiting
        return limit, 0
