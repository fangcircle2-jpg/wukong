"""
MCP configuration models.

Defines server configuration and settings for MCP support.
Config file: ~/.config/wukong/mcp_servers.json

Format (compatible with Claude Desktop):
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "env": {},
      "enabled": true,
      "timeout": 60000
    },
    "my-remote": {
      "url": "http://localhost:8080/sse",
      "enabled": true
    }
  }
}
"""

import json
import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, model_validator

logger = logging.getLogger(__name__)

MCP_CONFIG_FILE = Path.home() / ".config" / "wukong" / "mcp_servers.json"

# Separator for qualified tool names: "serverName__toolName"
MCP_TOOL_NAME_SEPARATOR = "__"


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server."""

    # stdio transport
    command: str | None = None
    args: list[str] = []
    env: dict[str, str] = {}
    cwd: str | None = None

    # SSE / Streamable HTTP transport
    url: str | None = None

    # Transport type hint (auto-detected if not set)
    transport: Literal["stdio", "sse", "http"] | None = None

    # General options
    enabled: bool = True
    timeout: int = 600_000  # milliseconds

    @model_validator(mode="after")
    def validate_transport(self) -> "MCPServerConfig":
        has_stdio = self.command is not None
        has_remote = self.url is not None
        if not has_stdio and not has_remote:
            raise ValueError("MCPServerConfig requires either 'command' (stdio) or 'url' (sse/http)")
        if has_stdio and has_remote:
            raise ValueError("MCPServerConfig cannot have both 'command' and 'url'")
        return self

    def get_transport_type(self) -> Literal["stdio", "sse", "http"]:
        """Detect transport type from config."""
        if self.transport:
            return self.transport
        if self.command:
            return "stdio"
        # Default remote to sse
        return "sse"


class MCPSettings(BaseModel):
    """Top-level MCP settings, loaded from mcp_servers.json."""

    mcpServers: dict[str, MCPServerConfig] = {}

    def get_enabled_servers(self) -> dict[str, MCPServerConfig]:
        """Return only enabled server configs."""
        return {
            name: cfg
            for name, cfg in self.mcpServers.items()
            if cfg.enabled
        }


def load_mcp_settings(config_file: Path | None = None) -> MCPSettings:
    """Load MCP settings from JSON config file.

    Args:
        config_file: Path to config file. Defaults to MCP_CONFIG_FILE.

    Returns:
        MCPSettings instance. Returns empty settings if file not found.
    """
    path = config_file or MCP_CONFIG_FILE

    if not path.exists():
        logger.debug(f"MCP config file not found: {path}, using empty settings")
        return MCPSettings()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        settings = MCPSettings.model_validate(raw)
        enabled = settings.get_enabled_servers()
        logger.info(f"Loaded {len(settings.mcpServers)} MCP servers ({len(enabled)} enabled) from {path}")
        return settings
    except Exception as e:
        logger.error(f"Failed to load MCP config from {path}: {e}")
        return MCPSettings()
