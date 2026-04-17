"""Config manager for worktree-manager."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class ConfigManager:
    """Manages worktree configuration stored in JSON."""

    DEFAULT_CONFIG_DIR = "~/.worktree_manager"
    DEFAULT_CONFIG_FILE = "config.json"

    def __init__(self, config_path: Optional[str] = None):
        """Initialize config manager.

        Args:
            config_path: Path to config file. Defaults to ~/.worktree_manager/config.json
        """
        if config_path:
            self.config_path = Path(config_path).expanduser()
        else:
            self.config_dir = Path(self.DEFAULT_CONFIG_DIR).expanduser()
            self.config_path = self.config_dir / self.DEFAULT_CONFIG_FILE

        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """Create config directory if it doesn't exist."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            self._save_default_config()

    def _load_raw(self) -> Dict[str, Any]:
        """Load raw config data."""
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return self._default_config()

    def _save_raw(self, data: Dict[str, Any]) -> bool:
        """Save raw config data."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"Failed to save config: {e}")
            return False

    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration structure."""
        return {
            "worktrees": {},
            "settings": {
                "base_server_port": 8000,
                "base_client_port": 5173,
                "port_increment": 1,
            },
        }

    def _save_default_config(self) -> None:
        """Save default configuration."""
        self._save_raw(self._default_config())

    def load(self) -> Dict[str, Any]:
        """Load configuration.

        Returns:
            Configuration dictionary.
        """
        return self._load_raw()

    def save(self, data: Dict[str, Any]) -> bool:
        """Save configuration.

        Args:
            data: Configuration data to save.

        Returns:
            True if successful, False otherwise.
        """
        return self._save_raw(data)

    def add_worktree(
        self,
        name: str,
        path: str,
        services: Dict[str, Any],
        created_at: Optional[str] = None,
    ) -> bool:
        """Add a new worktree entry.

        Args:
            name: Worktree name.
            path: Worktree path.
            services: Service configuration.
            created_at: Creation timestamp.

        Returns:
            True if successful, False otherwise.
        """
        data = self._load_raw()

        if created_at is None:
            from datetime import datetime
            created_at = datetime.now().isoformat()

        data["worktrees"][name] = {
            "path": path,
            "created_at": created_at,
            "services": services,
        }

        return self._save_raw(data)

    def remove_worktree(self, name: str) -> bool:
        """Remove a worktree entry.

        Args:
            name: Worktree name.

        Returns:
            True if removed, False if not found.
        """
        data = self._load_raw()

        if name in data["worktrees"]:
            del data["worktrees"][name]
            return self._save_raw(data)

        return False

    def get_worktree(self, name: str) -> Optional[Dict[str, Any]]:
        """Get worktree configuration.

        Args:
            name: Worktree name.

        Returns:
            Worktree configuration or None if not found.
        """
        data = self._load_raw()
        return data["worktrees"].get(name)

    def get_all_worktrees(self) -> Dict[str, Dict[str, Any]]:
        """Get all worktrees.

        Returns:
            Dictionary of all worktree configurations.
        """
        data = self._load_raw()
        return data.get("worktrees", {})

    def update_worktree_status(self, name: str, services: Dict[str, Any]) -> bool:
        """Update worktree service status.

        Args:
            name: Worktree name.
            services: Updated service configuration.

        Returns:
            True if successful, False otherwise.
        """
        data = self._load_raw()

        if name not in data["worktrees"]:
            return False

        data["worktrees"][name]["services"] = services
        return self._save_raw(data)

    def get_settings(self) -> Dict[str, Any]:
        """Get settings configuration.

        Returns:
            Settings dictionary.
        """
        data = self._load_raw()
        return data.get("settings", {
            "base_server_port": 8000,
            "base_client_port": 5173,
            "port_increment": 1,
        })

    def update_settings(self, settings: Dict[str, Any]) -> bool:
        """Update settings configuration.

        Args:
            settings: Settings to update.

        Returns:
            True if successful, False otherwise.
        """
        data = self._load_raw()
        data["settings"] = {**data.get("settings", {}), **settings}
        return self._save_raw(data)

    def worktree_exists(self, name: str) -> bool:
        """Check if worktree exists in config.

        Args:
            name: Worktree name.

        Returns:
            True if exists, False otherwise.
        """
        data = self._load_raw()
        return name in data["worktrees"]

    def get_next_port(self, service_type: str) -> int:
        """Get next available port for a service type.

        Args:
            service_type: 'server' or 'client'.

        Returns:
            Next available port number.
        """
        settings = self.get_settings()

        if service_type == "server":
            base = settings.get("base_server_port", 8000)
        else:
            base = settings.get("base_client_port", 5173)

        # Check existing ports in use
        used_ports = set()
        data = self._load_raw()
        for wt in data.get("worktrees", {}).values():
            for svc in wt.get("services", {}).values():
                if "port" in svc:
                    used_ports.add(svc["port"])

        # Find next available
        port = base
        while port in used_ports:
            port += settings.get("port_increment", 1)

        return port