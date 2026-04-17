"""wt-list command implementation."""

import sys
from datetime import datetime

from ..config import ConfigManager, WorktreeConfig
from ..services.process_service import ProcessService
from ..utils.logger import dim, error, info, section, success, value


def format_date(iso_date: str) -> str:
    """Format ISO date string for display.

    Args:
        iso_date: ISO format date string.

    Returns:
        Formatted date string.
    """
    try:
        dt = datetime.fromisoformat(iso_date)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso_date


def check_service_status(svc_config: dict) -> tuple:
    """Check if a service is running.

    Args:
        svc_config: Service configuration dictionary.

    Returns:
        Tuple of (status_text, is_running).
    """
    process_service = ProcessService()
    pid = svc_config.get("pid")

    if pid and process_service.is_process_running(pid):
        return ("running", True)

    return ("stopped", False)


def list_worktrees(args) -> None:
    """List all worktrees and their services.

    Args:
        args: Parsed command line arguments.
    """
    config = ConfigManager()
    worktrees = config.discover_worktrees()

    if not worktrees:
        print()
        info("No worktrees found")
        print()
        info("Create one with: wt-create <name>")
        print()
        return

    section("Worktree Manager - Active Worktrees")

    for name, wt_config in worktrees.items():
        path = wt_config.get("path", "unknown")
        created_at = wt_config.get("created_at", "unknown")
        services = wt_config.get("services", {})

        print(f"\n{'=' * 60}")
        print(f"  Worktree: {name}")
        print(f"{'=' * 60}")

        value("Path", path)
        value("Created", format_date(created_at))

        if services:
            print()
            info("Services:")
            print("-" * 60)

            any_running = False
            for svc_type, svc_config in services.items():
                if svc_type == "docker":
                    compose_file = svc_config.get("compose_file", "")
                    containers = svc_config.get("containers", [])
                    status = "running" if containers else "stopped"
                    print(f"  docker    | {compose_file}")
                    print(f"             | containers: {', '.join(containers) if containers else 'none'}")
                else:
                    status, is_running = check_service_status(svc_config)
                    if is_running:
                        any_running = True
                    status_symbol = "+" if is_running else "-"
                    pid = svc_config.get("pid", "N/A")
                    start_cmd = svc_config.get("start_command", "N/A")
                    print(f"  {status_symbol} {svc_type:8} | pid:{pid:6}")
                    print(f"              | {start_cmd}")

            print("-" * 60)

            if any_running:
                success(f"  {name}: running")
            else:
                dim(f"  {name}: stopped")
        else:
            dim("  No services configured")

        print()

    # Summary
    total = len(worktrees)
    running = sum(
        1 for wt in worktrees.values()
        if any(
            check_service_status(svc)[1]
            for svc in wt.get("services", {}).values()
            if isinstance(svc, dict)
        )
    )

    print("-" * 60)
    dim(f"Total: {total} worktrees | Running: {running} | Stopped: {total - running}")


def main(args=None):
    """Entry point for wt-list command."""
    import argparse

    parser = argparse.ArgumentParser(
        description="List all managed worktrees and their services"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show more details",
    )

    parsed_args = parser.parse_args(args)
    list_worktrees(parsed_args)


if __name__ == "__main__":
    main()