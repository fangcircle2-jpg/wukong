"""
MCP module - Model Context Protocol support.

Core chain:
    config.py    → MCPServerConfig, MCPSettings, load_mcp_settings
    client.py    → McpClient (single server: connect + discover + call)
    tool.py      → MCPToolWrapper (adapts MCP tools into Tool interface)
    manager.py   → MCPManager (manages multiple McpClients)
"""

from wukong.core.mcp.client import McpClient, McpClientError, MCPServerStatus
from wukong.core.mcp.config import (
    MCP_TOOL_NAME_SEPARATOR,
    MCPServerConfig,
    MCPSettings,
    load_mcp_settings,
)
from wukong.core.mcp.manager import MCPManager
from wukong.core.mcp.tool import MCPToolWrapper

__all__ = [
    "McpClient",
    "McpClientError",
    "MCPServerStatus",
    "MCPServerConfig",
    "MCPSettings",
    "MCP_TOOL_NAME_SEPARATOR",
    "load_mcp_settings",
    "MCPManager",
    "MCPToolWrapper",
]
