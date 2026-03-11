"""
CLI module - Command line interface for Wukong.

Usage:
    wukong              # Enter interactive session
    wukong "question"   # Single query mode
    wukong --version    # Show version
    wukong ls           # List sessions
    wukong resume       # Resume last session
    wukong fork         # Fork a session
"""

import asyncio
from typing import TYPE_CHECKING, Optional

import typer

if TYPE_CHECKING:
    from wukong.core.agent.loop import AgentLoop

from wukong import __version__
from wukong.cli.commands.session import (
    delete_session,
    fork_session,
    list_sessions,
    resume_session,
    session_app,
    show_session,
)
from wukong.cli.parser import MentionParser, ParseResult
from wukong.cli.ui.console import console


class TaskProgressHandler:
    """Real-time progress handler for subagent task execution.
    
    Displays subagent operations as they happen in a tree-style layout,
    tracks line positions for in-place status updates (running → completed),
    and supports three-level display when a subagent calls the batch tool.
    """
    
    def __init__(self) -> None:
        self._displayed: set[str] = set()
        self._tool_counts: dict[str, int] = {}
        self._status = None
        self._status_stopped = False
        # Line tracking for in-place ANSI updates
        self._line_count: int = 0
        self._tool_items: list[dict] = []
        self._done_count: int = 0
    
    def start_thinking(self) -> None:
        """Show thinking spinner."""
        self._status = console.status("Thinking...")
        self._status_stopped = False
        self._status.start()
    
    def stop_thinking(self) -> None:
        """Stop thinking spinner (idempotent)."""
        if self._status and not self._status_stopped:
            self._status.stop()
            self._status_stopped = True
    
    def __call__(self, event: dict) -> None:
        """Handle progress event from TaskTool.
        
        Event types:
          - tool_call: a new tool is about to execute (show as running/orange)
          - tool_done: a tool finished (update in-place to completed/green)
          - text: LLM text output (ignored for display)
        """
        self.stop_thinking()
        
        event_type = event.get("type")
        agent_name = event.get("agent", "unknown")
        task_title = event.get("task", "")
        task_key = f"{agent_name}|{task_title}"
        
        if event_type == "tool_call":
            self._handle_tool_call(event, task_key)
        elif event_type == "tool_done":
            self._handle_tool_done(event, task_key)
    
    def _handle_tool_call(self, event: dict, task_key: str) -> None:
        """Display a new tool as running (orange) and track its line position."""
        if task_key not in self._displayed:
            self._displayed.add(task_key)
            self._tool_counts[task_key] = 0
            console.print()
            self._line_count += 1
            console.task_start(
                agent_name=event.get("agent", "unknown"),
                task_title=event.get("task", ""),
                success=True,
            )
            self._line_count += 1
        
        self._tool_counts[task_key] = self._tool_counts.get(task_key, 0) + 1
        
        self._tool_items.append({
            "task_key": task_key,
            "name": event.get("tool", "unknown"),
            "args": event.get("args"),
            "line_num": self._line_count,
        })
        
        console.task_tool_item(
            tool_name=event.get("tool", "unknown"),
            status="running",
            params=event.get("args"),
        )
        self._line_count += 1
    
    def _handle_tool_done(self, event: dict, task_key: str) -> None:
        """Update a running tool line to completed (green) using ANSI cursor movement.
        
        For batch tools, also prints third-level sub-items below the current cursor.
        """
        if self._done_count >= len(self._tool_items):
            return
        
        item = self._tool_items[self._done_count]
        lines_back = self._line_count - item["line_num"]
        
        success = event.get("success", True)
        status = "completed" if success else "failed"
        
        if lines_back > 0:
            console.update_task_tool_item(
                lines_back=lines_back,
                tool_name=item["name"],
                status=status,
                params=event.get("args") or item.get("args"),
            )
        
        self._done_count += 1
        
        if item["name"] == "batch":
            batch_items = event.get("batch_items", [])
            for i, bi in enumerate(batch_items):
                is_last = (i == len(batch_items) - 1)
                console.task_batch_sub_item(
                    tool_name=bi.get("name", "unknown"),
                    params=bi.get("args"),
                    success=bi.get("success", True),
                    is_last=is_last,
                )
                self._line_count += 1
    
    def was_displayed(self, agent_name: str, task_title: str) -> bool:
        """Check if a task was displayed in real-time."""
        return f"{agent_name}|{task_title}" in self._displayed
    
    def get_tool_count(self, agent_name: str, task_title: str) -> int:
        """Get the number of tool calls tracked for a task."""
        return self._tool_counts.get(f"{agent_name}|{task_title}", 0)
    
    def reset(self) -> None:
        """Reset state for the next turn."""
        self._displayed.clear()
        self._tool_counts.clear()
        self._status = None
        self._status_stopped = False
        self._line_count = 0
        self._tool_items.clear()
        self._done_count = 0


# Module-level progress handler (shared across stream loop and display functions)
_task_progress = TaskProgressHandler()


# Create the main Typer app
app = typer.Typer(
    name="wukong",
    help="A powerful CLI agent tool with multi-LLM support.",
    add_completion=False,
    no_args_is_help=False,  # Allow running without arguments
)

# Register session subcommand group (wukong session ...)
app.add_typer(session_app, name="session")

# Register shortcut commands at root level (wukong ls, wukong resume, etc.)
app.command("ls")(list_sessions)
app.command("resume")(resume_session)
app.command("fork")(fork_session)


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"[bold]wukong[/bold] version [cyan]{__version__}[/cyan]")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    query: Optional[str] = typer.Option(
        None,
        "--query",
        "-q",
        help="Question or instruction to send to the agent.",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """
    Wukong - AI Coding Assistant.

    Run without arguments to enter interactive mode.
    Use -q/--query for single query mode.
    """
    # If a subcommand is invoked, skip the default behavior
    if ctx.invoked_subcommand is not None:
        return

    if query:
        # Single query mode
        asyncio.run(_handle_single_query_async(query))
    else:
        # Interactive session mode
        _enter_interactive_session()


async def _handle_single_query_async(query: str) -> None:
    """Handle a single query and exit (async version)."""
    from wukong.core.agent.loop import AgentLoop, MentionInput
    from wukong.core.llm.router import get_llm_backend
    from wukong.core.llm.schema import LLMResponse
    from wukong.core.session import SessionManager
    
    # Initialize
    from wukong.core.config import get_settings
    from wukong.core.mcp.config import MCPSettings, load_mcp_settings
    from wukong.core.mcp.manager import MCPManager
    from wukong.core.tools import get_registry as get_tool_registry
    manager = SessionManager()
    session = manager.create_session(title=query[:30] + "...")
    llm = get_llm_backend()
    tool_registry = get_tool_registry()
    _app_settings = get_settings()
    if _app_settings.mcp.enabled:
        _mcp_cfg = load_mcp_settings(_app_settings.mcp.config_file)
        mcp_manager = MCPManager(_mcp_cfg)
        await mcp_manager.connect_all(tool_registry)
    else:
        mcp_manager = MCPManager(MCPSettings())
    loop = AgentLoop(llm, session, manager, on_progress=_task_progress, mcp_manager=mcp_manager)
    parser = MentionParser()
    
    console.info(f"Processing query in session [bold]{session.session_id}[/bold]...")
    console.print(f"\n[dim]Query:[/dim] {query}\n")
    
    # Parse @mentions
    parse_result = parser.parse(query)
    _show_context_feedback(parse_result)
    
    mentions = [
        MentionInput(provider=m.provider, query=m.query)
        for m in parse_result.mentions
    ]
    
    console.print()
    try:
        _task_progress.reset()
        _task_progress.start_thinking()
        
        is_thinking = False
        accumulated_reasoning = ""
        
        try:
            async for chunk in loop.run(parse_result.clean_text, mentions=mentions):
                _task_progress.stop_thinking()
                
                if chunk.reasoning_content:
                    accumulated_reasoning += chunk.reasoning_content
                    if not is_thinking:
                        is_thinking = True
                    continue
                
                if chunk.content:
                    if is_thinking and accumulated_reasoning:
                        console.thinking(accumulated_reasoning)
                        accumulated_reasoning = ""
                        is_thinking = False
                    
                    if chunk.content.startswith("[Tool:"):
                        _display_tool_result(chunk.content)
                    else:
                        console.print(chunk.content, end="")
        finally:
            _task_progress.stop_thinking()
                
        console.print()
    except Exception as e:
        error_str = str(e).lower()
        if "ssl" in error_str or "decryption" in error_str or "connection" in error_str:
            console.error("Network connection error: connection to LLM service interrupted")
            console.warning("Tip: This may be caused by network instability. Please check your connection and retry.")
        else:
            console.error(f"Error: {e}")
    
    console.print("\n" + "[dim]-[/dim]" * 40)
    await mcp_manager.disconnect_all()


def _enter_interactive_session() -> None:
    """Enter interactive REPL session."""
    from wukong.core.agent.loop import AgentLoop, MentionInput
    from wukong.core.llm.router import get_llm_backend
    from wukong.core.session import SessionManager
    
    console.print()
    console.print("[bold cyan]Wukong[/bold cyan] - AI Coding Assistant")
    console.print(f"[dim]Version {__version__}[/dim]")
    console.print()
    
    # Initialize LLM, Session, and AgentLoop
    try:
        llm = get_llm_backend()
        console.print(f"[dim]LLM: {llm.__class__.__name__}[/dim]")
    except Exception as e:
        console.error(f"Failed to initialize LLM: {e}")
        console.warning("Falling back to MockLLM for testing.")
        from wukong.core.llm.adapters.mock import MockLLM
        from wukong.core.config import get_settings
        settings = get_settings()
        llm = MockLLM(
            model=settings.llm.model,
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
        )
    
    manager = SessionManager()
    session = manager.create_session(title="Interactive Session")
    console.print(f"[dim]Session: {session.session_id}[/dim]")

    # Use a persistent event loop so MCP connections survive across queries.
    # asyncio.run() would close the loop after each query, destroying McpClient sessions.
    event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(event_loop)

    from wukong.core.config import get_settings
    from wukong.core.mcp.config import MCPSettings, load_mcp_settings
    from wukong.core.mcp.manager import MCPManager
    from wukong.core.tools import get_registry as get_tool_registry
    _app_settings = get_settings()
    tool_registry = get_tool_registry()
    if _app_settings.mcp.enabled:
        _mcp_cfg = load_mcp_settings(_app_settings.mcp.config_file)
        mcp_manager = MCPManager(_mcp_cfg)
        mcp_counts = event_loop.run_until_complete(mcp_manager.connect_all(tool_registry))
        if mcp_counts:
            console.print(
                f"[dim]MCP: {len(mcp_counts)} server(s), "
                f"{sum(mcp_counts.values())} tool(s)[/dim]"
            )
    else:
        mcp_manager = MCPManager(MCPSettings())
        console.print("[dim]MCP: disabled[/dim]")

    loop = AgentLoop(llm, session, manager, on_progress=_task_progress, mcp_manager=mcp_manager)
    parser = MentionParser()
    
    console.print()
    console.print("[dim]Type your question or [bold]/help[/bold] for commands. Press Ctrl+C to exit.[/dim]")
    console.print("[dim]Use @file <path> to include file context.[/dim]")
    console.print("[dim]-[/dim]" * 40)
    console.print()

    # REPL loop
    try:
        while True:
            try:
                # Basic input
                user_input = console.input("[bold green]>[/bold green] ").strip()
                
                if not user_input:
                    continue
                
                # Handle slash commands
                if user_input.startswith("/"):
                    try:
                        if _handle_repl_command(user_input):
                            break
                    except typer.Exit as e:
                        if e.code != 0:
                            console.error(f"Command exited with code {e.code}")
                    except Exception as e:
                        console.error(f"An error occurred during command execution: {e}")
                    continue

                # Process user input with AgentLoop (reuse persistent event_loop)
                event_loop.run_until_complete(_process_user_input(loop, parser, user_input))
                
            except EOFError:
                break
            except Exception as e:
                console.error(f"Error: {e}")
                
    except KeyboardInterrupt:
        console.print("\n\n[dim]Interrupted. Goodbye![/dim]")
    finally:
        loop.save()
        event_loop.run_until_complete(mcp_manager.disconnect_all())
        event_loop.close()


async def _process_user_input(
    loop: "AgentLoop",
    parser: MentionParser,
    user_input: str,
) -> None:
    """Process user input and stream response from AgentLoop.
    
    Args:
        loop: AgentLoop instance
        parser: MentionParser instance
        user_input: Raw user input (may contain @mentions)
    """
    from wukong.core.agent.loop import MentionInput
    from wukong.core.llm.schema import LLMResponse
    
    # Parse @mentions
    parse_result = parser.parse(user_input)
    
    # Show context loading feedback
    _show_context_feedback(parse_result)
    
    # Convert to MentionInput
    mentions = [
        MentionInput(provider=m.provider, query=m.query)
        for m in parse_result.mentions
    ]
    
    # Call AgentLoop and stream response
    console.print()
    try:
        _task_progress.reset()
        _task_progress.start_thinking()
        
        is_thinking = False
        accumulated_reasoning = ""
        
        try:
            async for chunk in loop.run(parse_result.clean_text, mentions=mentions):
                _task_progress.stop_thinking()
                
                if chunk.reasoning_content:
                    accumulated_reasoning += chunk.reasoning_content
                    if not is_thinking:
                        is_thinking = True
                    continue
                
                if chunk.content:
                    if is_thinking and accumulated_reasoning:
                        console.thinking(accumulated_reasoning)
                        accumulated_reasoning = ""
                        is_thinking = False
                    
                    if chunk.content.startswith("[Tool:"):
                        console.print()
                        _display_tool_result(chunk.content)
                    else:
                        console.print(chunk.content, end="")
        finally:
            _task_progress.stop_thinking()
                
        console.print()
    except Exception as e:
        error_str = str(e).lower()
        if "ssl" in error_str or "decryption" in error_str or "connection" in error_str:
            console.error("Network connection error: connection to LLM service interrupted")
            console.warning("Tip: This may be caused by network instability. Please check your connection and retry.")
        else:
            console.error(f"Agent error: {e}")
    console.print()


def _show_context_feedback(parse_result: ParseResult) -> None:
    """Show UI feedback for loaded context.
    
    Displays "Read <file>" message for each @mention.
    
    Args:
        parse_result: Result from MentionParser
    """
    if not parse_result.mentions:
        return
    
    for mention in parse_result.mentions:
        # Format feedback based on provider type (avoid emoji for Windows compatibility)
        if mention.provider == "file":
            console.print(f"[dim][FILE] Read {mention.query}[/dim]")
        elif mention.provider == "url":
            console.print(f"[dim][URL] Fetching {mention.query}[/dim]")
        elif mention.provider == "folder":
            console.print(f"[dim][DIR] Scanning {mention.query}[/dim]")
        elif mention.provider == "codebase":
            console.print(f"[dim][SEARCH] Searching: {mention.query}[/dim]")
        else:
            console.print(f"[dim][CTX] Loading @{mention.provider} {mention.query}[/dim]")


def _display_tool_result(content: str) -> None:
    """Parse and display tool result with formatted output.
    
    Parses content like "[Tool: name|success|duration|args_json]\nresult..."
    and displays it with status indicators and key parameters.
    
    For batch tools, displays results in a tree structure.
    
    Args:
        content: Tool result content from AgentLoop
    """
    import json
    import re
    
    # Parse new format: [Tool: name|success|duration|args_json]\n
    # Use ]\n as delimiter to avoid matching ] inside JSON (e.g., arrays)
    match = re.match(r'\[Tool: (\w+)\|([01])\|([\d.]+)\|(.*?)\]\n', content, re.DOTALL)
    if not match:
        # Try old format for backwards compatibility
        old_match = re.match(r'\[Tool: (\w+)\]', content)
        if old_match:
            tool_name = old_match.group(1)
            result_content = content[old_match.end():].strip()
            is_error = result_content.startswith("Error:")
            console.tool_result(
                tool_name=tool_name,
                params={},
                success=not is_error,
                duration=0,
                error_msg=result_content[:50] if is_error else None,
            )
            return
        # Fallback to plain display
        console.print(content, end="")
        return
    
    tool_name = match.group(1)
    success = match.group(2) == "1"
    duration = float(match.group(3))
    
    # Parse args JSON
    try:
        args_json = match.group(4)
        params = json.loads(args_json)
    except json.JSONDecodeError:
        params = {}
    
    result_content = content[match.end():].strip()
    
    # Special handling for batch tool - display as tree
    if tool_name == "batch":
        _display_batch_result(params, result_content, duration, success)
        return
    
    # Special handling for task tool - display subagent results as tree
    if tool_name == "task":
        _display_task_result(params, result_content, duration, success)
        return
    
    # Extract error message if failed
    error_msg = None
    if not success and result_content.startswith("Error:"):
        error_msg = result_content.replace("Error: ", "", 1)[:60]
        if len(result_content) > 60:
            error_msg += "..."
    
    # Display formatted result
    console.tool_result(
        tool_name=tool_name,
        params=params,
        success=success,
        duration=duration,
        error_msg=error_msg,
    )


def _display_task_result(params: dict, result_content: str, total_duration: float, success: bool) -> None:
    """Display task tool result as a tree structure.
    
    If the task was already displayed in real-time via the progress handler,
    only the summary line is shown to avoid duplication.
    
    Args:
        params: Task tool parameters (contains agent, prompt)
        result_content: Result content from ToolResult (contains <task_metadata> block)
        total_duration: Total task execution duration
        success: Whether the task tool execution succeeded
    """
    import json
    import re
    
    agent_name = params.get("agent", "unknown")
    prompt = params.get("prompt", "")
    # Match the same truncation as TaskTool (50 chars)
    task_title = prompt[:50] + ("..." if len(prompt) > 50 else "")
    
    # Parse <task_metadata> block
    metadata_match = re.search(
        r'<task_metadata>\s*(.*?)\s*</task_metadata>',
        result_content,
        re.DOTALL,
    )
    
    summary = []
    final_output = result_content
    
    if metadata_match:
        try:
            metadata = json.loads(metadata_match.group(1).strip())
            summary = metadata.get("summary", [])
            final_output = result_content[metadata_match.end():].strip()
        except json.JSONDecodeError:
            pass
    
    success_count = sum(
        1 for item in summary
        if item.get("status") == "completed"
    )
    
    # If real-time progress was shown, only display summary line
    if _task_progress.was_displayed(agent_name, task_title):
        # Use handler's tracked count (reliable) over metadata summary
        live_count = _task_progress.get_tool_count(agent_name, task_title)
        total_count = live_count if live_count > 0 else len(summary)
        # For live display, assume all completed unless metadata says otherwise
        ok_count = success_count if success_count > 0 else total_count
        
        console.task_end(
            success_count=ok_count,
            total=total_count,
            total_duration=total_duration,
            has_output=bool(final_output),
        )
        return
    
    # Full display (no real-time progress was available)
    console.task_start(
        agent_name=agent_name,
        task_title=task_title,
        success=success,
    )
    
    max_display = 10
    display_items = summary[:max_display]
    hidden_count = len(summary) - max_display if len(summary) > max_display else 0
    
    for i, item in enumerate(display_items):
        is_last = (i == len(display_items) - 1) and hidden_count == 0
        tool_name = item.get("tool", "unknown")
        item_args = item.get("args") or {}
        console.task_tool_item(
            tool_name=tool_name,
            title=item.get("title"),
            status=item.get("status", "completed"),
            is_last=is_last,
            params=item_args if item_args else None,
        )
        # Three-level display: expand batch sub-items
        if tool_name == "batch" and item_args:
            sub_calls = item_args.get("tool_calls", [])
            for j, tc in enumerate(sub_calls):
                if isinstance(tc, dict):
                    console.task_batch_sub_item(
                        tool_name=tc.get("name", "unknown"),
                        params=tc.get("arguments"),
                        success=item.get("status") == "completed",
                        is_last=(j == len(sub_calls) - 1),
                    )
    
    if hidden_count > 0:
        console.print(f"  └─ [dim]... and {hidden_count} more tool calls[/dim]")
    
    console.task_end(
        success_count=success_count,
        total=len(summary),
        total_duration=total_duration,
        has_output=bool(final_output),
    )


def _display_batch_result(params: dict, result_content: str, total_duration: float, success: bool) -> None:
    """Display batch tool result as a tree structure.
    
    Args:
        params: Batch tool parameters (contains tool_calls)
        result_content: Result content from ToolResult
        total_duration: Total batch execution duration
        success: Whether the batch tool execution succeeded
    """
    import re
    
    # Get original tool_calls from params (this is the source of truth for arguments)
    tool_calls = params.get("tool_calls", [])
    
    # Parse status info from result_content
    # Format: "Batch execution completed: X/Y succeeded\n\n  [OK/FAIL] tool_name..."
    # Build a map: tool_name -> list of (success, error) for tools with same name
    status_map: dict[str, list[tuple[bool, str | None]]] = {}
    current_tool = None
    
    for line in result_content.strip().split("\n"):
        line = line.strip()
        if line.startswith("[OK]") or line.startswith("[FAIL]"):
            match = re.match(r'\[(OK|FAIL)\]\s+(\w+)', line)
            if match:
                is_ok = match.group(1) == "OK"
                name = match.group(2)
                if name not in status_map:
                    status_map[name] = []
                status_map[name].append((is_ok, None))
                current_tool = (name, len(status_map[name]) - 1)
        elif line.startswith("Error:") and current_tool:
            name, idx = current_tool
            old_success, _ = status_map[name][idx]
            status_map[name][idx] = (old_success, line.replace("Error: ", "", 1))
    
    # Build display items from tool_calls, matching status by name and order
    # Track how many times each tool name has been seen
    name_counts: dict[str, int] = {}
    display_items = []
    
    for tc in tool_calls:
        if not isinstance(tc, dict):
            continue
        
        name = tc.get("name", "unknown")
        arguments = tc.get("arguments", {})
        
        # Get status for this tool (by name and occurrence order)
        count = name_counts.get(name, 0)
        name_counts[name] = count + 1
        
        tool_success = True
        tool_error = None
        if name in status_map and count < len(status_map[name]):
            tool_success, tool_error = status_map[name][count]
        
        display_items.append({
            "name": name,
            "arguments": arguments,
            "success": tool_success,
            "error": tool_error,
        })
    
    # Show batch header
    console.batch_start(len(display_items), success)
    
    # Display each tool
    for i, item in enumerate(display_items):
        is_last = (i == len(display_items) - 1)
        console.batch_item(
            tool_name=item["name"],
            params=item["arguments"],
            success=item["success"],
            duration=0,  # Individual durations not tracked
            is_last=is_last,
            error_msg=item["error"],
        )
    
    # Show summary
    success_count = sum(1 for item in display_items if item["success"])
    console.batch_end(success_count, len(display_items), total_duration)


def _handle_repl_command(command_str: str) -> bool:
    """
    Handle slash commands in REPL.
    Returns: True if the REPL should exit, False otherwise.
    """
    parts = command_str.split()
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd in ("/exit", "/quit", "/q"):
        console.print("\n[dim]Goodbye![/dim]")
        return True

    elif cmd == "/help":
        _show_repl_help()

    elif cmd == "/ls":
        list_sessions(here=True)

    elif cmd == "/show":
        try:
            session_id = args[0] if args else None
            show_session(session_id=session_id)
        except IndexError:
            console.error("Usage: /show [session_id]")

    elif cmd == "/resume":
        try:
            session_id = args[0] if args else None
            resume_session(session_id=session_id)
        except Exception as e:
            console.error(f"Failed to resume session: {e}")

    elif cmd == "/fork":
        try:
            session_id = args[0] if args else None
            fork_session(session_id=session_id)
        except Exception as e:
            console.error(f"Failed to fork session: {e}")

    elif cmd == "/delete":
        if not args:
            console.error("Usage: /delete <session_id>")
        else:
            delete_session(session_id=args[0])

    else:
        console.error(f"Unknown command: {cmd}. Type [bold]/help[/bold] for available commands.")

    return False


def _show_repl_help() -> None:
    """Show available REPL commands."""
    from rich.table import Table
    
    table = Table(title="Available Commands", box=None, show_header=False)
    table.add_column("Command", style="cyan")
    table.add_column("Description", style="dim")
    
    table.add_row("/ls", "List sessions in current workspace")
    table.add_row("/show [id]", "Show session details and recent messages")
    table.add_row("/resume [id]", "Switch to a specific session")
    table.add_row("/fork [id]", "Clone a session history")
    table.add_row("/delete <id>", "Delete a session")
    table.add_row("/help", "Show this help message")
    table.add_row("/exit", "Exit the assistant")
    table.add_row("", "")
    table.add_row("@file <path>", "Include file content as context")
    table.add_row("@url <url>", "Include web page content (coming soon)")
    table.add_row("@codebase <query>", "Search codebase (coming soon)")
    
    console.print(table)
