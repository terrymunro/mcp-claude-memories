"""Configuration settings using Pydantic."""

import logging
from pathlib import Path

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Mem0 Configuration
    mem0_api_key: str = Field(..., description="Mem0 SaaS API key")

    # Claude Configuration
    claude_config_dir: Path = Field(
        default=Path.home() / ".config" / "claude",
        description="Path to Claude configuration directory",
    )
    default_user_id: str = Field(
        default="default_user", description="Default user ID for memory storage"
    )

    # Watch Configuration
    watch_patterns: list[str] = Field(
        default=["conversation*.jsonl"],
        description="File patterns to watch for conversations",
    )

    # Debug Settings
    debug: bool = Field(default=False, description="Enable debug logging")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @field_validator("mem0_api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate Mem0 API key format."""
        if not v or not v.strip():
            raise ValueError("Mem0 API key cannot be empty")

        # Basic format validation (adjust based on actual Mem0 key format)
        if len(v.strip()) < 10:
            raise ValueError("Mem0 API key appears to be too short")

        return v.strip()

    @field_validator("claude_config_dir")
    @classmethod
    def validate_config_dir(cls, v: Path) -> Path:
        """Validate Claude config directory."""
        if not v.exists():
            logger.warning(f"Claude config directory does not exist: {v}")
            # Don't raise error, just warn - directory might be created later
        elif not v.is_dir():
            raise ValueError(f"Claude config path is not a directory: {v}")

        return v

    def get_watch_directories(self) -> list[Path]:
        """Get list of directories to watch for conversation files."""
        projects_dir = self.claude_config_dir / "projects"
        if not projects_dir.exists():
            return []

        return [
            project_dir
            for project_dir in projects_dir.iterdir()
            if project_dir.is_dir()
        ]


def get_settings() -> Settings:
    """Get application settings instance."""
    try:
        return Settings()
    except ValidationError as e:
        logger.error(f"Configuration validation failed: {e}")
        # Print user-friendly error messages
        for error in e.errors():
            field = error["loc"][0] if error["loc"] else "unknown"
            message = error["msg"]
            logger.error(f"  {field}: {message}")
        raise ValueError(
            "Invalid configuration. Please check your environment variables and .env file."
        ) from e
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise
