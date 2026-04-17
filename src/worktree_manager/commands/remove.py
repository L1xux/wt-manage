"""wt-remove command implementation."""

import sys
from pathlib import Path

from ..config import ConfigManager, WorktreeConfig
from ..services.git_service import GitService
from ..services.process_service import ProcessService
from ..utils.logger import error, info, success, warning


def get_worktree_path(name: str, config: ConfigManager) -> str:
    """Get worktree path by name, or prompt user to select.

    Args:
        name: Worktree name provided as argument.
        config: ConfigManager instance.

    Returns:
        Path to the worktree.

    Raises:
        SystemExit: If no worktrees exist or invalid selection.
    """
    # Get base path where we scan for worktrees (parent of worktree-manager)
    base_path = Path(__file__).parent.parent.parent.parent  # worktree-manager dir
    scan_dir = base_path.parent  # parent of worktree-manager

    if name:
        # First try: find by config file (key matches worktree name)
        worktrees = config.discover_worktrees()
        wt_info = worktrees.get(name)
        if wt_info:
            return wt_info.get("path", "")

        # Second try: directory exists (directory name = worktree name)
        worktree_path = scan_dir / name
        if worktree_path.exists() and worktree_path.is_dir():
            info(f"Found worktree directory: {worktree_path}")
            return str(worktree_path)

        error(f"Worktree '{name}' not found")
        sys.exit(1)

    worktrees = config.discover_worktrees()

    if not worktrees:
        # Check if there are any directories that might be worktrees without config
        info("No worktrees with config files found.")
        info(f"Scanning directory: {scan_dir}")
        print()

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
            selected_name = names[idx]
            return worktrees[selected_name].get("path", "")
    except ValueError:
        pass

    # Try to match by name
    if selection in worktrees:
        return worktrees[selection].get("path", "")

    error(f"Invalid selection: {selection}")
    sys.exit(1)


def kill_worktree_services(worktree_config: dict) -> None:
    """Kill all services associated with a worktree based on config.

    Args:
        worktree_config: Worktree configuration dictionary.
    """
    services = worktree_config.get("services", {})
    process_service = ProcessService()

    for svc_type, svc_config in services.items():
        if svc_type == "docker":
            compose_file = svc_config.get("compose_file")
            if compose_file:
                warning(f"Stopping docker compose: {compose_file}")
                process_service.stop_docker_compose(compose_file)

        elif svc_type.startswith("server") or svc_type.startswith("client"):
            port = svc_config.get("port")
            pid = svc_config.get("pid")

            # First try killing by PID
            if pid and process_service.is_process_running(pid):
                info(f"Stopping {svc_type} (PID: {pid}, port: {port})")
                process_service.kill_process(pid)
            else:
                # Always try killing by port as primary method
                if port:
                    info(f"Stopping {svc_type} by port {port}")
                    killed = process_service.kill_processes_on_ports([port])
                    if killed:
                        info(f"  Stopped processes on port {port}")
                    else:
                        info(f"  No process on port {port}")


def remove_worktree(name: str, args) -> None:
    """Remove a worktree and its services.

    Args:
        name: Worktree name.
        args: Parsed command line arguments.
    """
    config = ConfigManager()

    # Get worktree path
    worktree_path = get_worktree_path(name, config)

    if not worktree_path or not Path(worktree_path).exists():
        error(f"Worktree '{name}' not found or path doesn't exist")
        sys.exit(1)

    # Load config from worktree directory
    wt_config = WorktreeConfig(worktree_path)
    worktree_config = wt_config.load()

    # Confirm removal
    if not args.force:
        info(f"About to remove worktree '{name}'")
        info(f"  Path: {worktree_path}")

        services = worktree_config.get("services", {})
        if services:
            info("  Services running:")
            for svc_type, svc_config in services.items():
                pid = svc_config.get("pid", "N/A")
                start_cmd = svc_config.get("start_command", "N/A")
                info(f"    - {svc_type}: pid={pid}")

        print()
        confirm = input("Remove this worktree? [y/N]: ").strip().lower()

        if confirm != 'y':
            info("Cancelled")
            return

    # Kill services
    info("Stopping services...")
    kill_worktree_services(worktree_config)

    # Remove worktree from git
    info(f"Removing git worktree: {worktree_path}")

    git_service = GitService()
    removed = git_service.remove_worktree(worktree_path, force=True)
    if not removed:
        warning("Git worktree removal returned False (may already be removed)")

    # Clean up the directory (git worktree remove doesn't always delete contents)
    import shutil
    import time
    max_retries = 5
    directory_removed = False

    for attempt in range(max_retries):
        try:
            shutil.rmtree(worktree_path)
            info(f"Directory cleaned up: {worktree_path}")
            directory_removed = True
            break
        except Exception as e:
            if attempt < max_retries - 1:
                warning(f"Directory removal failed (attempt {attempt + 1}/{max_retries}), retrying...")
                time.sleep(2)

                # Force kill all ports with taskkill
                process_service = ProcessService()
                ports = []
                for svc_config in worktree_config.get("services", {}).values():
                    port = svc_config.get("port")
                    if port:
                        ports.append(port)

                if ports:
                    warning(f"Force killing processes on ports: {ports}")
                    for port in ports:
                        process_service.kill_processes_on_ports([port])
                        # Also use taskkill directly
                        import subprocess
                        try:
                            subprocess.run(['taskkill', '/F', '/FI', f'PORT eq {port}'],
                                           capture_output=True, timeout=5)
                        except:
                            pass
            else:
                warning(f"Could not remove directory: {e}")

    print()
    if directory_removed:
        success(f"Worktree '{name}' removed successfully")
    else:
        warning(f"Worktree directory could not be fully removed")
        warning("You may need to manually clean up or kill remaining processes")


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

    if not parsed_args.name:
        # Show selection prompt
        config = ConfigManager()
        worktrees = config.discover_worktrees()
        if not worktrees:
            error("No worktrees found")
            sys.exit(1)

        parsed_args.name = get_worktree_path(None, config)

    remove_worktree(parsed_args.name, parsed_args)


if __name__ == "__main__":
    main()