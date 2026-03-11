"""
MCP Client - manages connection and tool discovery for a single MCP server.

Lifecycle:
    DISCONNECTED → CONNECTING → CONNECTED
                                    ↓
                              DISCONNECTING → DISCONNECTED

Usage:
    config = MCPServerConfig(command="npx", args=["-y", "@mcp/server-filesystem", "/tmp"])
    client = McpClient("filesystem", config)
    tools = await client.connect_and_discover()
    # tools: list[mcp.types.Tool]
    await client.call_tool("read_file", {"path": "/tmp/hello.txt"})
    await client.disconnect()
"""

import asyncio
import logging
from contextlib import AsyncExitStack
from enum import Enum
from typing import Any

import mcp.types as mcp_types
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

from wukong.core.mcp.config import MCPServerConfig

logger = logging.getLogger(__name__)


class MCPServerStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"


class McpClientError(Exception):
    """Raised when MCP client operations fail."""
    pass


class McpClient:
    """Client for a single MCP server.

    Responsible for:
    - Establishing transport connection (stdio / sse / http)
    - Initializing ClientSession
    - Discovering available tools
    - Executing tool calls
    - Clean disconnection
    """

    def __init__(self, server_name: str, config: MCPServerConfig) -> None:
        self.server_name = server_name
        self.config = config
        self.status = MCPServerStatus.DISCONNECTED

        self._session: ClientSession | None = None
        self._exit_stack: AsyncExitStack | None = None
        self._server_capabilities: mcp_types.ServerCapabilities | None = None

    # ========================================
    # Public API
    # ========================================

    async def connect_and_discover(self) -> list[mcp_types.Tool]:
        """Connect to MCP server and return discovered tools.

        Returns:
            List of MCP Tool definitions from the server.

        Raises:
            McpClientError: If connection or discovery fails.
        """
        await self._connect()
        return await self._discover_tools()

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> mcp_types.CallToolResult:
        """Call a tool on the connected MCP server.

        Args:
            tool_name: The original tool name (NOT the qualified name).
            arguments: Tool arguments dict.

        Returns:
            CallToolResult from the MCP server.

        Raises:
            McpClientError: If not connected or call fails.
        """
        self._assert_connected()

        timeout_seconds = self.config.timeout / 1000.0

        try:
            result = await asyncio.wait_for(
                self._session.call_tool(tool_name, arguments),  # type: ignore[union-attr]
                timeout=timeout_seconds,
            )
            logger.debug(f"[{self.server_name}] call_tool({tool_name}) -> isError={result.isError}")
            return result
        except asyncio.TimeoutError:
            raise McpClientError(
                f"Tool call '{tool_name}' on server '{self.server_name}' timed out after {timeout_seconds}s"
            )
        except Exception as e:
            raise McpClientError(
                f"Tool call '{tool_name}' on server '{self.server_name}' failed: {e}"
            ) from e

    async def disconnect(self) -> None:
        """Disconnect from MCP server and clean up resources."""
        if self.status == MCPServerStatus.DISCONNECTED:
            return

        self._update_status(MCPServerStatus.DISCONNECTING)
        try:
            if self._exit_stack:
                await self._exit_stack.aclose()
        except Exception as e:
            logger.warning(f"[{self.server_name}] Error during disconnect: {e}")
        finally:
            self._session = None
            self._exit_stack = None
            self._server_capabilities = None
            self._update_status(MCPServerStatus.DISCONNECTED)

    def is_connected(self) -> bool:
        return self.status == MCPServerStatus.CONNECTED

    # ========================================
    # Transport Layer
    # ========================================

    async def _connect(self) -> None:
        """Establish transport connection and initialize ClientSession."""
        if self.status != MCPServerStatus.DISCONNECTED:
            raise McpClientError(
                f"Cannot connect: server '{self.server_name}' is in state '{self.status}'"
            )

        self._update_status(MCPServerStatus.CONNECTING)

        try:
            self._exit_stack = AsyncExitStack()
            transport_type = self.config.get_transport_type()

            if transport_type == "stdio":
                read, write = await self._exit_stack.enter_async_context(
                    self._make_stdio_transport()
                )
            elif transport_type == "sse":
                read, write = await self._exit_stack.enter_async_context(
                    self._make_sse_transport()
                )
            elif transport_type == "http":
                read, write, _ = await self._exit_stack.enter_async_context(
                    self._make_http_transport()
                )
            else:
                raise McpClientError(f"Unknown transport type: {transport_type}")

            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read, write)
            )

            try:
                init_result = await self._session.initialize()
            except RuntimeError as e:
                if "Unsupported protocol version" in str(e):
                    raise McpClientError(
                        f"MCP server '{self.server_name}' uses an incompatible protocol version. "
                        f"Please update the server or the mcp SDK. Detail: {e}"
                    ) from e
                raise

            self._server_capabilities = init_result.capabilities
            self._update_status(MCPServerStatus.CONNECTED)
            logger.info(
                f"[{self.server_name}] Connected via {transport_type}, "
                f"capabilities: tools={init_result.capabilities.tools is not None}, "
                f"resources={init_result.capabilities.resources is not None}, "
                f"prompts={init_result.capabilities.prompts is not None}"
            )

        except McpClientError:
            self._update_status(MCPServerStatus.DISCONNECTED)
            if self._exit_stack:
                await self._exit_stack.aclose()
                self._exit_stack = None
            raise
        except Exception as e:
            self._update_status(MCPServerStatus.DISCONNECTED)
            if self._exit_stack:
                await self._exit_stack.aclose()
                self._exit_stack = None
            raise McpClientError(
                f"Failed to connect to MCP server '{self.server_name}': {e}"
            ) from e

    def _make_stdio_transport(self):
        """Create stdio transport context manager."""
        params = StdioServerParameters(
            command=self.config.command,  # type: ignore[arg-type]
            args=self.config.args,
            env=self.config.env or None,
            cwd=self.config.cwd,
        )
        return stdio_client(params)

    def _make_sse_transport(self):
        """Create SSE transport context manager."""
        timeout_seconds = self.config.timeout / 1000.0
        return sse_client(
            url=self.config.url,  # type: ignore[arg-type]
            timeout=timeout_seconds,
        )

    def _make_http_transport(self):
        """Create Streamable HTTP transport context manager."""
        timeout_seconds = self.config.timeout / 1000.0
        return streamablehttp_client(
            url=self.config.url,  # type: ignore[arg-type]
            timeout=timeout_seconds,
        )

    # ========================================
    # Discovery
    # ========================================

    @property
    def server_capabilities(self) -> mcp_types.ServerCapabilities | None:
        """Server capabilities from the initialize handshake (None before connect)."""
        return self._server_capabilities

    async def _discover_tools(self) -> list[mcp_types.Tool]:
        """Fetch tool list from connected MCP server.

        Returns:
            List of mcp.types.Tool from the server.
            Empty list if server does not advertise tools capability.
        """
        self._assert_connected()

        if self._server_capabilities and self._server_capabilities.tools is None:
            logger.info(
                f"[{self.server_name}] Server does not advertise tools capability, skipping discovery"
            )
            return []

        try:
            result = await self._session.list_tools()  # type: ignore[union-attr]
            tools = result.tools
            logger.info(
                f"[{self.server_name}] Discovered {len(tools)} tools: "
                f"{[t.name for t in tools]}"
            )
            return tools
        except Exception as e:
            raise McpClientError(
                f"Failed to discover tools from '{self.server_name}': {e}"
            ) from e

    # ========================================
    # Internal helpers
    # ========================================

    def _assert_connected(self) -> None:
        if self.status != MCPServerStatus.CONNECTED or self._session is None:
            raise McpClientError(
                f"MCP server '{self.server_name}' is not connected (state: {self.status})"
            )

    def _update_status(self, status: MCPServerStatus) -> None:
        logger.debug(f"[{self.server_name}] status: {self.status} → {status}")
        self.status = status

    def __repr__(self) -> str:
        return f"<McpClient server={self.server_name!r} status={self.status}>"
