"""Batch tool - Execute multiple tools in parallel."""

import asyncio
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from wukong.core.tools.base import Tool, ToolResult


def _load_description() -> str:
    """Load tool description from text file."""
    desc_file = Path(__file__).parent / "batch.txt"
    if desc_file.exists():
        return desc_file.read_text(encoding="utf-8").strip()
    return "Execute multiple tools in parallel."


class ToolCallInput(BaseModel):
    """Single tool call input."""
    name: str = Field(description="Tool name to execute")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class BatchParams(BaseModel):
    """Parameters for batch tool."""
    tool_calls: list[ToolCallInput] = Field(
        description="Array of tool calls to execute in parallel"
    )


# Maximum concurrent tool executions
MAX_CONCURRENT = 10

# Tools that cannot be called from batch (prevent recursion)
BLOCKED_TOOLS = {"batch"}


class BatchTool(Tool):
    """Tool to execute multiple tools in parallel.
    
    Runs up to 10 tools concurrently for efficiency.
    Each tool executes independently - failures don't affect others.
    
    Returns a summary; detailed results stored as Parts.
    """
    
    name = "batch"
    description = _load_description()
    parameters = BatchParams
    context_keys = ["tool_registry"]
    
    async def execute(
        self,
        *,
        workspace_dir: str = "",
        tool_registry: Any = None,  # ToolRegistry passed at runtime
        message_id: str | None = None,  # For Part storage (optional)
        **kwargs: Any,
    ) -> ToolResult:
        """Execute multiple tools in parallel.
        
        Args:
            workspace_dir: Workspace directory path.
            tool_registry: ToolRegistry instance for looking up tools.
            message_id: Parent message ID for Part storage.
            **kwargs: Tool parameters (tool_calls).
            
        Returns:
            ToolResult with execution summary.
        """
        # Validate parameters
        try:
            params = self.validate_params(**kwargs)
        except Exception as e:
            return ToolResult.fail(f"Invalid parameters: {e}")
        
        # Check tool_registry is provided
        if tool_registry is None:
            return ToolResult.fail("tool_registry is required for batch execution")
        
        tool_calls = params.tool_calls
        
        # Validate: no empty batch
        if not tool_calls:
            return ToolResult.fail("tool_calls array is empty")
        
        # Validate: check for blocked tools
        for tc in tool_calls:
            if tc.name in BLOCKED_TOOLS:
                return ToolResult.fail(
                    f"Tool '{tc.name}' cannot be called from batch (recursion not allowed)"
                )
        
        # Validate: check all tools exist
        missing_tools = []
        for tc in tool_calls:
            if tool_registry.get(tc.name) is None:
                missing_tools.append(tc.name)
        
        if missing_tools:
            return ToolResult.fail(
                f"Unknown tools: {', '.join(missing_tools)}"
            )
        
        # Execute tools in parallel with concurrency limit
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        
        async def execute_single(index: int, tc: ToolCallInput) -> dict[str, Any]:
            """Execute a single tool call with semaphore."""
            async with semaphore:
                tool = tool_registry.get(tc.name)
                try:
                    result = await tool.execute(
                        workspace_dir=workspace_dir,
                        **tc.arguments,
                    )
                    return {
                        "index": index,
                        "name": tc.name,
                        "success": result.success,
                        "output": result.output if result.success else None,
                        "error": result.error if not result.success else None,
                    }
                except Exception as e:
                    return {
                        "index": index,
                        "name": tc.name,
                        "success": False,
                        "output": None,
                        "error": str(e),
                    }
        
        # Run all tool calls concurrently
        tasks = [
            execute_single(i, tc)
            for i, tc in enumerate(tool_calls)
        ]
        results = await asyncio.gather(*tasks)
        
        # Sort results by original index
        results.sort(key=lambda r: r["index"])
        
        # TODO: Store detailed results as Parts (when PartManager is implemented)
        # for result in results:
        #     part = Part(
        #         message_id=message_id,
        #         part_type=PartType.TOOL_RESULT,
        #         data=result,
        #     )
        #     await part_manager.save(part)
        
        # Build output with full results
        success_count = sum(1 for r in results if r["success"])
        failure_count = len(results) - success_count
        
        output_lines = [
            f"Batch execution completed: {success_count}/{len(results)} succeeded",
            "",
        ]
        
        # Include full output for each tool
        for i, r in enumerate(results):
            tc = tool_calls[i]
            status = "OK" if r["success"] else "FAIL"
            
            # Format tool call info
            args_brief = ", ".join(f"{k}={v!r}" for k, v in tc.arguments.items())
            if len(args_brief) > 60:
                args_brief = args_brief[:57] + "..."
            
            output_lines.append(f"  [{status}] {r['name']}({args_brief})")
            
            if r["success"] and r["output"]:
                # Include actual output content
                output_lines.append(f"    {r['output']}")
            elif not r["success"] and r["error"]:
                output_lines.append(f"    Error: {r['error']}")
            
            output_lines.append("")  # Blank line between results
        
        output = "\n".join(output_lines)
        
        return ToolResult.ok(
            output,
            total=len(results),
            success_count=success_count,
            failure_count=failure_count,
            results=results,
        )
