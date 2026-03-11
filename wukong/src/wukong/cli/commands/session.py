"""
Session commands - ls, resume, fork.

Provides CLI commands for session management.
"""

from datetime import datetime
from typing import Optional, Annotated

import typer
from rich.table import Table

from wukong.cli.ui.console import console
from wukong.core.session import SessionManager

# Create session command group
session_app = typer.Typer(
    name="session",
    help="Session management commands.",
    no_args_is_help=True,
)


def _get_manager() -> SessionManager:
    """Get session manager for current workspace."""
    return SessionManager()


def _format_time_ago(dt: datetime) -> str:
    """Format datetime as relative time string."""
    now = datetime.now()
    diff = now - dt

    seconds = diff.total_seconds()
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} min ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days > 1 else ''} ago"
    else:
        return dt.strftime("%Y-%m-%d")


@session_app.command("ls")
def list_sessions(
    limit: Annotated[int, typer.Option("--limit", "-n", help="Maximum number of sessions to show.")] = 20,
    here: Annotated[bool, typer.Option("--here", "-h", help="Only show sessions from current workspace.")] = False,
) -> None:
    """List all sessions.

    Shows sessions sorted by last updated time (newest first).
    """
    manager = _get_manager()
    sessions = manager.list_sessions(limit=limit, workspace_filter=here)

    if not sessions:
        console.info("No sessions found.")
        if here:
            console.print("[dim]Try without --here to see all sessions.[/dim]")
        return

    # Get last active session ID
    last_active_id = manager.get_last_active_session_id()

    # Create table
    table = Table(
        title="Sessions",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
    )

    table.add_column("ID", style="dim", width=14)
    table.add_column("Title", min_width=20, max_width=40)
    table.add_column("Model", style="cyan", width=15)
    table.add_column("Messages", justify="right", width=8)
    table.add_column("Updated", style="dim", width=12)

    for s in sessions:
        # Mark last active session
        session_id = s.session_id
        if session_id == last_active_id:
            session_id = f"[bold green]{session_id}[/bold green] *"

        # Truncate title if too long
        title = s.title
        if len(title) > 38:
            title = title[:35] + "..."

        table.add_row(
            session_id,
            title,
            s.model_name or "-",
            str(s.message_count),
            _format_time_ago(s.updated_at),
        )

    console.print()
    console.print(table)
    console.print()
    console.print("[dim](* = last active)[/dim]")


@session_app.command("resume")
def resume_session(
    session_id: Annotated[Optional[str], typer.Argument(help="Session ID to resume. If not provided, resumes the last active session.")] = None,
    query: Annotated[Optional[str], typer.Argument(help="Optional query to continue the conversation.")] = None,
) -> None:
    """Resume a previous session.

    If no session ID is provided, resumes the most recently active session.

    Examples:
        wukong resume              # Resume last active session
        wukong resume abc123       # Resume specific session
        wukong resume abc123 "继续上次的任务"
    """
    manager = _get_manager()

    # Resume session
    session = manager.resume_session(session_id)

    if session is None:
        if session_id:
            console.error(f"Session '{session_id}' not found.")
        else:
            console.error("No sessions to resume.")
            console.info("Create a new session by running: wukong")
        raise typer.Exit(1)

    # Show session info
    console.success(f"Resumed session: [bold]{session.session_id}[/bold]")
    console.print(f"  Title: {session.title}")
    console.print(f"  Messages: {len(session.history)}")
    if session.model_name:
        console.print(f"  Model: {session.model_name}")
    console.print()

    if query:
        # TODO: Continue conversation with the query
        console.info(f"Query: {query}")
        console.warning("Agent not yet implemented. Query will be processed when agent is ready.")
    else:
        # TODO: Enter interactive mode with resumed session
        console.info("Entering interactive mode...")
        console.warning("Interactive mode not yet implemented.")


@session_app.command("fork")
def fork_session(
    session_id: Annotated[Optional[str], typer.Argument(help="Session ID to fork. If not provided, forks the last active session.")] = None,
    title: Annotated[Optional[str], typer.Option("--title", "-t", help="Title for the new forked session.")] = None,
) -> None:
    """Fork (copy) an existing session.

    Creates a new session with a copy of the conversation history.
    Useful for exploring alternative approaches without losing the original.

    Examples:
        wukong fork                    # Fork last active session
        wukong fork abc123             # Fork specific session
        wukong fork abc123 -t "新方案"  # Fork with custom title
    """
    manager = _get_manager()

    # Get source session ID
    source_id = session_id
    if source_id is None:
        source_id = manager.get_last_active_session_id()
        if source_id is None:
            console.error("No sessions to fork.")
            console.info("Create a new session by running: wukong")
            raise typer.Exit(1)

    # Fork session
    new_session = manager.fork_session(source_id, new_title=title)

    if new_session is None:
        console.error(f"Session '{source_id}' not found.")
        raise typer.Exit(1)

    # Show result
    console.success("Session forked successfully!")
    console.print()
    console.print(f"  [dim]From:[/dim] {source_id}")
    console.print(f"  [dim]To:[/dim]   [bold green]{new_session.session_id}[/bold green]")
    console.print(f"  [dim]Title:[/dim] {new_session.title}")
    console.print(f"  [dim]Messages:[/dim] {len(new_session.history)}")
    console.print()
    console.info(f"Resume with: wukong resume {new_session.session_id}")


@session_app.command("delete")
def delete_session(
    session_id: Annotated[str, typer.Argument(help="Session ID to delete.")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation prompt.")] = False,
) -> None:
    """Delete a session.

    This action cannot be undone.

    Examples:
        wukong session delete abc123
        wukong session delete abc123 -f  # Skip confirmation
    """
    manager = _get_manager()

    # Check if session exists
    session = manager.get_session(session_id)
    if session is None:
        console.error(f"Session '{session_id}' not found.")
        raise typer.Exit(1)

    # Confirm deletion
    if not force:
        console.print(f"Session: [bold]{session_id}[/bold]")
        console.print(f"Title: {session.title}")
        console.print(f"Messages: {len(session.history)}")
        console.print()

        confirm = typer.confirm("Are you sure you want to delete this session?")
        if not confirm:
            console.info("Cancelled.")
            raise typer.Exit(0)

    # Delete
    result = manager.delete_session(session_id)
    if result:
        console.success(f"Session '{session_id}' deleted.")
    else:
        console.error("Failed to delete session.")
        raise typer.Exit(1)


@session_app.command("show")
def show_session(
    session_id: Annotated[Optional[str], typer.Argument(help="Session ID to show. If not provided, shows the last active session.")] = None,
) -> None:
    """Show session details.

    Displays session metadata and recent messages.

    Examples:
        wukong session show          # Show last active session
        wukong session show abc123   # Show specific session
    """
    manager = _get_manager()

    # Get session
    target_id = session_id or manager.get_last_active_session_id()
    if target_id is None:
        console.error("No session to show.")
        raise typer.Exit(1)

    session = manager.get_session(target_id)
    if session is None:
        console.error(f"Session '{target_id}' not found.")
        raise typer.Exit(1)

    # Show session info
    console.print()
    console.panel(
        f"[bold]Session ID:[/bold] {session.session_id}\n"
        f"[bold]Title:[/bold] {session.title}\n"
        f"[bold]Workspace:[/bold] {session.workspace_directory}\n"
        f"[bold]Model:[/bold] {session.model_name or 'Not set'}\n"
        f"[bold]Messages:[/bold] {len(session.history)}\n"
        f"[bold]Created:[/bold] {session.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"[bold]Updated:[/bold] {session.updated_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"[bold]Active:[/bold] {'Yes' if session.is_active else 'No'}\n"
        f"[bold]Parent:[/bold] {session.parent_session_id or 'None'}",
        title="Session Details",
        border_style="cyan",
    )

    # Show recent messages
    if session.history:
        console.print()
        console.print("[bold]Recent Messages:[/bold]")
        console.print()

        # Show last 5 messages
        recent = session.history[-5:]
        for item in recent:
            role = item.message.role.value.upper()
            content = item.message.content

            # Truncate long messages
            if len(content) > 100:
                content = content[:97] + "..."

            # Color by role
            if item.message.role.value == "user":
                console.print(f"  [green]{role}:[/green] {content}")
            elif item.message.role.value == "assistant":
                console.print(f"  [cyan]{role}:[/cyan] {content}")
            elif item.message.role.value == "system":
                console.print(f"  [yellow]{role}:[/yellow] {content}")
            else:
                console.print(f"  [dim]{role}:[/dim] {content}")

        if len(session.history) > 5:
            console.print(f"\n  [dim]... and {len(session.history) - 5} more messages[/dim]")

    console.print()

