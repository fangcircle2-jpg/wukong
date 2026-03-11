"""
MCPManager - manages multiple MCP server connections.

Lifecycle:
    settings = load_mcp_settings()
    manager = MCPManager(settings)
    await manager.connect_all(tool_registry)
    ...
    await manager.disconnect_all()

Usage in AgentLoop:
    extra_kwargs = {"mcp_manager": manager}  # injected via context_keys
"""

import asyncio
import logging

from wukong.core.mcp.client import McpClient, McpClientError
from wukong.core.mcp.config import MCPServerConfig, MCPSettings, load_mcp_settings
from wukong.core.mcp.tool import MCPToolWrapper
from wukong.core.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class MCPManager:
    """Manages multiple MCP server connections and tool registration.

    Attributes:
        _settings: Loaded MCP settings (all server configs).
        _clients: Active McpClient instances keyed by server name.
    """

    def __init__(self, settings: MCPSettings) -> None:
        self._settings = settings
        self._clients: dict[str, McpClient] = {}

    # ========================================
    # Public API
    # ========================================

    def get_client(self, server_name: str) -> McpClient | None:
        """Get a connected McpClient by server name.

        Called by MCPToolWrapper.execute() at tool invocation time.

        Args:
            server_name: Name of the MCP server.

        Returns:
            McpClient if connected, None otherwise.
        """
        return self._clients.get(server_name)

    async def connect_all(self, registry: ToolRegistry) -> dict[str, int]:
        """Connect to all enabled MCP servers in parallel and register tools.

        Each server is connected concurrently. Failures are logged and skipped
        so one broken server does not block others.

        Args:
            registry: ToolRegistry to register discovered tools into.

        Returns:
            Dict mapping server_name -> number of tools registered.
        """
        servers = self._settings.get_enabled_servers()
        if not servers:
            logger.info("No enabled MCP servers configured")
            return {}

        logger.info(f"Connecting to {len(servers)} MCP server(s): {list(servers)}")

        tasks = [
            self._connect_one(name, config, registry)
            for name, config in servers.items()
        ]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: dict[str, int] = {}
        for (name, _), outcome in zip(servers.items(), raw_results):
            if isinstance(outcome, BaseException):
                logger.error(f"[{name}] Failed to connect: {outcome}")
            else:
                results[name] = outcome
                logger.info(f"[{name}] Connected, {outcome} tool(s) registered")

        logger.info(
            f"MCP connect_all done: {len(results)}/{len(servers)} server(s) ok, "
            f"{sum(results.values())} total tool(s)"
        )
        return results

    async def disconnect_all(self) -> None:
        """Disconnect all connected MCP servers in parallel."""
        if not self._clients:
            return

        logger.info(f"Disconnecting {len(self._clients)} MCP server(s)")

        tasks = [client.disconnect() for client in self._clients.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

        self._clients.clear()
        logger.info("All MCP servers disconnected")

    # ========================================
    # Internal helpers
    # ========================================

    async def _connect_one(
        self,
        name: str,
        config: MCPServerConfig,
        registry: ToolRegistry,
    ) -> int:
        """Connect a single MCP server, wrap and register its tools.

        Args:
            name: Server name (used as key and tool name prefix).
            config: Server configuration.
            registry: ToolRegistry to register wrapped tools into.

        Returns:
            Number of tools successfully registered.

        Raises:
            McpClientError: If connection or discovery fails.
        """
        client = McpClient(name, config)
        mcp_tools = await client.connect_and_discover()

        registered = 0
        for mcp_tool in mcp_tools:
            wrapper = MCPToolWrapper(server_name=name, mcp_tool=mcp_tool)
            if registry.register(wrapper):
                registered += 1

        self._clients[name] = client
        return registered

    # ========================================
    # Factory / context manager
    # ========================================

    @classmethod
    def from_config_file(cls) -> "MCPManager":
        """Create MCPManager by loading settings from default config file."""
        settings = load_mcp_settings()
        return cls(settings)

    async def __aenter__(self) -> "MCPManager":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.disconnect_all()

    def __repr__(self) -> str:
        connected = [n for n, c in self._clients.items() if c.is_connected()]
        return f"<MCPManager servers={connected}>"
