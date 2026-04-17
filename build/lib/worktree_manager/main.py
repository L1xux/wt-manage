"""Worktree Manager CLI - Main entry point.

A CLI tool for managing Git worktrees with automatic service detection
and AI-powered startup using MiniMax m2.7 API.

Usage:
    python -m worktree_manager <command> [options]

Commands:
    wt-create [name]    Create a new worktree with service detection
    wt-remove [name]    Remove a worktree and stop its services
    wt-list             List all worktrees and their status
"""

import argparse
import sys
from pathlib import Path

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent))

from .commands.create import main as create_main, create_worktree
from .commands.remove import main as remove_main, remove_worktree, get_worktree_name
from .commands.list import main as list_main, list_worktrees
from .utils.logger import error, info, section


def create_command(args=None):
    """Entry point for wt-create command."""
    create_main(args)


def remove_command(args=None):
    """Entry point for wt-remove command."""
    remove_main(args)


def list_command(args=None):
    """Entry point for wt-list command."""
    list_main(args)


def main(args=None):
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="worktree-manager",
        description="Git worktree management CLI with AI-powered service detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  wt-create my-feature    Create a worktree named 'my-feature'
  wt-list                 List all worktrees
  wt-remove my-feature    Remove the 'my-feature' worktree

Environment:
  MINIMAX_API_KEY    API key for MiniMax m2.7 (for AI service detection)
  MINIMAX_BASE_URL   API base URL (default: https://api.minimax.chat/v1)
  MODEL              Model name (default: mimicat-m2.7)
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # wt-create subcommand
    create_parser = subparsers.add_parser(
        "wt-create",
        help="Create a new git worktree with AI-powered service detection",
    )
    create_parser.add_argument(
        "name",
        nargs="?",
        help="Name of the worktree to create",
    )
    create_parser.set_defaults(func=create_command)

    # wt-remove subcommand
    remove_parser = subparsers.add_parser(
        "wt-remove",
        help="Remove a worktree and stop its services",
    )
    remove_parser.add_argument(
        "name",
        nargs="?",
        help="Name of the worktree to remove",
    )
    remove_parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Skip confirmation prompt",
    )
    remove_parser.set_defaults(func=remove_command)

    # wt-list subcommand
    list_parser = subparsers.add_parser(
        "wt-list",
        help="List all worktrees and their services",
    )
    list_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show more details",
    )
    list_parser.set_defaults(func=list_command)

    # Parse arguments
    parsed = parser.parse_args(args)

    if not parsed.command:
        parser.print_help()
        print()
        info("Run 'wt-create', 'wt-remove', or 'wt-list' to get started")
        return 0

    # Execute command
    try:
        return parsed.func(parsed) or 0
    except KeyboardInterrupt:
        info("\nOperation cancelled by user")
        return 130
    except Exception as e:
        error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())


# Make module executable
if __name__ == "__main__":
    sys.exit(main())