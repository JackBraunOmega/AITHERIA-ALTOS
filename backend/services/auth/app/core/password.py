"""
AITHERIA ALTOS - Auth Service Password Utilities
==============================================

This module provides utilities for password hashing and verification.
It is separated from the security module to prevent circular dependencies.

Usage:
    from app.core.password import get_password_hash, verify_password
"""

from passlib.context import CryptContext


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against

    Returns:
        True if the password matches the hash, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)
