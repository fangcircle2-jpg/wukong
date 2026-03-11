"""
MCPToolWrapper - adapts MCP server tools into wukong's Tool interface.

Each discovered MCP tool is wrapped as an MCPToolWrapper instance,
which can be registered directly into ToolRegistry.

Tool naming convention: "serverName__toolName"
  e.g. "filesystem__read_file", "github__create_issue"

Execution flow:
    AgentLoop calls tool.execute(**kwargs)
        → MCPToolWrapper gets mcp_manager from context_keys injection
        → calls mcp_manager.get_client(server_name).call_tool(original_tool_name, kwargs)
        → converts CallToolResult → ToolResult
"""

import logging
from typing import TYPE_CHECKING, Any

import mcp.types as mcp_types
from pydantic import BaseModel

from wukong.core.mcp.config import MCP_TOOL_NAME_SEPARATOR
from wukong.core.tools.base import Tool, ToolResult

if TYPE_CHECKING:
    from wukong.core.mcp.manager import MCPManager

logger = logging.getLogger(__name__)


class MCPToolWrapper(Tool):
    """Wraps a discovered MCP tool as a wukong Tool.

    Injected via context_keys["mcp_manager"] at execution time.
    The mcp_manager provides access to the correct server's McpClient
    by server_name, so multiple MCP servers can coexist in one ToolRegistry.

    Attributes:
        name: Qualified name "serverName__toolName" (used by AgentLoop)
        description: Tool description from MCP server
        parameters: JSON Schema from MCP server's inputSchema
        server_name: The MCP server this tool belongs to
        original_tool_name: The tool name as registered in the MCP server
    """

    # Declared at class level to satisfy Tool ABC, overridden in __init__
    name: str = ""
    description: str = ""

    # Request mcp_manager injection from AgentLoop._build_tool_context()
    context_keys: list[str] = ["mcp_manager"]

    def __init__(
        self,
        server_name: str,
        mcp_tool: mcp_types.Tool,
    ) -> None:
        """Create wrapper for a discovered MCP tool.

        Args:
            server_name: Name of the MCP server (used for qualified naming).
            mcp_tool: Tool definition from mcp.types.Tool.
        """
        self.server_name = server_name
        self.original_tool_name = mcp_tool.name

        # Build qualified name: "serverName__toolName"
        self.name = f"{server_name}{MCP_TOOL_NAME_SEPARATOR}{mcp_tool.name}"
        self.description = (
            f"{mcp_tool.description or ''} ({server_name} MCP Server)"
        ).strip()

        # Build a dynamic Pydantic model from MCP's inputSchema
        self.parameters = _build_parameters_model(mcp_tool.inputSchema)

    async def execute(
        self,
        *,
        workspace_dir: str = "",
        mcp_manager: "MCPManager | None" = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute the MCP tool via MCPManager.

        Args:
            workspace_dir: Passed by AgentLoop (unused for remote tools).
            mcp_manager: Injected by AgentLoop via context_keys.
            **kwargs: Tool arguments from LLM.

        Returns:
            ToolResult wrapping the MCP CallToolResult.
        """
        if mcp_manager is None:
            return ToolResult.fail(
                f"MCPManager not available for tool '{self.name}'. "
                "Ensure MCP is initialized before running the agent."
            )

        client = mcp_manager.get_client(self.server_name)
        if client is None:
            return ToolResult.fail(
                f"MCP server '{self.server_name}' is not connected."
            )

        try:
            call_result = await client.call_tool(
                self.original_tool_name,
                arguments=kwargs if kwargs else None,
            )
            return _convert_call_result(call_result, self.name)
        except Exception as e:
            logger.error(f"MCP tool '{self.name}' execution failed: {e}", exc_info=True)
            return ToolResult.fail(str(e))

    def __repr__(self) -> str:
        return f"<MCPToolWrapper name={self.name!r} server={self.server_name!r}>"


# ========================================
# Result conversion
# ========================================

def _convert_call_result(
    result: mcp_types.CallToolResult,
    tool_name: str,
) -> ToolResult:
    """Convert MCP CallToolResult to wukong ToolResult.

    MCP CallToolResult has:
    - content: list of TextContent | ImageContent | AudioContent | ...
    - isError: bool

    Args:
        result: Raw result from McpClient.call_tool().
        tool_name: Qualified tool name (for error messages).

    Returns:
        ToolResult with merged text output or error.
    """
    output = _extract_text_content(result.content)

    if result.isError:
        return ToolResult.fail(
            error=output or f"MCP tool '{tool_name}' returned an error with no message",
            source="mcp",
        )

    return ToolResult.ok(
        output=output or "",
        source="mcp",
    )


def _extract_text_content(
    content: list[
        mcp_types.TextContent
        | mcp_types.ImageContent
        | mcp_types.AudioContent
        | mcp_types.ResourceLink
        | mcp_types.EmbeddedResource
    ],
) -> str:
    """Extract and merge text from MCP content blocks.

    Text blocks are joined with newlines.
    Non-text blocks (images, audio, resources) are summarized as placeholders.
    """
    parts: list[str] = []

    for block in content:
        if isinstance(block, mcp_types.TextContent):
            parts.append(block.text)
        elif isinstance(block, mcp_types.ImageContent):
            parts.append(f"[Image: {block.mimeType}]")
        elif isinstance(block, mcp_types.AudioContent):
            parts.append(f"[Audio: {block.mimeType}]")
        elif isinstance(block, mcp_types.ResourceLink):
            title = block.title or block.name or block.uri
            parts.append(f"[Resource: {title} → {block.uri}]")
        elif isinstance(block, mcp_types.EmbeddedResource):
            resource = block.resource
            if hasattr(resource, "text") and resource.text:
                parts.append(resource.text)
            else:
                mime = getattr(resource, "mimeType", "unknown")
                parts.append(f"[Embedded Resource: {mime}]")

    return "\n".join(parts)


# ========================================
# Dynamic parameters model
# ========================================

def _build_parameters_model(input_schema: dict[str, Any]) -> type[BaseModel]:
    """Build a Pydantic model class from MCP tool's inputSchema.

    Since MCP tools provide JSON Schema for their parameters, we create
    a minimal Pydantic model that passes the schema through as-is.
    This satisfies Tool.parameters requirement and enables get_json_schema().

    Args:
        input_schema: JSON Schema dict from mcp_types.Tool.inputSchema.

    Returns:
        A Pydantic BaseModel subclass whose model_json_schema() returns input_schema.
    """

    class MCPParameters(BaseModel):
        model_config = {"extra": "allow"}

        @classmethod
        def model_json_schema(cls, **kwargs: Any) -> dict[str, Any]:
            return input_schema

    return MCPParameters
