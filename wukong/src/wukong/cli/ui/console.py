"""
Console module - Rich console output utilities.

Provides a unified interface for terminal output with consistent styling.
"""

import time
from typing import Any

from rich.console import Console as RichConsole
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.theme import Theme

# Custom theme for Wukong (悟空)
wukong_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "dim": "dim",
    "highlight": "bold magenta",
    "thinking": "grey50 italic",
    "tool.name": "bold cyan",
    "tool.param": "dim cyan",
    "tool.running": "yellow",
    "tool.done": "green",
    "tool.failed": "red",
})

# Status indicator icons (using Unicode circles for cross-platform compatibility)
STATUS_ICONS = {
    "running": "●",  # Yellow circle for running
    "done": "●",     # Green circle for success
    "failed": "●",   # Red circle for failure
    "pending": "○",  # Empty circle for pending
}


class Console:
    """
    Wrapper around Rich Console with convenience methods.
    
    Provides consistent styling for different message types.
    """
    
    def __init__(self) -> None:
        self._console = RichConsole(theme=wukong_THEME)
        self._error_console = RichConsole(stderr=True, theme=wukong_THEME)
    
    @property
    def rich(self) -> RichConsole:
        """Access the underlying Rich Console for advanced usage."""
        return self._console
    
    def print(self, *args, **kwargs) -> None:
        """Print to console (wrapper around Rich print)."""
        self._console.print(*args, **kwargs)
    
    def input(self, prompt: str = "") -> str:
        """Get input from user with Rich formatting support."""
        return self._console.input(prompt)
    
    # ========================================
    # Message type methods
    # ========================================
    
    def info(self, message: str) -> None:
        """Print an info message."""
        self._console.print(f"[info][i][/info] {message}")
    
    def success(self, message: str) -> None:
        """Print a success message."""
        self._console.print(f"[success][+][/success] {message}")
    
    def warning(self, message: str) -> None:
        """Print a warning message."""
        self._console.print(f"[warning][!][/warning] {message}")
    
    def error(self, message: str) -> None:
        """Print an error message to stderr."""
        self._error_console.print(f"[error][x][/error] {message}")
    
    # ========================================
    # Rich content methods
    # ========================================
    
    def markdown(self, text: str) -> None:
        """Render and print Markdown content."""
        md = Markdown(text)
        self._console.print(md)
    
    def code(
        self,
        code: str,
        language: str = "python",
        line_numbers: bool = False,
    ) -> None:
        """Print syntax-highlighted code."""
        syntax = Syntax(
            code,
            language,
            theme="monokai",
            line_numbers=line_numbers,
        )
        self._console.print(syntax)
    
    def panel(
        self,
        content: str,
        title: str | None = None,
        border_style: str = "cyan",
    ) -> None:
        """Print content in a bordered panel."""
        panel = Panel(content, title=title, border_style=border_style)
        self._console.print(panel)

    def status(self, status: str = "Thinking..."):
        """Show a spinner status message."""
        return self._console.status(status, spinner="dots")

    # ========================================
    # Thinking/Reasoning display methods
    # ========================================
    
    def thinking(self, content: str, max_length: int = 80) -> None:
        """Display thinking/reasoning content in a single line.
        
        Content is truncated with '...' if too long.
        Not stored, only for display.
        
        Args:
            content: Thinking content to display.
            max_length: Maximum length before truncation.
        """
        if not content:
            return
        
        # Clean up: remove newlines, collapse whitespace
        clean_content = " ".join(content.split())
        
        # Truncate if needed
        if len(clean_content) > max_length:
            clean_content = clean_content[:max_length - 3] + "..."
        
        self._console.print(f"[thinking]💭 {clean_content}[/thinking]")
    
    # ========================================
    # Tool execution display methods
    # ========================================
    
    def tool_start(self, tool_name: str, params: dict[str, Any] | None = None) -> float:
        """Display tool execution start with running status.
        
        Args:
            tool_name: Name of the tool being executed.
            params: Tool parameters (optional, for displaying key info).
            
        Returns:
            Start timestamp for calculating duration.
        """
        icon = STATUS_ICONS["running"]
        param_str = self._format_tool_params(tool_name, params)
        
        self._console.print(
            f"[tool.running]{icon}[/tool.running] "
            f"[tool.name]{tool_name}[/tool.name]"
            f"{param_str}",
            end="",
        )
        return time.time()
    
    def tool_done(self, start_time: float) -> None:
        """Update tool display to show completion.
        
        Args:
            start_time: Timestamp from tool_start for duration calculation.
        """
        duration = time.time() - start_time
        duration_str = self._format_duration(duration)
        
        # Clear current line and reprint with done status
        self._console.print(
            f" [tool.done]{STATUS_ICONS['done']}[/tool.done] "
            f"[dim]{duration_str}[/dim]"
        )
    
    def tool_error(self, start_time: float, error_msg: str | None = None) -> None:
        """Update tool display to show failure.
        
        Args:
            start_time: Timestamp from tool_start for duration calculation.
            error_msg: Optional error message to display.
        """
        duration = time.time() - start_time
        duration_str = self._format_duration(duration)
        
        error_text = f" - {error_msg}" if error_msg else ""
        self._console.print(
            f" [tool.failed]{STATUS_ICONS['failed']}[/tool.failed] "
            f"[dim]{duration_str}[/dim]"
            f"[tool.failed]{error_text}[/tool.failed]"
        )
    
    def tool_result(
        self, 
        tool_name: str, 
        params: dict[str, Any] | None,
        success: bool,
        duration: float,
        error_msg: str | None = None,
    ) -> None:
        """Display complete tool execution result in one line.
        
        This is an alternative to start/done pattern for simpler usage.
        
        Args:
            tool_name: Name of the tool.
            params: Tool parameters.
            success: Whether execution succeeded.
            duration: Execution duration in seconds.
            error_msg: Error message if failed.
        """
        if success:
            icon = f"[tool.done]{STATUS_ICONS['done']}[/tool.done]"
        else:
            icon = f"[tool.failed]{STATUS_ICONS['failed']}[/tool.failed]"
        
        param_str = self._format_tool_params(tool_name, params)
        duration_str = self._format_duration(duration)
        error_text = f" [tool.failed]({error_msg})[/tool.failed]" if error_msg else ""
        
        self._console.print(
            f"{icon} [tool.name]{tool_name}[/tool.name]"
            f"{param_str} [dim]{duration_str}[/dim]{error_text}"
        )
    
    # ========================================
    # Batch tool tree display methods
    # ========================================
    
    def batch_start(self, tool_count: int, success: bool) -> None:
        """Display batch tool start with tree root.
        
        Args:
            tool_count: Number of tools in the batch.
            success: Whether the batch tool execution succeeded.
        """
        if success:
            icon = f"[tool.done]{STATUS_ICONS['done']}[/tool.done]"
        else:
            icon = f"[tool.failed]{STATUS_ICONS['failed']}[/tool.failed]"
        self._console.print(
            f"{icon} [tool.name]batch[/tool.name] "
            f"[tool.param]({tool_count} tools)[/tool.param]"
        )
    
    def batch_item(
        self,
        tool_name: str,
        params: dict[str, Any] | None,
        success: bool,
        duration: float,
        is_last: bool = False,
        error_msg: str | None = None,
    ) -> None:
        """Display a single tool result in batch tree.
        
        Args:
            tool_name: Name of the tool.
            params: Tool parameters.
            success: Whether execution succeeded.
            duration: Execution duration in seconds.
            is_last: Whether this is the last item in the batch.
            error_msg: Error message if failed.
        """
        # Tree branch character
        branch = "└─" if is_last else "├─"
        
        # Status icon
        if success:
            icon = f"[tool.done]{STATUS_ICONS['done']}[/tool.done]"
        else:
            icon = f"[tool.failed]{STATUS_ICONS['failed']}[/tool.failed]"
        
        param_str = self._format_tool_params(tool_name, params)
        duration_str = self._format_duration(duration)
        error_text = f" [tool.failed]({error_msg[:30]}...)[/tool.failed]" if error_msg and len(error_msg) > 30 else (f" [tool.failed]({error_msg})[/tool.failed]" if error_msg else "")
        
        self._console.print(
            f"  {branch} {icon} [tool.name]{tool_name}[/tool.name]"
            f"{param_str} [dim]{duration_str}[/dim]{error_text}"
        )
    
    def batch_end(self, success_count: int, total: int, total_duration: float) -> None:
        """Display batch completion summary.
        
        Args:
            success_count: Number of successful tool executions.
            total: Total number of tools.
            total_duration: Total batch duration in seconds.
        """
        duration_str = self._format_duration(total_duration)
        
        if success_count == total:
            status = f"[tool.done]{STATUS_ICONS['done']}[/tool.done]"
            summary = f"[tool.done]{success_count}/{total} succeeded[/tool.done]"
        elif success_count == 0:
            status = f"[tool.failed]{STATUS_ICONS['failed']}[/tool.failed]"
            summary = f"[tool.failed]0/{total} succeeded[/tool.failed]"
        else:
            status = f"[warning]{STATUS_ICONS['done']}[/warning]"
            summary = f"[warning]{success_count}/{total} succeeded[/warning]"
        
        self._console.print(
            f"  {status} {summary} [dim]{duration_str}[/dim]"
        )
    
    # ========================================
    # Task tool tree display methods
    # ========================================
    
    def task_start(
        self,
        agent_name: str,
        task_title: str,
        success: bool,
    ) -> None:
        """Display task header: AgentName(task description).
        
        Args:
            agent_name: Name of the subagent used.
            task_title: Brief task description.
            success: Whether the task execution succeeded.
        """
        if success:
            icon = f"[tool.done]{STATUS_ICONS['done']}[/tool.done]"
        else:
            icon = f"[tool.failed]{STATUS_ICONS['failed']}[/tool.failed]"
        
        # Capitalize agent name for display (e.g., "explore" → "Explore")
        display_name = agent_name.capitalize()
        
        # Truncate task title if too long
        if len(task_title) > 60:
            task_title = task_title[:57] + "..."
        
        self._console.print(
            f"{icon} [tool.name]{display_name}[/tool.name]"
            f"[tool.param]({task_title})[/tool.param]"
        )
    
    def task_tool_item(
        self,
        tool_name: str,
        title: str | None = None,
        status: str = "completed",
        is_last: bool = False,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Display a single tool call in task tree, with key parameters.
        
        Args:
            tool_name: Name of the tool.
            title: Tool call title/description (used as fallback if no params).
            status: Tool status ("completed", "failed", "running", "cancelled").
            is_last: Whether this is the last item in the tree.
            params: Tool parameters for displaying key info.
        """
        line = self._format_task_tool_line(tool_name, title, status, is_last, params)
        self._console.print(line)
    
    def update_task_tool_item(
        self,
        lines_back: int,
        tool_name: str,
        title: str | None = None,
        status: str = "completed",
        is_last: bool = False,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Update a previously printed task tool item in-place using ANSI cursor movement.
        
        Moves the cursor up to the target line, clears it, prints the updated
        content, then moves the cursor back to the original position.
        
        Args:
            lines_back: Number of lines above the cursor to update (1 = previous line).
            tool_name: Name of the tool.
            title: Tool call title/description.
            status: New status ("completed", "failed").
            is_last: Whether this is the last item in the tree.
            params: Tool parameters for displaying key info.
        """
        if lines_back <= 0:
            return
        
        line = self._format_task_tool_line(tool_name, title, status, is_last, params)
        self._update_line_above(lines_back, line)
    
    def task_batch_sub_item(
        self,
        tool_name: str,
        params: dict[str, Any] | None = None,
        success: bool = True,
        is_last: bool = False,
    ) -> None:
        """Display a third-level item inside a batch within a task tree.
        
        Uses deeper indentation (│  ├─ / │  └─) to show hierarchy:
          ├─ ● batch (3 tools)
          │  ├─ ● grep (pattern)
          │  └─ ● read_file (path)
        
        Args:
            tool_name: Name of the sub-tool.
            params: Tool parameters for displaying key info.
            success: Whether this sub-tool succeeded.
            is_last: Whether this is the last sub-item.
        """
        branch = "└─" if is_last else "├─"
        if success:
            icon = f"[tool.done]{STATUS_ICONS['done']}[/tool.done]"
        else:
            icon = f"[tool.failed]{STATUS_ICONS['failed']}[/tool.failed]"
        
        param_str = self._format_tool_params(tool_name, params)
        self._console.print(
            f"  │  {branch} {icon} [tool.name]{tool_name}[/tool.name]{param_str}"
        )
    
    def _format_task_tool_line(
        self,
        tool_name: str,
        title: str | None = None,
        status: str = "completed",
        is_last: bool = False,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Build the Rich markup string for a task tool tree item."""
        branch = "└─" if is_last else "├─"
        
        if status == "completed":
            icon = f"[tool.done]{STATUS_ICONS['done']}[/tool.done]"
        elif status == "failed":
            icon = f"[tool.failed]{STATUS_ICONS['failed']}[/tool.failed]"
        elif status == "running":
            icon = f"[tool.running]{STATUS_ICONS['running']}[/tool.running]"
        else:
            icon = f"[dim]{STATUS_ICONS['pending']}[/dim]"
        
        param_str = self._format_tool_params(tool_name, params) if params else ""
        if not param_str and title:
            param_str = f" [dim]{title}[/dim]"
        
        return f"  {branch} {icon} [tool.name]{tool_name}[/tool.name]{param_str}"
    
    def _update_line_above(self, lines_back: int, content: str) -> None:
        """Overwrite a previously printed line using ANSI cursor movement.
        
        Args:
            lines_back: How many lines above the current cursor to update.
            content: New Rich-markup content for that line.
        """
        out = self._console.file
        out.write(f"\x1b[{lines_back}A")   # cursor up
        out.write("\x1b[2K\r")              # clear entire line, carriage return
        out.flush()
        self._console.print(content, end="")
        out.write("\n")                     # finish the line
        if lines_back > 1:
            out.write(f"\x1b[{lines_back - 1}B")  # cursor down to original position
        out.flush()
    
    def task_end(
        self,
        success_count: int,
        total: int,
        total_duration: float,
        has_output: bool = True,
    ) -> None:
        """Display task completion summary.
        
        Args:
            success_count: Number of successful tool calls.
            total: Total number of tool calls.
            total_duration: Total task duration in seconds.
            has_output: Whether the task produced output.
        """
        duration_str = self._format_duration(total_duration)
        
        if total == 0:
            summary = "[dim]completed[/dim]"
            status = f"[tool.done]{STATUS_ICONS['done']}[/tool.done]"
        elif success_count == total:
            status = f"[tool.done]{STATUS_ICONS['done']}[/tool.done]"
            summary = f"[tool.done]{total} tool calls[/tool.done]"
        elif success_count == 0:
            status = f"[tool.failed]{STATUS_ICONS['failed']}[/tool.failed]"
            summary = f"[tool.failed]0/{total} succeeded[/tool.failed]"
        else:
            status = f"[warning]{STATUS_ICONS['done']}[/warning]"
            summary = f"[warning]{success_count}/{total} succeeded[/warning]"
        
        output_indicator = "" if has_output else " [dim](no output)[/dim]"
        
        self._console.print(
            f"  {status} {summary} [dim]{duration_str}[/dim]{output_indicator}"
        )
    
    def _format_tool_params(self, tool_name: str, params: dict[str, Any] | None) -> str:
        """Format tool parameters for display.
        
        Shows key parameters based on tool type.
        
        Args:
            tool_name: Name of the tool.
            params: Tool parameters dict.
            
        Returns:
            Formatted parameter string.
        """
        if not params:
            return ""
        
        # Define which parameters to show for each tool
        key_params = {
            "read_file": ["path"],
            "write_file": ["path"],
            "list_dir": ["path"],
            "grep": ["pattern", "path"],
            "glob": ["pattern", "path"],
            "bash": ["command"],
            "run_shell": ["command"],
            "batch": [],  # Batch shows tool count separately
            "task": ["agent", "prompt"],  # Task shows agent and prompt
        }
        
        keys_to_show = key_params.get(tool_name, list(params.keys())[:2])
        
        parts = []
        for key in keys_to_show:
            if key in params:
                value = params[key]
                # Truncate long values
                if isinstance(value, str) and len(value) > 50:
                    value = value[:47] + "..."
                parts.append(f"{value}")
        
        if parts:
            return f" [tool.param]({', '.join(parts)})[/tool.param]"
        return ""
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration for display.
        
        Args:
            seconds: Duration in seconds.
            
        Returns:
            Formatted duration string in seconds (e.g., "0s", "1.5s", "2m30s").
        """
        if seconds < 1:
            ms = int(seconds * 1000)
            return f"{ms}ms" if ms > 0 else "<1ms"
        elif seconds < 60:
            if seconds < 10:
                return f"{seconds:.1f}s"
            else:
                return f"{int(seconds)}s"
        else:
            minutes = int(seconds // 60)
            secs = seconds % 60
            return f"{minutes}m{int(secs)}s"

    # ========================================
    # Utility methods
    # ========================================
    
    def rule(self, title: str = "") -> None:
        """Print a horizontal rule."""
        self._console.rule(title)
    
    def clear(self) -> None:
        """Clear the console."""
        self._console.clear()


# Global console instance
console = Console()

