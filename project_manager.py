from __future__ import annotations
from pathlib import Path

PROJECTS_ROOT = Path.cwd() / "projects"

def ensure_project_structure(project_file: str | Path) -> Path:
    """
    Ensure the directory structure for a project file exists and return the normalized path.
    Creates common asset folders (assets, sprites, backgrounds, menus, audio, builds, scenes).
    """
    path = Path(project_file).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    for sub in ("assets", "sprites", "backgrounds", "menus", "audio", "scenes", "builds"):
        (path.parent / sub).mkdir(parents=True, exist_ok=True)
    return path

def default_projects_root() -> Path:
    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
    return PROJECTS_ROOT

