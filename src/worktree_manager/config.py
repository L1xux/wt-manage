"""Config manager for worktree-manager.

Each worktree stores its own config in a .worktree directory inside the worktree.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional


class WorktreeConfig:
    """Manages configuration for a single worktree, stored inside the worktree directory."""

    CONFIG_DIR = ".worktree"
    CONFIG_FILE = "config.json"

    def __init__(self, worktree_path: str):
        """Initialize config for a specific worktree.

        Args:
            worktree_path: Path to the worktree directory.
        """
        self.worktree_path = Path(worktree_path).resolve()
        self.config_dir = self.worktree_path / self.CONFIG_DIR
        self.config_path = self.config_dir / self.CONFIG_FILE

    def exists(self) -> bool:
        """Check if config file exists for this worktree."""
        return self.config_path.exists()

    def load(self) -> Dict[str, Any]:
        """Load config data.

        Returns:
            Configuration dictionary or empty dict if not found.
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def save(self, data: Dict[str, Any]) -> bool:
        """Save config data.

        Args:
            data: Configuration data to save.

        Returns:
            True if successful, False otherwise.
        """
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"Failed to save config: {e}")
            return False

    def delete(self) -> bool:
        """Delete the config directory for this worktree."""
        try:
            if self.config_dir.exists():
                import shutil
                shutil.rmtree(self.config_dir)
            return True
        except Exception as e:
            print(f"Failed to delete config: {e}")
            return False


class ConfigManager:
    """Manages worktree configurations by discovering them from filesystem.

    Instead of a central config file, worktrees are discovered by scanning
    parent directories for worktrees with their own config files.
    """

    def __init__(self, base_path: Optional[str] = None):
        """Initialize config manager.

        Args:
            base_path: Base directory to scan for worktrees. Defaults to parent of worktree-manager.
        """
        self.base_path = Path(base_path).resolve() if base_path else Path(__file__).parent.parent.parent.parent

    def discover_worktrees(self) -> Dict[str, Dict[str, Any]]:
        """Discover all worktrees by scanning parent directories.

        Returns:
            Dictionary mapping worktree name to its config data.
        """
        worktrees = {}
        parent = self.base_path.parent  # Scan siblings of base_path

        if not parent.exists():
            return worktrees

        for item in parent.iterdir():
            if item.is_dir() and item.name != self.base_path.name:
                # Check if this directory has a .worktree config
                wt_config = WorktreeConfig(str(item))
                if wt_config.exists():
                    config_data = wt_config.load()
                    if "name" in config_data:
                        worktrees[config_data["name"]] = {
                            "path": str(item),
                            **config_data
                        }

        return worktrees

    def get_worktree_config(self, worktree_path: str) -> WorktreeConfig:
        """Get a WorktreeConfig instance for a specific path."""
        return WorktreeConfig(worktree_path)

    def get_worktree(self, name: str, worktree_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get worktree configuration.

        Args:
            name: Worktree name.
            worktree_path: Optional path to worktree (faster lookup).

        Returns:
            Worktree configuration or None if not found.
        """
        if worktree_path:
            config = WorktreeConfig(worktree_path)
            data = config.load()
            if data.get("name") == name:
                return {"path": worktree_path, **data}
        else:
            # Scan to find
            worktrees = self.discover_worktrees()
            return worktrees.get(name)
        return None

    def worktree_exists(self, name: str, worktree_path: Optional[str] = None) -> bool:
        """Check if worktree exists.

        Args:
            name: Worktree name.
            worktree_path: Optional path to check directly.

        Returns:
            True if exists, False otherwise.
        """
        if worktree_path:
            config = WorktreeConfig(worktree_path)
            return config.exists() and config.load().get("name") == name
        return name in self.discover_worktrees()