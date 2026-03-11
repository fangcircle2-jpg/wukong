"""Bash tool - Execute shell commands."""

import asyncio
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from wukong.core.tools.base import Tool, ToolResult


def _load_description() -> str:
    """Load tool description from text file."""
    desc_file = Path(__file__).parent / "bash.txt"
    if desc_file.exists():
        return desc_file.read_text(encoding="utf-8").strip()
    return "Execute shell commands."


class BashParams(BaseModel):
    """Parameters for bash tool."""
    command: str = Field(description="The shell command to execute")
    workdir: str = Field(default="", description="Working directory for command execution (relative to workspace)")
    timeout: int = Field(default=120000, description="Command timeout in milliseconds")


class BashTool(Tool):
    """Tool to execute shell commands.
    
    Runs commands in a subprocess and captures output.
    Supports timeout and working directory configuration.
    
    Examples:
        - "ls -la" - List files in detail
        - "git status" - Check git status
        - "python --version" - Check Python version
        - "npm install" - Install npm packages
    """
    
    name = "bash"
    description = _load_description()
    parameters = BashParams
    
    async def execute(
        self,
        *,
        workspace_dir: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a shell command.
        
        Args:
            workspace_dir: Workspace directory path.
            **kwargs: Tool parameters (command, working_dir, timeout).
            
        Returns:
            ToolResult with command output or error.
        """
        # Validate parameters
        try:
            params = self.validate_params(**kwargs)
        except Exception as e:
            return ToolResult.fail(f"Invalid parameters: {e}")
        
        # Resolve working directory
        cwd = params.workdir
        if cwd:
            if workspace_dir and not os.path.isabs(cwd):
                cwd = os.path.join(workspace_dir, cwd)
        else:
            cwd = workspace_dir or os.getcwd()
        
        # Check working directory exists
        if not os.path.isdir(cwd):
            return ToolResult.fail(f"Working directory not found: {cwd}")
        
        # Execute command
        try:
            process = await asyncio.create_subprocess_shell(
                params.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            
            # Convert timeout from milliseconds to seconds
            timeout_seconds = params.timeout / 1000
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult.fail(
                    f"Command timed out after {params.timeout}ms",
                    command=params.command,
                    timeout=params.timeout,
                )
            
            # Decode output
            stdout_text = stdout.decode("utf-8", errors="replace").strip()
            stderr_text = stderr.decode("utf-8", errors="replace").strip()
            
            # Build output
            exit_code = process.returncode
            output_parts = []
            
            if stdout_text:
                output_parts.append(stdout_text)
            
            if stderr_text:
                if stdout_text:
                    output_parts.append(f"\n[stderr]\n{stderr_text}")
                else:
                    output_parts.append(f"[stderr]\n{stderr_text}")
            
            output = "\n".join(output_parts) if output_parts else "(no output)"
            
            # Add exit code info if non-zero
            if exit_code != 0:
                output += f"\n\n[exit code: {exit_code}]"
            
            return ToolResult.ok(
                output,
                command=params.command,
                exit_code=exit_code,
                cwd=cwd,
            )
            
        except Exception as e:
            return ToolResult.fail(f"Command execution failed: {e}")
