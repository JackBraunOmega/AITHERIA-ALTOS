"""
AITHERIA ALTOS - Auth Service Configuration
==========================================

This module defines the configuration settings for the Auth service using Pydantic's
BaseSettings for automatic environment variable loading, validation, and type conversion.

Configuration priorities (highest to lowest):
1. Environment variables
2. .env file
3. Default values specified in this file

Usage:
    from app.core.config import settings
    
    database_url = settings.DATABASE_URL
    jwt_secret = settings.JWT_SECRET_KEY
"""

import secrets
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import AnyHttpUrl, EmailStr, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvironmentType(str, Enum):
    """Supported environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class Settings(BaseSettings):
    """
    Application settings with environment variable mapping.
    
    All settings can be overridden with environment variables.
    Example: `API_V1_STR=/api/v1 uvicorn app.main:app`
    """
    # Model config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )
    
    # API settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AITHERIA ALTOS Auth Service"
    VERSION: str = "0.1.0"
    
    # Environment settings
    ENVIRONMENT: EnvironmentType = EnvironmentType.DEVELOPMENT
    DEBUG: bool = True
    
    # CORS settings - list of origins that can access the API
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []
    
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # Database settings
    DATABASE_URL: PostgresDsn = "postgresql+asyncpg://postgres:postgres@localhost:5432/aitheria_auth"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_ECHO: bool = False
    
    # Security settings
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    
    # JWT settings
    JWT_SECRET_KEY: str = secrets.token_urlsafe(32)
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Password hashing
    BCRYPT_ROUNDS: int = 12  # Higher is more secure but slower
    
    # Redis settings for rate limiting and session storage
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_POOL_SIZE: int = 10
    
    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT_LIMIT: int = 100  # requests
    RATE_LIMIT_DEFAULT_PERIOD: int = 60  # seconds
    
    # First superuser
    FIRST_SUPERUSER: Optional[EmailStr] = None
    FIRST_SUPERUSER_PASSWORD: Optional[str] = None
    
    # OAuth2 providers
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_DISCOVERY_URL: str = "https://accounts.google.com/.well-known/openid-configuration"
    
    # ORCID OAuth settings
    ORCID_CLIENT_ID: Optional[str] = None
    ORCID_CLIENT_SECRET: Optional[str] = None
    ORCID_AUTHORIZE_URL: str = "https://orcid.org/oauth/authorize"
    ORCID_TOKEN_URL: str = "https://orcid.org/oauth/token"
    
    # Application URLs
    SERVER_HOST: AnyHttpUrl = "http://localhost:8000"
    FRONTEND_URL: AnyHttpUrl = "http://localhost:3000"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "simple"  # "simple" or "json"
    
    # Security headers
    SECURITY_HEADERS: bool = True
    
    # Session settings
    SESSION_COOKIE_NAME: str = "aitheria_session"
    SESSION_COOKIE_SECURE: bool = False  # Set to True in production
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "lax"  # "lax", "strict", or "none"
    
    # Feature flags
    ENABLE_MFA: bool = False  # Multi-factor authentication
    ENABLE_SSO: bool = True   # Single sign-on
    ENABLE_SOCIAL_LOGIN: bool = True  # Social login (Google, etc.)
    
    # Audit logging
    ENABLE_AUDIT_LOG: bool = True
    
    @property
    def access_token_expires(self) -> timedelta:
        """Get the access token expiration time as a timedelta."""
        return timedelta(minutes=self.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    @property
    def refresh_token_expires(self) -> timedelta:
        """Get the refresh token expiration time as a timedelta."""
        return timedelta(days=self.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    
    @property
    def is_development(self) -> bool:
        """Check if the current environment is development."""
        return self.ENVIRONMENT == EnvironmentType.DEVELOPMENT
    
    @property
    def is_production(self) -> bool:
        """Check if the current environment is production."""
        return self.ENVIRONMENT == EnvironmentType.PRODUCTION
    
    @property
    def is_test(self) -> bool:
        """Check if the current environment is test."""
        return self.ENVIRONMENT == EnvironmentType.TEST
    
    def get_environment_specific_settings(self) -> Dict[str, Any]:
        """
        Get environment-specific settings overrides.
        
        Returns:
            Dict of settings that are specific to the current environment.
        """
        env_settings = {
            EnvironmentType.DEVELOPMENT: {
                "DEBUG": True,
                "DATABASE_ECHO": True,
                "LOG_LEVEL": "DEBUG",
            },
            EnvironmentType.STAGING: {
                "DEBUG": False,
                "SESSION_COOKIE_SECURE": True,
                "RATE_LIMIT_DEFAULT_LIMIT": 200,
            },
            EnvironmentType.PRODUCTION: {
                "DEBUG": False,
                "SESSION_COOKIE_SECURE": True,
                "BCRYPT_ROUNDS": 14,  # Higher security for production
                "JWT_ACCESS_TOKEN_EXPIRE_MINUTES": 15,  # Shorter token lifetime
                "RATE_LIMIT_ENABLED": True,
                "RATE_LIMIT_DEFAULT_LIMIT": 300,
                "SECURITY_HEADERS": True,
            },
            EnvironmentType.TEST: {
                "DEBUG": True,
                "DATABASE_ECHO": True,
                "BCRYPT_ROUNDS": 4,  # Lower for faster tests
                "JWT_ACCESS_TOKEN_EXPIRE_MINUTES": 60,  # Longer for testing
                "RATE_LIMIT_ENABLED": False,
            },
        }
        
        return env_settings.get(self.ENVIRONMENT, {})
    
    def __init__(self, **data: Any):
        """Initialize settings with environment-specific overrides."""
        super().__init__(**data)
        
        # Apply environment-specific settings
        env_specific = self.get_environment_specific_settings()
        for key, value in env_specific.items():
            setattr(self, key, value)


# Create settings instance
settings = Settings()
