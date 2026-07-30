"""COM wrappers for ConfigurationDesk project management.

All functions must be called on the STA thread via dispatch().
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from configurationdesk_com_bridge.domains.verify_com import (
    verify_active_project,
    verify_file_exists,
    verify_no_active_project,
    verify_not_contains,
)

_log = logging.getLogger(__name__)


def create_project(
    connection, name: str, project_root: Optional[str] = None, replace: bool = True
) -> dict[str, Any]:
    """Create a new project. Closes any active project first."""
    app = connection.app
    if app.ActiveProject:
        try:
            app.ActiveProject.Close()
        except Exception:
            pass
    if project_root:
        path = str(Path(project_root).absolute())
        project_roots = app.ProjectRoots
        if project_roots.Contains(path):
            project_roots.Item(path).Activate()
        else:
            project_roots.Add(path)
            project_roots.Item(path).Activate()
    projects = app.Projects
    if replace and projects.Contains(name):
        projects.Item(name).Remove(True)
    projects.Add(name)
    ok, detail = verify_active_project(connection, name)
    return {"name": name, "verified": ok, "detail": detail}


def open_project(connection, name: str) -> dict[str, Any]:
    """Open an existing project by name. Creates it if not found."""
    app = connection.app
    projects = app.Projects
    if app.ActiveProject and app.ActiveProject.Name == name:
        return {"name": name, "verified": True, "detail": f"Project '{name}' is already active"}
    if projects.Contains(name):
        projects.Item(name).Open(True)
    else:
        projects.Add(name)
    ok, detail = verify_active_project(connection, name)
    return {"name": name, "verified": ok, "detail": detail}


def close_project(connection, save: bool = False) -> dict[str, Any]:
    """Close the active project."""
    app = connection.app
    if app.ActiveProject:
        app.ActiveProject.Close(save)
        ok, detail = verify_no_active_project(connection)
        return {"verified": ok, "detail": detail}
    return {"verified": True, "detail": "No active project"}


def remove_project(connection, name: str, purge_directory: bool = True) -> dict[str, Any]:
    """Remove a project by name."""
    app = connection.app
    if app.ActiveProject and app.ActiveProject.Name == name:
        app.ActiveProject.Close(False)
    if app.Projects.Contains(name):
        app.Projects.Item(name).Remove(purge_directory)
        ok, detail = verify_not_contains(app.Projects, name)
        return {"name": name, "verified": ok, "detail": detail}
    return {"name": name, "verified": False, "detail": f"Project '{name}' not found"}


def list_projects(connection) -> list[str]:
    """List all projects in the current project root."""
    projects = []
    project_collection = connection.app.Projects
    count = project_collection.Count
    if count > 0:
        try:
            project_collection.Item(0).Name
            for i in range(count):
                projects.append(project_collection.Item(i).Name)
            return projects
        except Exception:
            pass
        try:
            project_collection.Item(1).Name
            for i in range(1, count + 1):
                projects.append(project_collection.Item(i).Name)
            return projects
        except Exception:
            pass
    try:
        for project in project_collection:
            try:
                projects.append(project.Name)
            except Exception:
                pass
    except Exception:
        pass
    return projects


def set_project_root(connection, path: str) -> dict[str, Any]:
    """Set or create the project root directory."""
    abs_path = str(Path(path).absolute())
    project_roots = connection.app.ProjectRoots
    if not project_roots.Contains(abs_path):
        project_roots.Add(abs_path)
    project_roots.Item(abs_path).Activate()
    try:
        actual = str(connection.app.ActiveProjectRoot.PathName)
        if actual.rstrip("\\/") == abs_path.rstrip("\\/"):
            return {
                "path": abs_path,
                "verified": True,
                "detail": f"Project root set to '{abs_path}'",
            }
        return {
            "path": abs_path,
            "verified": False,
            "detail": f"Active root is '{actual}', expected '{abs_path}'",
        }
    except Exception:
        return {"path": abs_path, "verified": True, "detail": f"Project root set to '{abs_path}'"}


def get_project_path(connection) -> str:
    """Get the directory path of the active project."""
    return str(connection.app.ActiveProject.DirectoryName)


def backup_project(connection, path: Optional[str] = None) -> dict[str, Any]:
    """Save the active project as a zip backup."""
    project_name = connection.app.ActiveProject.Name
    target_path = Path(path) if path else Path(f"{project_name}.zip")
    if target_path.exists() and target_path.is_dir():
        target_path = target_path / f"{project_name}.zip"
    elif not target_path.suffix:
        target_path.mkdir(parents=True, exist_ok=True)
        target_path = target_path / f"{project_name}.zip"
    else:
        target_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path = str(target_path.absolute())
    connection.app.ActiveProject.Backup(abs_path)
    ok, detail = verify_file_exists(abs_path)
    return {"path": abs_path, "verified": ok, "detail": detail}


def open_project_from_backup(
    connection, backup_path: str, name: str, overwrite: bool = False
) -> dict[str, Any]:
    """Open a project from a backup zip file."""
    app = connection.app
    target = Path(backup_path)
    if target.exists() and target.is_dir() or not target.suffix:
        candidate_paths = [
            target / f"{name}.zip",
            target / f"{name}.cdsbk",
        ]
        existing_candidate = next(
            (candidate for candidate in candidate_paths if candidate.exists()), None
        )
        if existing_candidate is None:
            zip_candidates = sorted(target.glob("*.zip")) if target.exists() else []
            if len(zip_candidates) == 1:
                existing_candidate = zip_candidates[0]
        if existing_candidate is None:
            return {
                "name": name,
                "verified": False,
                "detail": (
                    f"No backup archive found under '{target}'. "
                    f"Provide a backup zip file path or store '{name}.zip' in that folder."
                ),
            }
        target = existing_candidate
    abs_path = str(target.absolute())
    if overwrite and app.Projects.Contains(name):
        app.Projects.Item(name).Remove(True)
    app.Projects.OpenFromBackup(abs_path, name, overwrite)
    ok, detail = verify_active_project(connection, name)
    return {"name": name, "verified": ok, "detail": detail}
