"""
Entry point for running wukong as a module.

Usage:
    python -m wukong
    wukong  (after installation)
"""

import sys


def main() -> int:
    """Main entry point for the CLI application."""
    from wukong.cli import app

    try:
        app()
        return 0
    except KeyboardInterrupt:
        # User pressed Ctrl+C
        return 130
    except Exception as e:
        # Unexpected error - print and exit
        from rich.console import Console

        console = Console(stderr=True)
        console.print(f"[red]Error:[/red] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

