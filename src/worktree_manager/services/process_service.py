"""Process management service for starting and killing processes."""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Union

import psutil


class ProcessService:
    """Service for managing processes and docker containers."""

    def start_process(
        self,
        command: str,
        cwd: str,
        env: Optional[Dict[str, str]] = None,
        shell: bool = False,
        log_file: Optional[str] = None,
    ) -> int:
        """Start a process in the background.

        Args:
            command: Command to execute (string or list).
            cwd: Working directory for the process.
            env: Environment variables (merged with current env).
            shell: If True, execute through shell.
            log_file: Optional path to log file for stdout/stderr.

        Returns:
            PID of the started process.
        """
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        # Determine if we're on Windows
        is_windows = sys.platform == 'win32'

        # Prepare command
        if isinstance(command, str):
            if is_windows:
                # On Windows, use cmd /c for proper shell execution
                cmd = ['cmd', '/c', command]
            else:
                # On Unix, use shell=True for proper execution
                cmd = command
                shell = True
        else:
            cmd = command

        # Setup output (log file or devnull)
        if log_file:
            # Ensure log directory exists
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            stdout_file = open(log_file, 'a')
            stderr_file = subprocess.STDOUT  # Redirect stderr to stdout
        else:
            stdout_file = subprocess.DEVNULL
            stderr_file = subprocess.DEVNULL

        # Start process
        kwargs = {
            'cwd': cwd,
            'env': full_env,
            'stdout': stdout_file,
            'stderr': stderr_file,
        }

        if is_windows:
            # On Windows, don't use start_new_session - it causes issues
            # Use CREATE_NEW_PROCESS_GROUP for proper detachment
            kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs['start_new_session'] = True

        if shell:
            kwargs['shell'] = True

        process = subprocess.Popen(cmd, **kwargs)

        return process.pid

    def kill_process(self, pid: int) -> bool:
        """Kill a process by PID.

        Args:
            pid: Process ID to kill.

        Returns:
            True if process was killed, False otherwise.
        """
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
            return True
        except psutil.NoSuchProcess:
            return True  # Already dead
        except psutil.AccessDenied:
            # On Windows, try taskkill as fallback
            if sys.platform == 'win32':
                try:
                    subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                                   capture_output=True, timeout=5)
                    return True
                except Exception:
                    pass
            return False

    def kill_processes_on_ports(self, ports: List[int]) -> List[int]:
        """Kill all processes using specific ports.

        Args:
            ports: List of port numbers.

        Returns:
            List of PIDs that were killed.
        """
        killed = []
        for port in ports:
            for conn in psutil.net_connections():
                try:
                    if conn.laddr.port == port:
                        pid = conn.pid
                        if pid and pid != os.getpid():
                            if self.kill_process(pid):
                                killed.append(pid)
                except (ValueError, OSError, psutil.NoSuchProcess):
                    continue
        return killed

    def is_process_running(self, pid: int) -> bool:
        """Check if a process is still running.

        Args:
            pid: Process ID to check.

        Returns:
            True if running, False otherwise.
        """
        try:
            proc = psutil.Process(pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False

    def start_docker_compose(self, compose_file: str) -> bool:
        """Start docker compose services.

        Args:
            compose_file: Path to docker-compose.yml file.

        Returns:
            True if successful, False otherwise.
        """
        try:
            subprocess.run(
                ["docker", "compose", "-f", compose_file, "up", "-d"],
                check=True,
                capture_output=True,
                cwd=Path(compose_file).parent,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def stop_docker_compose(self, compose_file: str) -> bool:
        """Stop docker compose services.

        Args:
            compose_file: Path to docker-compose.yml file.

        Returns:
            True if successful, False otherwise.
        """
        try:
            subprocess.run(
                ["docker", "compose", "-f", compose_file, "down"],
                check=True,
                capture_output=True,
                cwd=Path(compose_file).parent,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def get_container_names(self, compose_file: str) -> List[str]:
        """Get list of container names from a compose file.

        Args:
            compose_file: Path to docker-compose.yml file.

        Returns:
            List of container names.
        """
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", compose_file, "ps", "--format", "json"],
                check=True,
                capture_output=True,
                text=True,
                cwd=Path(compose_file).parent,
            )
            # Parse container names from output
            containers = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    import json
                    try:
                        data = json.loads(line)
                        if "Name" in data:
                            containers.append(data["Name"])
                    except json.JSONDecodeError:
                        continue
            return containers
        except (subprocess.CalledProcessError, FileNotFoundError):
            return []

    def is_port_listening(self, port: int, host: str = "localhost") -> bool:
        """Check if a port is actively listening.

        Args:
            port: Port number to check.
            host: Host to check against.

        Returns:
            True if port is listening, False otherwise.
        """
        import socket
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except (socket.timeout, socket.error, OSError):
            return False