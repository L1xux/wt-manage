"""wt-remove command implementation."""

import sys
from pathlib import Path

from ..config import ConfigManager, WorktreeConfig
from ..services.git_service import GitService
from ..services.process_service import ProcessService
from ..utils.logger import error, info, success, warning


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

    # Get ports from config, or scan common worktree ports
    ports = []
    services_info = []

    if worktree_config.get("services"):
        # Use config
        for svc_type, svc_config in worktree_config.get("services", {}).items():
            port = svc_config.get("port")
            if port:
                ports.append(port)
                services_info.append(f"{svc_type}: port {port}")
    else:
        # No config - scan for processes using common ports in this directory
        info("No config found, scanning for processes...")
        process_service = ProcessService()

        # Common ports for worktrees
        common_ports = [8000, 8001, 8002, 5173, 5174, 5175, 5000, 5001, 3000, 3001]

        for port in common_ports:
            if process_service.get_process_using_port(port):
                # Check if process cwd is in our worktree
                import psutil
                for conn in psutil.net_connections():
                    try:
                        if conn.laddr.port == port and conn.pid:
                            proc = psutil.Process(conn.pid)
                            cwd = proc.cwd() or ""
                            if worktree_path.lower() in cwd.lower():
                                ports.append(port)
                                services_info.append(f"port {port} (cwd matches)")
                                info(f"  Found process on port {port}: PID {conn.pid}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

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

    # Wait for processes to fully terminate
    import time
    time.sleep(2)

    # Remove git worktree
    info(f"Removing git worktree: {worktree_path}")
    git_service = GitService()
    removed = git_service.remove_worktree(worktree_path, force=True)
    if not removed:
        warning("Git worktree removal returned False (may already be removed)")

    # Try to kill any remaining processes in the worktree directory
    import psutil
    for proc in psutil.process_iter(['pid', 'cwd', 'name']):
        try:
            cwd = proc.info.get('cwd') or ""
            if worktree_path.lower() in cwd.lower():
                info(f"  Killing remaining process: {proc.info['name']} (PID: {proc.info['pid']})")
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    time.sleep(1)

    # Delete directory - Windows cmd approach
    import subprocess

    deleted = False
    if sys.platform == 'win32':
        # Use PowerShell Remove-Item with -Recurse -Force
        try:
            result = subprocess.run(
                ['powershell', '-Command', f'Remove-Item -Path "{worktree_path}" -Recurse -Force -ErrorAction Stop'],
                capture_output=True,
                timeout=30
            )
            if result.returncode == 0:
                deleted = True
        except Exception as e:
            pass

        # Also verify and retry with cmd if needed
        if not deleted:
            try:
                subprocess.run(
                    ['cmd', '/c', 'rd', '/s', '/q', worktree_path],
                    capture_output=True,
                    timeout=30
                )
                deleted = True
            except:
                pass

        # Check if directory still exists
        import os
        if os.path.exists(worktree_path):
            warning(f"Directory still exists: {worktree_path}")
            warning("Close any programs that have this folder open (VS Code, Explorer)")
            return

    else:
        import shutil
        try:
            shutil.rmtree(worktree_path)
            deleted = True
        except Exception as e:
            warning(f"Could not remove directory: {e}")
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