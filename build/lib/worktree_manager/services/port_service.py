"""Port management service using psutil."""

import socket
from typing import List, Optional

import psutil


class PortService:
    """Service for finding and managing ports."""

    def is_port_in_use(self, port: int) -> bool:
        """Check if a port is currently in use.

        Args:
            port: Port number to check.

        Returns:
            True if port is in use, False otherwise.
        """
        for conn in psutil.net_connections():
            try:
                if conn.laddr.port == port:
                    return True
            except (ValueError, OSError):
                continue
        return False

    def find_unused_port(self, start_from: int = 8000, max_attempts: int = 100) -> int:
        """Find an unused port starting from the given port.

        Args:
            start_from: Starting port number.
            max_attempts: Maximum number of ports to try.

        Returns:
            An unused port number.

        Raises:
            RuntimeError: If no unused port found after max_attempts.
        """
        for port in range(start_from, start_from + max_attempts):
            if not self.is_port_in_use(port):
                return port

        raise RuntimeError(
            f"Could not find unused port after trying {max_attempts} ports"
        )

    def get_process_using_port(self, port: int) -> Optional[int]:
        """Get the PID of the process using a specific port.

        Args:
            port: Port number to check.

        Returns:
            PID of process using the port, or None if not found.
        """
        for conn in psutil.net_connections():
            try:
                if conn.laddr.port == port and conn.status == 'LISTEN':
                    return conn.pid
            except (ValueError, OSError, psutil.NoSuchProcess):
                continue
        return None

    def get_processes_on_ports(self, ports: List[int]) -> List[int]:
        """Get PIDs of processes using specific ports.

        Args:
            ports: List of port numbers to check.

        Returns:
            List of PIDs (may contain duplicates if multiple ports share a process).
        """
        pids = []
        for port in ports:
            pid = self.get_process_using_port(port)
            if pid:
                pids.append(pid)
        return pids

    def is_port_listening(self, port: int, host: str = "localhost") -> bool:
        """Check if a port is actively listening.

        Args:
            port: Port number to check.
            host: Host to check against.

        Returns:
            True if port is listening, False otherwise.
        """
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except (socket.timeout, socket.error, OSError):
            return False