"""AI service for project structure analysis using MiniMax API."""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI

from ..utils.logger import warning


class AIService:
    """Service for AI-powered project analysis using MiniMax m2.7."""

    DEFAULT_BASE_URL = "https://api.minimax.chat/v1"
    DEFAULT_MODEL = "mimicat-m2.7"
    TIMEOUT = 30

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """Initialize AI service.

        Args:
            api_key: MiniMax API key. If None, reads from MINIMAX_API_KEY env.
            base_url: API base URL. Defaults to MiniMax endpoint.
            model: Model name. Defaults to mimicat-m2.7.
        """
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.base_url = base_url or os.environ.get(
            "MINIMAX_BASE_URL", self.DEFAULT_BASE_URL
        )
        self.model = model or os.environ.get("MODEL", self.DEFAULT_MODEL)
        self.client = None

        if self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )

    def analyze_project(self, worktree_path: str) -> Dict[str, Any]:
        """Analyze project structure and detect services.

        Args:
            worktree_path: Path to the worktree to analyze.

        Returns:
            Dict with services, docker_compose_files, and project_type.
            Returns fallback detection on API failure.
        """
        if not self.client:
            warning("No API key configured, using heuristic detection")
            return self._detect_services_heuristic(worktree_path)

        try:
            project_structure = self._scan_project_structure(worktree_path)

            prompt = f"""Analyze this project structure and return a JSON response describing the services that need to be started.

Project path: {worktree_path}

Project structure:
{project_structure}

Return ONLY valid JSON in this exact format, no markdown or explanation:
{{
  "services": [
    {{
      "type": "server" | "client" | "docker",
      "name": "descriptive name",
      "detection_paths": ["path/to/server"],
      "start_command": "command to start (e.g., 'python run.py', 'npm run dev')",
      "working_directory": "relative path from project root",
      "port_hints": ["default expected ports like 8000, 3000"]
    }}
  ],
  "docker_compose_files": ["path/to/docker-compose.yml if exists"],
  "project_type": "frontend-only | backend-only | fullstack"
}}"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a DevOps assistant that analyzes project structures."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=2000,
                timeout=self.TIMEOUT,
            )

            content = response.choices[0].message.content.strip()

            # Extract JSON from response (handle potential markdown code blocks)
            json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to find raw JSON
                json_match = re.search(r"\{[\s\S]*\}", content)
                if json_match:
                    content = json_match.group(0)

            return json.loads(content)

        except Exception as e:
            warning(f"AI analysis failed: {e}, using heuristic detection")
            return self._detect_services_heuristic(worktree_path)

    def _scan_project_structure(self, worktree_path: str) -> str:
        """Scan project structure for analysis.

        Args:
            worktree_path: Path to scan.

        Returns:
            String representation of project structure.
        """
        structure_lines = []
        root = Path(worktree_path)

        # Scan top-level directories and key files
        if root.exists():
            for item in sorted(root.iterdir()):
                if item.is_dir() and not item.name.startswith("."):
                    # List some files in subdirectories
                    sub_items = []
                    try:
                        for sub in list(item.iterdir())[:5]:
                            sub_items.append(f"  {sub.name}")
                    except PermissionError:
                        pass

                    if sub_items:
                        structure_lines.append(f"{item.name}/")
                        structure_lines.extend(sub_items)
                    else:
                        structure_lines.append(f"{item.name}/")
                elif item.is_file() and not item.name.startswith("."):
                    structure_lines.append(item.name)

        return "\n".join(structure_lines[:50])  # Limit output

    def _detect_services_heuristic(self, worktree_path: str) -> Dict[str, Any]:
        """Fallback heuristic detection when AI fails.

        Args:
            worktree_path: Path to analyze.

        Returns:
            Detected services configuration.
        """
        services = []
        docker_files = []
        project_type = "unknown"
        root = Path(worktree_path)

        # Check for server directory
        server_path = root / "server"
        if server_path.exists():
            if (server_path / "package.json").exists():
                services.append({
                    "type": "server",
                    "name": "Node.js Server",
                    "detection_paths": [str(server_path / "package.json")],
                    "start_command": "npm run dev",
                    "working_directory": "server",
                    "port_hints": [8000, 3000, 8080],
                })
                project_type = "fullstack" if (root / "client").exists() else "backend-only"
            elif (server_path / "requirements.txt").exists() or (server_path / "pyproject.toml").exists():
                services.append({
                    "type": "server",
                    "name": "Python Server",
                    "detection_paths": [str(server_path / "requirements.txt")],
                    "start_command": "python run.py",
                    "working_directory": "server",
                    "port_hints": [8000, 8080, 5000],
                })
                project_type = "fullstack" if (root / "client").exists() else "backend-only"
            elif (server_path / "go.mod").exists():
                services.append({
                    "type": "server",
                    "name": "Go Server",
                    "detection_paths": [str(server_path / "go.mod")],
                    "start_command": "go run .",
                    "working_directory": "server",
                    "port_hints": [8080, 3000],
                })
                project_type = "fullstack" if (root / "client").exists() else "backend-only"

        # Check for client directory
        client_path = root / "client"
        if client_path.exists():
            if (client_path / "package.json").exists():
                services.append({
                    "type": "client",
                    "name": "Node.js Client",
                    "detection_paths": [str(client_path / "package.json")],
                    "start_command": "npm run dev",
                    "working_directory": "client",
                    "port_hints": [5173, 3000, 8080],
                })
                if project_type == "unknown":
                    project_type = "frontend-only"

        # Check for alternative frontend location
        if not (root / "client").exists() and (root / "frontend").exists():
            if (root / "frontend" / "package.json").exists():
                services.append({
                    "type": "client",
                    "name": "Frontend",
                    "detection_paths": [str(root / "frontend" / "package.json")],
                    "start_command": "npm run dev",
                    "working_directory": "frontend",
                    "port_hints": [5173, 3000, 8080],
                })
                if project_type == "unknown":
                    project_type = "frontend-only"

        # Check for docker-compose files
        for docker_file in root.glob("docker-compose*.yml"):
            docker_files.append(str(docker_file))
            services.append({
                "type": "docker",
                "name": f"Docker ({docker_file.name})",
                "detection_paths": [str(docker_file)],
                "compose_file": str(docker_file),
            })

        # Check for docker-compose in subdirectories
        for subdir in ["docker", "infra"]:
            sub_path = root / subdir
            if sub_path.exists():
                for docker_file in sub_path.glob("docker-compose*.yml"):
                    docker_files.append(str(docker_file))
                    services.append({
                        "type": "docker",
                        "name": f"Docker ({docker_file.name})",
                        "detection_paths": [str(docker_file)],
                        "compose_file": str(docker_file),
                    })

        # Check for main package.json (monorepo style)
        main_package = root / "package.json"
        if main_package.exists():
            # Check for common patterns
            content = main_package.read_text() if main_package.exists() else ""
            if '"start"' in content or '"dev"' in content:
                # Likely a frontend or full monorepo
                if project_type == "unknown":
                    project_type = "frontend-only"

        return {
            "services": services,
            "docker_compose_files": docker_files,
            "project_type": project_type,
        }