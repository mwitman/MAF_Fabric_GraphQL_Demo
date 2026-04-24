"""Launch DevUI with the GraphQL Agents Orchestrator.

Usage:
    python graphql_agents/run.py

Or use the DevUI CLI directly (if devui is on PATH):
    devui ./graphql_agents --port 8080
"""

import os
from pathlib import Path
import sys


def _venv_python(repo_root: Path) -> Path:
    if os.name == "nt":
        return repo_root / ".venv" / "Scripts" / "python.exe"
    return repo_root / ".venv" / "bin" / "python"


def _ensure_repo_venv_python() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    expected_python = _venv_python(repo_root).resolve()
    current_python = Path(sys.executable).resolve()

    if expected_python.exists() and current_python != expected_python:
        os.execv(str(expected_python), [str(expected_python), str(Path(__file__).resolve()), *sys.argv[1:]])

if __name__ == "__main__":
    _ensure_repo_venv_python()
    from agent_framework_devui._cli import main as devui_main

    graphql_agents_dir = Path(__file__).resolve().parent
    sys.argv = ["devui", str(graphql_agents_dir), "--port", "8080"]
    devui_main()
