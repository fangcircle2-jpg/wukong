"""
Settings module - Application configuration using Pydantic Settings.

Configuration loading priority:
    Environment variables > .env file > User config file > Default values
"""

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_config_dir() -> Path:
    """Get the configuration directory path."""
    # Use ~/.config/wukong/ on all platforms
    config_dir = Path.home() / ".config" / "wukong"
    return config_dir


def get_config_file() -> Path:
    """Get the user config file path."""
    return get_config_dir() / "config.toml"


class LLMSettings(BaseSettings):
    """LLM provider settings."""

    model_config = SettingsConfigDict(
        env_prefix="wukong_LLM_",
        extra="ignore",
    )

    provider: Literal["openai", "anthropic", "google", "local", "mock"] = Field(
        default="anthropic",
        description="Default LLM provider",
    )
    model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Default model name",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Temperature for generation",
    )
    max_tokens: int = Field(
        default=4096,
        gt=0,
        description="Maximum tokens in response",
    )

    # API Keys (loaded from environment)
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key",
        json_schema_extra={"env": "OPENAI_API_KEY"},
    )
    openai_base_url: str | None = Field(
        default=None,
        description="OpenAI API base URL (optional, uses default if not set)",
        json_schema_extra={"env": "OPENAI_BASE_URL"},
    )
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key",
        json_schema_extra={"env": "ANTHROPIC_API_KEY"},
    )
    google_api_key: str = Field(
        default="",
        description="Google AI API key",
        json_schema_extra={"env": "GOOGLE_API_KEY"},
    )

    # Local model settings
    local_base_url: str = Field(
        default="http://localhost:11434/v1",
        description="Local model API base URL",
    )
    local_model: str = Field(
        default="llama3.2",
        description="Local model name",
    )


class AppSettings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_prefix="wukong_",
        extra="ignore",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Log level",
    )
    streaming: bool = Field(
        default=True,
        description="Enable streaming output",
    )
    max_context_tokens: int = Field(
        default=128000,
        gt=0,
        description="Maximum context window tokens",
    )

    # Directories
    config_dir: Path = Field(
        default_factory=get_config_dir,
        description="Configuration directory",
    )
    session_dir: Path = Field(
        default_factory=lambda: get_config_dir() / "sessions",
        description="Session storage directory",
    )

    @field_validator("config_dir", "session_dir", mode="after")
    @classmethod
    def ensure_dir_exists(cls, v: Path) -> Path:
        """Ensure directory exists."""
        v.mkdir(parents=True, exist_ok=True)
        return v


class PermissionSettings(BaseSettings):
    """Permission and safety settings."""

    model_config = SettingsConfigDict(
        env_prefix="wukong_PERMISSION_",
        extra="ignore",
    )

    auto_confirm_safe: bool = Field(
        default=True,
        description="Auto-confirm safe operations (read-only)",
    )
    auto_confirm_moderate: bool = Field(
        default=False,
        description="Auto-confirm moderate operations (file writes)",
    )
    auto_confirm_dangerous: bool = Field(
        default=False,
        description="Auto-confirm dangerous operations (code execution)",
    )


class ContextSettings(BaseSettings):
    """Context provider settings.
    
    Controls which context providers are enabled.
    Provider-specific configuration is managed within each provider.
    """

    model_config = SettingsConfigDict(
        env_prefix="wukong_CONTEXT_",
        extra="ignore",
    )

    enabled_providers: list[str] = Field(
        default=["file"],
        description="List of enabled context providers (e.g., file, url, codebase)",
    )


class MCPAppSettings(BaseSettings):
    """MCP feature settings.

    Controls whether MCP support is enabled at all and allows overriding
    the default config file path (~/.config/wukong/mcp_servers.json).

    Environment variables:
        wukong_MCP_ENABLED=false     → disable MCP globally
        wukong_MCP_CONFIG_FILE=/path → use a custom mcp_servers.json
    """

    model_config = SettingsConfigDict(
        env_prefix="wukong_MCP_",
        extra="ignore",
    )

    enabled: bool = Field(
        default=True,
        description="Enable MCP server support",
    )
    config_file: Path | None = Field(
        default=None,
        description=(
            "Path to mcp_servers.json. "
            "Defaults to ~/.config/wukong/mcp_servers.json when None."
        ),
    )


class Settings(BaseSettings):
    """Main settings class that combines all settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Nested settings
    llm: LLMSettings = Field(default_factory=LLMSettings)
    app: AppSettings = Field(default_factory=AppSettings)
    permission: PermissionSettings = Field(default_factory=PermissionSettings)
    context: ContextSettings = Field(default_factory=ContextSettings)
    mcp: MCPAppSettings = Field(default_factory=MCPAppSettings)

    @classmethod
    def load(cls) -> "Settings":
        """
        Load settings from environment and config file.
        
        Priority: Environment variables > .env file > User config > Defaults
        """
        # First, try to load .env file from current directory
        from dotenv import load_dotenv
        load_dotenv()

        # TODO: Add TOML config file loading in the future
        # config_file = get_config_file()
        # if config_file.exists():
        #     Load and merge TOML config

        return cls()


# Global settings instance (lazy loaded)
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from disk."""
    global _settings
    _settings = Settings.load()
    return _settings

