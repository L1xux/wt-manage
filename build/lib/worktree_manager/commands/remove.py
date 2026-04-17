"""wt-remove command implementation."""

import sys
from pathlib import Path

from ..config import ConfigManager
from ..services.git_service import GitService
from ..services.process_service import ProcessService
from ..utils.logger import error, info, success, warning


def get_worktree_name(args_name: str, config: ConfigManager) -> str:
    """Get worktree name from args or prompt user to select.

    Args:
        args_name: Name provided as argument.
        config: ConfigManager instance.

    Returns:
        Selected worktree name.

    Raises:
        SystemExit: If no worktrees exist or invalid selection.
    """
    if args_name:
        return args_name

    worktrees = config.get_all_worktrees()

    if not worktrees:
        error("No worktrees found in configuration")
        sys.exit(1)

    # Show list and prompt for selection
    info("Select a worktree to remove:")
    print()

    names = list(worktrees.keys())
    for i, name in enumerate(names, 1):
        wt = worktrees[name]
        path = wt.get("path", "unknown")
        services = wt.get("services", {})
        service_count = len(services)

        print(f"  {i}. {name}")
        print(f"     Path: {path}")
        print(f"     Services: {service_count}")
        print()

    print("Enter number or name (or 'q' to cancel):")
    selection = input("  > ").strip()

    if selection.lower() == 'q':
        info("Cancelled")
        sys.exit(0)

    # Try to parse as number
    try:
        idx = int(selection) - 1
        if 0 <= idx < len(names):
            return names[idx]
    except ValueError:
        pass

    # Try to match by name
    if selection in worktrees:
        return selection

    error(f"Invalid selection: {selection}")
    sys.exit(1)


def kill_worktree_services(worktree_config: dict) -> None:
    """Kill all services associated with a worktree.

    Args:
        worktree_config: Worktree configuration dictionary.
    """
    services = worktree_config.get("services", {})
    process_service = ProcessService()

    ports_to_kill = []
    pids_to_kill = []

    for svc_type, svc_config in services.items():
        if svc_type == "docker":
            compose_file = svc_config.get("compose_file")
            if compose_file:
                warning(f"Stopping docker compose: {compose_file}")
                process_service.stop_docker_compose(compose_file)

        elif svc_type == "server" or svc_type == "client":
            # Kill by PID
            pid = svc_config.get("pid")
            if pid and process_service.is_process_running(pid):
                info(f"Stopping {svc_type} (PID: {pid})")
                process_service.kill_process(pid)
                pids_to_kill.append(pid)

            # Also kill by port as fallback
            port = svc_config.get("port")
            if port:
                ports_to_kill.append(port)

    # Kill any remaining processes on ports
    if ports_to_kill:
        killed = process_service.kill_processes_on_ports(ports_to_kill)
        if killed:
            info(f"Stopped processes on ports: {ports_to_kill}")


def remove_worktree(name: str, args) -> None:
    """Remove a worktree and its services.

    Args:
        name: Worktree name.
        args: Parsed command line arguments.
    """
    config = ConfigManager()

    # Get worktree config
    worktree_config = config.get_worktree(name)

    if not worktree_config:
        error(f"Worktree '{name}' not found in configuration")
        sys.exit(1)

    path = worktree_config.get("path")

    # Confirm removal
    if not args.force:
        info(f"About to remove worktree '{name}'")
        info(f"  Path: {path}")

        services = worktree_config.get("services", {})
        if services:
            info("  Services running:")
            for svc_type, svc_config in services.items():
                port = svc_config.get("port", "N/A")
                pid = svc_config.get("pid", "N/A")
                info(f"    - {svc_type}: port={port}, pid={pid}")

        print()
        confirm = input("Remove this worktree? [y/N]: ").strip().lower()

        if confirm != 'y':
            info("Cancelled")
            return

    # Kill services
    info("Stopping services...")
    kill_worktree_services(worktree_config)

    # Remove worktree from git
    if path and Path(path).exists():
        info(f"Removing git worktree: {path}")

        git_service = GitService()
        try:
            git_service.remove_worktree(path, force=True)
            success("Git worktree removed")
        except Exception as e:
            warning(f"Failed to remove git worktree: {e}")
            warning("You may need to manually remove the directory")
    else:
        warning(f"Worktree path not found: {path}")

    # Remove from config
    config.remove_worktree(name)
    success(f"Configuration for '{name}' removed")

    print()
    success(f"Worktree '{name}' removed successfully")


def main(args=None):
    """Entry point for wt-remove command."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Remove a git worktree and stop its services"
    )
    parser.add_argument(
        "name",
        nargs="?",
        help="Name of the worktree to remove",
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Skip confirmation prompt",
    )

    parsed_args = parser.parse_args(args)

    config = ConfigManager()
    name = get_worktree_name(parsed_args.name, config)

    remove_worktree(name, parsed_args)


if __name__ == "__main__":
    main()