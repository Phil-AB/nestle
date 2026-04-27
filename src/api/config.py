"""
API configuration settings.

Loads configuration from environment variables and YAML config file.
"""

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, model_validator
from typing import List, Optional, Union
from functools import lru_cache
import yaml
from pathlib import Path


class APISettings(BaseSettings):
    """
    API configuration settings.

    Loaded from environment variables with API_ prefix.
    """

    # API Metadata
    API_TITLE: str = "Nestle Document Processing API"
    API_DESCRIPTION: str = "Production-grade REST API for document extraction and validation"
    API_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"

    # Server Configuration
    API_HOST: str = Field(default="0.0.0.0", description="API host")
    API_PORT: int = Field(default=8000, description="API port")
    ENVIRONMENT: str = Field(default="development", description="Environment (development, staging, production)")
    DEBUG: bool = Field(default=False, description="Debug mode")
    LOG_LEVEL: str = Field(default="INFO", description="Log level")

    # CORS Configuration — production origins must be set via API_CORS_ORIGINS env var
    ENABLE_CORS: bool = Field(default=True, description="Enable CORS")
    CORS_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:8080",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
        ],
        description="Allowed CORS origins. Override via API_CORS_ORIGINS=origin1,origin2"
    )
    CORS_METHODS: List[str] = Field(
        default=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        description="Allowed HTTP methods"
    )
    CORS_HEADERS: List[str] = Field(
        default=["Content-Type", "Authorization", "X-API-Key", "X-Request-ID"],
        description="Allowed request headers"
    )

    # Authentication
    ENABLE_AUTH: bool = Field(default=True, description="Enable API authentication")
    API_KEY_HEADER: str = Field(default="X-API-Key", description="API key header name")
    API_KEYS: List[str] = Field(default=[], description="Valid API keys — must be set via API_API_KEYS env var; no built-in default")
    JWT_SECRET_KEY: Optional[str] = Field(default=None, description="JWT secret key")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="Access token expiration")

    # LLM
    LLM_TIMEOUT_SECONDS: int = Field(default=180, description="Timeout in seconds for LLM API calls")

    # Rate Limiting
    ENABLE_RATE_LIMIT: bool = Field(default=True, description="Enable rate limiting")
    RATE_LIMIT_REQUESTS: int = Field(default=100, description="Max requests per window")
    RATE_LIMIT_WINDOW: int = Field(default=60, description="Rate limit window in seconds")

    # File Upload
    MAX_UPLOAD_SIZE: int = Field(default=50 * 1024 * 1024, description="Max upload size in bytes (50MB)")
    ALLOWED_EXTENSIONS: List[str] = Field(
        default=[
            # Document formats
            "pdf", "docx", "doc", "txt", "xlsx", "xls", "csv",
            # Image formats
            "png", "jpg", "jpeg", "webp", "tiff", "tif", "bmp", "gif", "svg",
            # Modern formats
            "webm", "heic", "heif",
        ],
        description="Allowed file extensions for document upload"
    )
    UPLOAD_DIRECTORY: str = Field(default="uploads", description="Upload directory path")

    # Background Tasks
    ENABLE_BACKGROUND_TASKS: bool = Field(default=True, description="Enable async background processing")
    CELERY_BROKER_URL: Optional[str] = Field(default=None, description="Celery broker URL")
    CELERY_RESULT_BACKEND: Optional[str] = Field(default=None, description="Celery result backend")

    # Webhooks
    ENABLE_WEBHOOKS: bool = Field(default=False, description="Enable webhook notifications")
    WEBHOOK_RETRY_ATTEMPTS: int = Field(default=3, description="Webhook retry attempts")
    WEBHOOK_TIMEOUT: int = Field(default=30, description="Webhook timeout in seconds")

    # Email notifications
    EMAIL_ENABLED: bool = Field(default=False, description="Enable email notifications")
    EMAIL_PROVIDER: str = Field(default="smtp", description="Email provider: 'sendgrid' or 'smtp'")
    SENDGRID_API_KEY: Optional[str] = Field(default=None, description="SendGrid API key")
    SMTP_HOST: Optional[str] = Field(default=None, description="SMTP server hostname")
    SMTP_PORT: int = Field(default=587, description="SMTP server port")
    SMTP_USERNAME: Optional[str] = Field(default=None, description="SMTP auth username")
    SMTP_PASSWORD: Optional[str] = Field(default=None, description="SMTP auth password")
    SMTP_USE_TLS: bool = Field(default=False, description="Use SMTP_SSL instead of STARTTLS")
    EMAIL_SENDER: str = Field(default="noreply@nestle.com", description="From address")
    EMAIL_SENDER_NAME: str = Field(default="Nestle Validation System", description="From name")
    EMAIL_RECIPIENTS: List[str] = Field(default=[], description="Alert recipient addresses")
    EMAIL_NOTIFY_ON_FAILURE: bool = Field(default=True, description="Send alert when validation fails")
    EMAIL_NOTIFY_ON_SUCCESS: bool = Field(default=False, description="Send alert when validation passes")
    EMAIL_NOTIFY_ON_REVIEW: bool = Field(default=True, description="Send alert when validation requires attention")
    APP_BASE_URL: str = Field(default="http://localhost:3000", description="Frontend base URL for email links")

    # Documentation
    ENABLE_DOCS: bool = Field(default=True, description="Enable API documentation")

    # Response Configuration
    INCLUDE_RAW_DATA: bool = Field(default=False, description="Include raw parser data in responses")
    INCLUDE_LAYOUT_DATA: bool = Field(default=False, description="Include layout data in responses")
    DEFAULT_PAGE_SIZE: int = Field(default=50, description="Default pagination size")
    MAX_PAGE_SIZE: int = Field(default=100, description="Maximum pagination size")

    @model_validator(mode='after')
    def require_api_keys_when_auth_enabled(self) -> 'APISettings':
        if self.ENABLE_AUTH and not self.API_KEYS:
            raise ValueError(
                "ENABLE_AUTH is True but API_KEYS is empty. "
                "Set API_API_KEYS=key1,key2 in the environment, or set API_ENABLE_AUTH=False."
            )
        return self

    @field_validator('CORS_ORIGINS', 'CORS_METHODS', 'CORS_HEADERS', 'API_KEYS', 'ALLOWED_EXTENSIONS', mode='before')
    @classmethod
    def split_string_to_list(cls, value):
        """Convert comma-separated string to list."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(',') if item.strip()]
        return value

    class Config:
        env_file = ".env"
        env_prefix = "API_"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_api_settings() -> APISettings:
    """
    Get cached API settings instance.

    Returns:
        APISettings instance
    """
    return APISettings()


def load_api_config_from_yaml(config_path: Optional[str] = None) -> dict:
    """
    Load additional API configuration from YAML file.

    Args:
        config_path: Optional path to config file

    Returns:
        Configuration dictionary
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "api_config.yaml"

    try:
        if Path(config_path).exists():
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        else:
            return {}
    except Exception as e:
        import logging
        logging.warning(f"Could not load API config from YAML: {e}")
        return {}
