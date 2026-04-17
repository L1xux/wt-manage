"""Git worktree operations service."""

import subprocess
from pathlib import Path
from typing import List, Optional


class GitService:
    """Service for Git worktree operations."""

    def is_git_repo(self, path: str) -> bool:
        """Check if the given path is a git repository.

        Args:
            path: Directory path to check.

        Returns:
            True if .git folder exists, False otherwise.
        """
        git_path = Path(path) / ".git"
        return git_path.exists()

    def get_repo_root(self, path: str) -> Optional[str]:
        """Get the root directory of the git repository.

        Args:
            path: Any path within the git repository.

        Returns:
            Root path as string, or None if not in a git repo.
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def create_worktree(self, name: str, base_path: str) -> str:
        """Create a new git worktree.

        Args:
            name: Name of the worktree (used for branch and directory).
            base_path: Base path where the worktree should be created.

        Returns:
            Absolute path to the created worktree.

        Raises:
            subprocess.CalledProcessError: If git command fails.
        """
        repo_root = self.get_repo_root(base_path)
        if not repo_root:
            raise ValueError(f"Not a git repository: {base_path}")

        worktree_path = Path(base_path).parent / name
        branch_name = f"feature/{name}"

        # Check if worktree already exists
        if worktree_path.exists():
            raise ValueError(f"Worktree path already exists: {worktree_path}")

        # Create worktree with new branch
        subprocess.run(
            ["git", "worktree", "add", "-b", branch_name, str(worktree_path)],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )

        return str(worktree_path.resolve())

    def remove_worktree(self, path: str, force: bool = False) -> bool:
        """Remove a git worktree.

        Args:
            path: Path to the worktree to remove.
            force: If True, use --force flag.

        Returns:
            True if removal succeeded, False otherwise.

        Raises:
            subprocess.CalledProcessError: If git command fails.
        """
        repo_root = self.get_repo_root(path)
        if not repo_root:
            return False

        worktree_path = Path(path).resolve()
        if not worktree_path.exists():
            return False

        cmd = ["git", "worktree", "remove", str(worktree_path)]
        if force:
            cmd.append("--force")

        result = subprocess.run(
            cmd, cwd=repo_root, capture_output=True, text=True
        )

        if result.returncode != 0:
            # Try pruning first, then remove again
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=repo_root,
                capture_output=True,
            )
            result = subprocess.run(
                cmd + ["--force"], cwd=repo_root, capture_output=True, text=True
            )

        return result.returncode == 0

    def list_worktrees(self) -> List[dict]:
        """List all worktrees in the repository.

        Returns:
            List of dicts with 'path', 'name', 'branch', 'head' keys.
        """
        repo_root = self.get_repo_root(".")
        if not repo_root:
            return []

        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )

        worktrees = []
        current = {}
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            if line.startswith("worktree "):
                current["path"] = line.split("worktree ", 1)[1]
            elif line.startswith("branch "):
                current["branch"] = line.split("branch ", 1)[1]
            elif line == "bare":
                current["is_bare"] = True
            elif line == "locked":
                current["is_locked"] = True
            elif line == "prunable":
                current["is_prunable"] = True
            elif not line.startswith("HEAD"):
                # End of current worktree entry
                if current and "path" in current:
                    current["name"] = Path(current["path"]).name
                    worktrees.append(current)
                    current = {}

        # Handle last entry
        if current and "path" in current:
            current["name"] = Path(current["path"]).name
            worktrees.append(current)

        return worktrees

    def get_current_branch(self, path: str = ".") -> Optional[str]:
        """Get the current branch of the repository.

        Args:
            path: Path within the repository.

        Returns:
            Branch name or None if detached HEAD.
        """
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=path,
                capture_output=True,
                text=True,
                check=True,
            )
            branch = result.stdout.strip()
            return branch if branch else None
        except subprocess.CalledProcessError:
            return None