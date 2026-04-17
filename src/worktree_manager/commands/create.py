"""wt-create command implementation."""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv

from ..config import ConfigManager, WorktreeConfig
from ..services.ai_service import AIService
from ..services.git_service import GitService
from ..services.process_service import ProcessService
from ..utils.logger import error, header, info, success, warning


def get_env_path() -> Optional[str]:
    """Find .env file in worktree_manager package directory."""
    pkg_dir = Path(__file__).parent.parent
    env_path = pkg_dir / ".env"
    if env_path.exists():
        return str(env_path)

    # Also check current directory and parent directories
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        env_path = parent / ".env"
        if env_path.exists():
            return str(env_path)

    return None


def get_worktree_name(args_name: Optional[str]) -> str:
    """Get worktree name from args or prompt user."""
    if args_name:
        return args_name

    # Prompt user for name
    info("Enter a name for the new worktree:")
    name = input("  > ").strip()

    if not name:
        error("Worktree name cannot be empty")
        sys.exit(1)

    return name


def verify_git_repo() -> str:
    """Verify current directory is a git repository.

    Returns:
        Path to git repository root.

    Raises:
        SystemExit: If not in a git repo.
    """
    git_service = GitService()
    repo_root = git_service.get_repo_root(".")

    if not repo_root:
        error("Current directory is not a git repository")
        sys.exit(1)

    return repo_root


def analyze_and_configure_services(
    worktree_path: str,
    ai_service: AIService,
    base_server_port: int = 8000,
    base_client_port: int = 5173,
) -> Tuple[Dict[str, any], List[str]]:
    """Analyze project and configure services.

    Returns:
        Tuple of (services_dict, services_info_list).
    """
    from ..services.port_service import PortService
    import time

    info("Analyzing project structure...")

    # Use AI to detect services
    analysis = ai_service.analyze_project(worktree_path)

    services = {}
    services_info = []
    server_count = 0
    client_count = 0
    port_service = PortService()
    next_server_port = base_server_port
    next_client_port = base_client_port

    # Setup log directory
    log_dir = Path(worktree_path) / ".worktree" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    def find_free_port(start_from: int) -> int:
        """Find next free port starting from start_from."""
        port = start_from
        while port_service.is_port_in_use(port):
            port += 1
        return port

    def wait_for_port(port: int, timeout: int = 10) -> bool:
        """Wait for port to start listening. Returns True if listening."""
        for _ in range(timeout):
            time.sleep(1)
            if port_service.is_port_listening(port):
                return True
        return False

    # Configure each detected service
    for svc in analysis.get("services", []):
        svc_type = svc.get("type")

        if svc_type == "docker":
            # Docker services - start containers
            compose_file = svc.get("compose_file")
            if compose_file:
                process_service = ProcessService()
                success(f"Starting docker compose: {compose_file}")
                process_service.start_docker_compose(compose_file)

                services["docker"] = {
                    "compose_file": compose_file,
                    "containers": process_service.get_container_names(compose_file),
                }
                services_info.append(f"  Docker: {compose_file}")

        elif svc_type == "server":
            server_count += 1
            svc_name = f"server-{server_count}" if server_count > 1 else "server"
            port = find_free_port(next_server_port)
            next_server_port = port + 1

            start_command = svc.get("start_command", "python run.py")
            working_dir = svc.get("working_directory", "server")

            abs_working_dir = str(Path(worktree_path) / working_dir)

            info(f"Starting server on port {port}...")
            info(f"  Command: {start_command}")
            info(f"  Working directory: {abs_working_dir}")

            # Create log file for this service
            log_file = str(log_dir / f"{svc_name}.log")

            process_service = ProcessService()
            pid = process_service.start_process(
                command=start_command,
                cwd=abs_working_dir,
                log_file=log_file,
            )

            # Wait for port to be listening
            info(f"  Waiting for server to start...")
            if wait_for_port(port):
                success(f"  Server running at http://localhost:{port}")
                status = "running"
            else:
                warning(f"  Server started but port {port} not responding yet")
                status = "started"

            services[svc_name] = {
                "port": port,
                "pid": pid,
                "start_command": start_command,
                "working_dir": abs_working_dir,
                "status": status,
                "log_file": log_file,
            }
            services_info.append(f"  Server: http://localhost:{port}")

        elif svc_type == "client":
            client_count += 1
            svc_name = f"client-{client_count}" if client_count > 1 else "client"
            port = find_free_port(next_client_port)
            next_client_port = port + 1

            start_command = svc.get("start_command", "npm run dev")
            working_dir = svc.get("working_directory", "client")

            abs_working_dir = str(Path(worktree_path) / working_dir)

            info(f"Starting client on port {port}...")
            info(f"  Command: {start_command}")
            info(f"  Working directory: {abs_working_dir}")

            # Create log file for this service
            log_file = str(log_dir / f"{svc_name}.log")

            process_service = ProcessService()
            pid = process_service.start_process(
                command=start_command,
                cwd=abs_working_dir,
                log_file=log_file,
            )

            # Wait for port to be listening
            info(f"  Waiting for client to start...")
            if wait_for_port(port):
                success(f"  Client running at http://localhost:{port}")
                status = "running"
            else:
                warning(f"  Client started but port {port} not responding yet")
                status = "started"

            services[svc_name] = {
                "port": port,
                "pid": pid,
                "start_command": start_command,
                "working_dir": abs_working_dir,
                "status": status,
                "log_file": log_file,
            }
            services_info.append(f"  Client: http://localhost:{port}")

    return services, services_info


def create_worktree(name: str, args) -> None:
    """Create a new worktree with services.

    Args:
        name: Worktree name.
        args: Parsed command line arguments.
    """
    # Load environment variables
    env_path = get_env_path()
    if env_path:
        load_dotenv(env_path)
        info(f"Loaded environment from: {env_path}")
    else:
        warning("No .env file found, AI features may not work")

    # Verify git repo
    repo_root = verify_git_repo()
    info(f"Git repository: {repo_root}")

    # Initialize services
    git_service = GitService()
    ai_service = AIService()
    config = ConfigManager()

    # Check if worktree directory already exists with a config
    worktree_path = Path.cwd().parent / name
    if worktree_path.exists():
        wt_config = WorktreeConfig(str(worktree_path))
        if wt_config.exists():
            error(f"Worktree '{name}' already exists")
            info(f"Path: {worktree_path}")
            info("Use 'wt-remove' to remove it first, or choose a different name")
            sys.exit(1)
        else:
            error(f"Worktree directory already exists: {worktree_path}")
            info("A previous worktree may have been partially cleaned up.")
            confirm = input("Remove existing directory and create new worktree? [y/N]: ").strip().lower()
            if confirm != 'y':
                info("Cancelled")
                sys.exit(0)

            # Remove the existing directory
            import shutil
            try:
                shutil.rmtree(worktree_path)
                info(f"Removed existing directory: {worktree_path}")
            except Exception as e:
                error(f"Failed to remove directory: {e}")
                sys.exit(1)

    # Create worktree
    info(f"Creating worktree '{name}'...")

    try:
        worktree_path = git_service.create_worktree(name, ".")
        success(f"Worktree created at: {worktree_path}")
    except ValueError as e:
        error(str(e))
        sys.exit(1)
    except Exception as e:
        error(f"Failed to create worktree: {e}")
        sys.exit(1)

    # Analyze and configure services
    services, services_info = analyze_and_configure_services(
        worktree_path=worktree_path,
        ai_service=ai_service,
    )

    # Save configuration to worktree's .worktree/config.json
    wt_config = WorktreeConfig(str(worktree_path))
    config_data = {
        "name": name,
        "created_at": datetime.now().isoformat(),
        "services": services,
    }
    wt_config.save(config_data)
    success("Configuration saved")

    # Print summary
    print()
    success(f"Worktree '{name}' created successfully!")
    print()
    info("Services started:")
    for svc_info in services_info:
        print(svc_info)

    if not services:
        warning("No services detected or started")
        info("You may need to manually start services in the worktree")

    print()
    info(f"Worktree location: {worktree_path}")
    info(f"Logs saved to: {worktree_path}/.worktree/logs/")
    info(f"To remove: wt-remove {name}")

    # Show last few lines of logs for each service
    print()
    header("Live Log Output (last 20 lines each):")
    print("-" * 60)
    for svc_name, svc_config in services.items():
        log_file = svc_config.get("log_file")
        if log_file and Path(log_file).exists():
            info(f"{svc_name}:")
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    for line in lines[-20:]:
                        print(f"  {line.rstrip()}")
            except Exception:
                print("  (no output yet)")
            print()

    print("=" * 60)
    info("To watch logs continuously, run: wt-logs " + name)


def main(args=None):
    """Entry point for wt-create command."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Create a new git worktree with AI-powered service detection"
    )
    parser.add_argument(
        "name",
        nargs="?",
        help="Name of the worktree to create",
    )

    parsed_args = parser.parse_args(args)
    name = get_worktree_name(parsed_args.name)

    create_worktree(name, parsed_args)


if __name__ == "__main__":
    main()