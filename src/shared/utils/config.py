"""
Configuration management using pydantic-settings.
Loads configuration from environment variables and .env file.
"""

from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Database Configuration
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str
    DB_NAME: str = "nestle_boe"

    # Database Connection Pool Settings (optimized for 100+ concurrent users)
    DATABASE_POOL_SIZE: int = 20  # Core pool size (10-20 for small/medium, 30-50 for large deployments)
    DATABASE_MAX_OVERFLOW: int = 30  # Additional connections beyond pool_size during peak load
    DATABASE_POOL_PRE_PING: bool = True  # Verify connections before using (prevents stale connections)
    DATABASE_POOL_RECYCLE: int = 3600  # Recycle connections after 1 hour (3600 seconds)
    DATABASE_ECHO: bool = False  # Echo SQL queries to console (debug only)

    @property
    def DATABASE_URL(self) -> str:
        """Construct database URL from individual components."""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Redis Configuration (for distributed rate limiting and caching)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_DB: int = 0
    REDIS_URL: str | None = None  # Optional: full Redis URL overrides individual settings

    @property
    def redis_connection_url(self) -> str:
        """Construct Redis URL from settings."""
        if self.REDIS_URL:
            return self.REDIS_URL

        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Reducto API Configuration
    REDUCTO_API_KEY: str
    REDUCTO_BASE_URL: str = "https://platform.reducto.ai"

    # LLM Configuration
    LLM_PROVIDER: Literal["openai", "anthropic", "custom"] = "openai"
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    CUSTOM_LLM_ENDPOINT: str | None = None
    CUSTOM_LLM_MODEL: str = "gpt-4"
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_TOKENS: int = 4096

    # Application Configuration
    APP_NAME: str = "Nestle BOE Validation System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Streamlit Configuration
    STREAMLIT_SERVER_PORT: int = 8501
    STREAMLIT_SERVER_ADDRESS: str = "localhost"

    # Validation Configuration (COMMENTED OUT - not used for now)
    # VALIDATION_ACCURACY_THRESHOLD: float = 98.0
    # VALIDATION_ADDRESS_SIMILARITY_THRESHOLD: int = 90
    # VALIDATION_AUTO_TRIGGER: bool = True

    # Insurance Calculation Rates (COMMENTED OUT - not used for now)
    # INSURANCE_RATE_SEA: float = 0.00875  # 0.875%
    # INSURANCE_RATE_AIR: float = 0.01     # 1%

    # File Upload Configuration
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: str = "pdf,xlsx,xls,png,jpg,jpeg"

    @property
    def allowed_extensions_list(self) -> list[str]:
        """Get allowed file extensions as a list."""
        return self.ALLOWED_EXTENSIONS.split(",")

    @property
    def max_upload_size_bytes(self) -> int:
        """Get max upload size in bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    def get_llm_api_key(self) -> str:
        """Get the appropriate LLM API key based on provider."""
        if self.LLM_PROVIDER == "openai":
            if not self.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY not set")
            return self.OPENAI_API_KEY
        elif self.LLM_PROVIDER == "anthropic":
            if not self.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY not set")
            return self.ANTHROPIC_API_KEY
        elif self.LLM_PROVIDER == "custom":
            return ""  # Custom endpoints may not need API keys
        else:
            raise ValueError(f"Unknown LLM provider: {self.LLM_PROVIDER}")


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to ensure settings are loaded only once.
    """
    return Settings()


# Global settings instance
settings = get_settings()
