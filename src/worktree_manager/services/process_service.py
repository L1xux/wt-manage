"""Process management service for starting and killing processes."""

import os
import signal
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import psutil


class ProcessService:
    """Service for managing processes and docker containers."""

    def start_process(
        self,
        command: str,
        cwd: str,
        env: Optional[Dict[str, str]] = None,
        shell: bool = True,
    ) -> int:
        """Start a process in the background.

        Args:
            command: Command to execute.
            cwd: Working directory for the process.
            env: Environment variables (merged with current env).
            shell: If True, execute through shell.

        Returns:
            PID of the started process.

        Raises:
            subprocess.CalledProcessError: If process fails to start.
        """
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=full_env,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

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
            return True
        except psutil.NoSuchProcess:
            return True  # Already dead
        except psutil.AccessDenied:
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