"""wt-remove command implementation."""

import sys
from pathlib import Path

from ..config import ConfigManager, WorktreeConfig
from ..services.git_service import GitService
from ..services.process_service import ProcessService
from ..utils.logger import error, info, success, warning


def force_delete_directory(path: str) -> bool:
    """Force delete a directory on Windows using cmd.

    Args:
        path: Path to directory to delete.

    Returns:
        True if deleted, False otherwise.
    """
    if sys.platform == 'win32':
        import subprocess
        try:
            # Use cmd /c rmdir /s /q for force delete on Windows
            result = subprocess.run(
                ['cmd', '/c', 'rmdir', '/s', '/q', path],
                capture_output=True,
                timeout=30
            )
            return result.returncode == 0
        except Exception as e:
            warning(f"Force delete failed: {e}")
            return False
    else:
        import shutil
        try:
            shutil.rmtree(path)
            return True
        except Exception:
            return False


def remove_worktree(name: str, args) -> None:
    """Remove a worktree and its services.

    Args:
        name: Worktree name.
        args: Parsed command line arguments.
    """
    # Get base path where we scan for worktrees
    base_path = Path(__file__).parent.parent.parent.parent  # worktree-manager dir
    scan_dir = base_path.parent  # parent of worktree-manager

    # Find worktree path
    worktree_path = None

    # First try: find by config file
    config = ConfigManager()
    worktrees = config.discover_worktrees()
    if name in worktrees:
        worktree_path = worktrees[name].get("path", "")

    # Second try: directory exists (directory name = worktree name)
    if not worktree_path:
        candidate_path = scan_dir / name
        if candidate_path.exists() and candidate_path.is_dir():
            worktree_path = str(candidate_path)

    if not worktree_path or not Path(worktree_path).exists():
        error(f"Worktree '{name}' not found")
        sys.exit(1)

    # Load config from worktree directory
    wt_config = WorktreeConfig(worktree_path)
    worktree_config = wt_config.load()

    # Get ports from config
    ports = []
    services_info = []
    for svc_type, svc_config in worktree_config.get("services", {}).items():
        port = svc_config.get("port")
        if port:
            ports.append(port)
            services_info.append(f"{svc_type}: port {port}")

    # Confirm removal
    if not args.force:
        info(f"About to remove worktree '{name}'")
        info(f"  Path: {worktree_path}")
        if services_info:
            info("  Services:")
            for svc in services_info:
                info(f"    - {svc}")
        print()
        confirm = input("Remove this worktree? [y/N]: ").strip().lower()
        if confirm != 'y':
            info("Cancelled")
            return

    # Kill services by port
    info("Stopping services...")
    if ports:
        process_service = ProcessService()
        for port in ports:
            info(f"  Stopping port {port}...")
            killed = process_service.kill_processes_on_ports([port])
            if killed:
                info(f"    Stopped (killed {len(killed)} process(es))")
            else:
                info(f"    No process on port {port}")

    # Remove git worktree
    info(f"Removing git worktree: {worktree_path}")
    git_service = GitService()
    removed = git_service.remove_worktree(worktree_path, force=True)
    if not removed:
        warning("Git worktree removal returned False (may already be removed)")

    # Delete directory - try normal first, then force
    import shutil
    try:
        shutil.rmtree(worktree_path)
        info(f"Directory cleaned up: {worktree_path}")
    except Exception as e:
        warning(f"Normal deletion failed, trying force delete...")
        if force_delete_directory(worktree_path):
            info(f"Directory force deleted: {worktree_path}")
        else:
            warning(f"Could not remove directory: {e}")
            warning("You may need to manually close any programs that have this folder open")
            return

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

    if not parsed_args.name:
        error("Worktree name required")
        sys.exit(1)

    remove_worktree(parsed_args.name, parsed_args)


if __name__ == "__main__":
    main()