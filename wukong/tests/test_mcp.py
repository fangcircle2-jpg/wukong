"""
Tests for MCP module: MCPManager, MCPToolWrapper.

Run with: pytest tests/test_mcp.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import mcp.types as mcp_types

from wukong.core.mcp.config import MCPServerConfig, MCPSettings
from wukong.core.mcp.manager import MCPManager
from wukong.core.mcp.tool import MCPToolWrapper
from wukong.core.tools.base import ToolResult
from wukong.core.tools.registry import ToolRegistry


# ========================================
# Helpers
# ========================================

def make_mcp_tool(name: str, description: str = "", schema: dict | None = None) -> mcp_types.Tool:
    """Build a minimal mcp_types.Tool for testing."""
    return mcp_types.Tool(
        name=name,
        description=description,
        inputSchema=schema or {"type": "object", "properties": {}},
    )


def make_settings(*server_names: str) -> MCPSettings:
    """Build MCPSettings with stdio-style stub configs."""
    servers = {
        name: MCPServerConfig(command="echo", args=[name])
        for name in server_names
    }
    return MCPSettings(mcpServers=servers)


def make_mock_client(tools: list[mcp_types.Tool]) -> MagicMock:
    """Build a mock McpClient that returns `tools` on connect_and_discover."""
    client = MagicMock()
    client.is_connected.return_value = True
    client.connect_and_discover = AsyncMock(return_value=tools)
    client.disconnect = AsyncMock()
    return client


# ========================================
# MCPManager.connect_all
# ========================================

@pytest.mark.asyncio
async def test_connect_all_registers_tools():
    """connect_all should wrap each discovered tool and register it."""
    settings = make_settings("fs")
    manager = MCPManager(settings)
    registry = ToolRegistry()

    fs_tools = [make_mcp_tool("read_file"), make_mcp_tool("write_file")]
    mock_client = make_mock_client(fs_tools)

    with patch("wukong.core.mcp.manager.McpClient", return_value=mock_client):
        counts = await manager.connect_all(registry)

    assert counts == {"fs": 2}
    assert "fs__read_file" in registry
    assert "fs__write_file" in registry


@pytest.mark.asyncio
async def test_connect_all_parallel_multiple_servers():
    """connect_all should connect all servers even when they run in parallel."""
    settings = make_settings("server_a", "server_b")
    manager = MCPManager(settings)
    registry = ToolRegistry()

    clients = {
        "server_a": make_mock_client([make_mcp_tool("tool_x")]),
        "server_b": make_mock_client([make_mcp_tool("tool_y"), make_mcp_tool("tool_z")]),
    }

    call_order: list[str] = []

    def client_factory(name, config):
        call_order.append(name)
        return clients[name]

    with patch("wukong.core.mcp.manager.McpClient", side_effect=client_factory):
        counts = await manager.connect_all(registry)

    assert counts["server_a"] == 1
    assert counts["server_b"] == 2
    assert "server_a__tool_x" in registry
    assert "server_b__tool_y" in registry
    assert "server_b__tool_z" in registry


@pytest.mark.asyncio
async def test_connect_all_skips_failed_server():
    """A failing server should not block others from connecting."""
    settings = make_settings("good", "bad")
    manager = MCPManager(settings)
    registry = ToolRegistry()

    good_client = make_mock_client([make_mcp_tool("tool_ok")])
    bad_client = MagicMock()
    bad_client.connect_and_discover = AsyncMock(side_effect=Exception("connection refused"))

    def client_factory(name, config):
        return good_client if name == "good" else bad_client

    with patch("wukong.core.mcp.manager.McpClient", side_effect=client_factory):
        counts = await manager.connect_all(registry)

    assert "good" in counts
    assert "bad" not in counts
    assert "good__tool_ok" in registry


@pytest.mark.asyncio
async def test_connect_all_no_servers_returns_empty():
    """connect_all with no enabled servers should return empty dict."""
    settings = MCPSettings(mcpServers={})
    manager = MCPManager(settings)
    registry = ToolRegistry()

    counts = await manager.connect_all(registry)

    assert counts == {}


# ========================================
# MCPManager.get_client
# ========================================

@pytest.mark.asyncio
async def test_get_client_returns_connected_client():
    """get_client should return the McpClient after connect_all."""
    settings = make_settings("myserver")
    manager = MCPManager(settings)
    registry = ToolRegistry()

    mock_client = make_mock_client([make_mcp_tool("ping")])
    with patch("wukong.core.mcp.manager.McpClient", return_value=mock_client):
        await manager.connect_all(registry)

    assert manager.get_client("myserver") is mock_client


def test_get_client_returns_none_before_connect():
    """get_client should return None for unknown/unconnected server."""
    manager = MCPManager(MCPSettings(mcpServers={}))
    assert manager.get_client("nonexistent") is None


# ========================================
# MCPManager.disconnect_all
# ========================================

@pytest.mark.asyncio
async def test_disconnect_all_calls_disconnect_on_all():
    """disconnect_all should call disconnect() on every connected client."""
    settings = make_settings("s1", "s2")
    manager = MCPManager(settings)
    registry = ToolRegistry()

    clients = {
        "s1": make_mock_client([make_mcp_tool("a")]),
        "s2": make_mock_client([make_mcp_tool("b")]),
    }

    with patch("wukong.core.mcp.manager.McpClient", side_effect=lambda n, c: clients[n]):
        await manager.connect_all(registry)

    await manager.disconnect_all()

    clients["s1"].disconnect.assert_awaited_once()
    clients["s2"].disconnect.assert_awaited_once()
    assert manager.get_client("s1") is None
    assert manager.get_client("s2") is None


@pytest.mark.asyncio
async def test_disconnect_all_idempotent_when_empty():
    """disconnect_all on an empty manager should not raise."""
    manager = MCPManager(MCPSettings(mcpServers={}))
    await manager.disconnect_all()  # should not raise


# ========================================
# MCPToolWrapper.execute
# ========================================

@pytest.mark.asyncio
async def test_tool_execute_success():
    """execute() should call client.call_tool and return ToolResult.ok."""
    mcp_tool = make_mcp_tool("search", schema={
        "type": "object",
        "properties": {"query": {"type": "string"}},
    })
    wrapper = MCPToolWrapper(server_name="myserver", mcp_tool=mcp_tool)
    assert wrapper.name == "myserver__search"

    call_result = mcp_types.CallToolResult(
        content=[mcp_types.TextContent(type="text", text="found 3 results")],
        isError=False,
    )
    mock_client = MagicMock()
    mock_client.call_tool = AsyncMock(return_value=call_result)

    mock_manager = MagicMock()
    mock_manager.get_client.return_value = mock_client

    result = await wrapper.execute(
        workspace_dir="/tmp",
        mcp_manager=mock_manager,
        query="hello",
    )

    assert result.success is True
    assert "found 3 results" in result.output
    mock_client.call_tool.assert_awaited_once_with("search", arguments={"query": "hello"})


@pytest.mark.asyncio
async def test_tool_execute_mcp_error_response():
    """execute() should return ToolResult.fail when isError=True."""
    mcp_tool = make_mcp_tool("fail_tool")
    wrapper = MCPToolWrapper(server_name="srv", mcp_tool=mcp_tool)

    call_result = mcp_types.CallToolResult(
        content=[mcp_types.TextContent(type="text", text="something went wrong")],
        isError=True,
    )
    mock_client = MagicMock()
    mock_client.call_tool = AsyncMock(return_value=call_result)

    mock_manager = MagicMock()
    mock_manager.get_client.return_value = mock_client

    result = await wrapper.execute(workspace_dir="/tmp", mcp_manager=mock_manager)

    assert result.success is False
    assert "something went wrong" in result.error


@pytest.mark.asyncio
async def test_tool_execute_no_manager():
    """execute() without mcp_manager should return a clear failure."""
    wrapper = MCPToolWrapper(server_name="srv", mcp_tool=make_mcp_tool("ping"))

    result = await wrapper.execute(workspace_dir="/tmp", mcp_manager=None)

    assert result.success is False
    assert "MCPManager not available" in result.error


@pytest.mark.asyncio
async def test_tool_execute_server_not_connected():
    """execute() when server is not in manager should return failure."""
    wrapper = MCPToolWrapper(server_name="missing", mcp_tool=make_mcp_tool("ping"))

    mock_manager = MagicMock()
    mock_manager.get_client.return_value = None

    result = await wrapper.execute(workspace_dir="/tmp", mcp_manager=mock_manager)

    assert result.success is False
    assert "missing" in result.error


# ========================================
# MCPToolWrapper naming & schema
# ========================================

def test_tool_name_qualified():
    """Tool name should be 'serverName__toolName'."""
    tool = MCPToolWrapper(
        server_name="github",
        mcp_tool=make_mcp_tool("create_issue"),
    )
    assert tool.name == "github__create_issue"


def test_tool_description_includes_server():
    """Tool description should mention the server name."""
    tool = MCPToolWrapper(
        server_name="myserver",
        mcp_tool=make_mcp_tool("ping", description="Check health"),
    )
    assert "myserver" in tool.description
    assert "Check health" in tool.description


def test_tool_parameters_schema_passthrough():
    """parameters model should return the original MCP inputSchema."""
    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "encoding": {"type": "string"},
        },
        "required": ["path"],
    }
    tool = MCPToolWrapper(
        server_name="fs",
        mcp_tool=make_mcp_tool("read_file", schema=schema),
    )
    assert tool.parameters.model_json_schema() == schema
