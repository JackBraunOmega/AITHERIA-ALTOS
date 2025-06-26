"""
AITHERIA ALTOS - Project Service Configuration
=============================================

This module defines the configuration settings for the Project service using Pydantic's
BaseSettings for automatic environment variable loading, validation, and type conversion.

Configuration priorities (highest to lowest):
1. Environment variables
2. .env file
3. Default values specified in this file

Usage:
    from app.core.config import settings
    
    database_url = settings.DATABASE_URL
"""

import secrets
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import AnyHttpUrl, PostgresDsn, field_validator
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
    PROJECT_NAME: str = "AITHERIA ALTOS Project Service"
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
    DATABASE_URL: PostgresDsn = "postgresql+asyncpg://postgres:postgres@localhost:5432/aitheria_project"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_ECHO: bool = False
    
    # Application URLs
    SERVER_HOST: AnyHttpUrl = "http://localhost:8002" # Default port for Project Service
    FRONTEND_URL: AnyHttpUrl = "http://localhost:3000"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "simple"  # "simple" or "json"
    
    # Uvicorn reload settings for local development
    UVICORN_RELOAD: bool = True
    UVICORN_RELOAD_DIRS: str = "/app"
    
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
            },
            EnvironmentType.PRODUCTION: {
                "DEBUG": False,
            },
            EnvironmentType.TEST: {
                "DEBUG": True,
                "DATABASE_ECHO": True,
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
