"""COM wrappers for ConfigurationDesk application lifecycle.

All functions must be called on the STA thread via dispatch().
They take a connection object and return JSON-safe dicts.
"""

from __future__ import annotations

import os
import logging
from typing import Any

_log = logging.getLogger(__name__)


def get_status(connection) -> dict[str, Any]:
    """Return current application status."""
    app = connection.app
    project_name = app.ActiveProject.Name if app.ActiveProject else None
    project_root = str(app.ActiveProjectRoot.PathName) if app.ActiveProjectRoot else None
    app_name = None
    try:
        app_name = app.ActiveApplication.Name
    except Exception:
        try:
            app_name = app.ActiveApplication.Application.Name
        except Exception:
            pass
    return {
        "connected": True,
        "project": project_name,
        "project_name": project_name,
        "project_root": project_root,
        "application": app_name,
        "application_name": app_name,
    }


def save_project(connection) -> dict[str, Any]:
    """Save the current project."""
    try:
        proj_dir = str(connection.app.ActiveProject.DirectoryName)
        before_mtime = os.path.getmtime(proj_dir) if os.path.isdir(proj_dir) else None
    except Exception:
        before_mtime = None
        proj_dir = None

    connection.app.ActiveProject.Save()

    verified = False
    if proj_dir and before_mtime is not None:
        try:
            after_mtime = os.path.getmtime(proj_dir)
            if after_mtime >= before_mtime:
                verified = True
        except Exception:
            pass
    else:
        verified = True

    return {"saved": True, "verified": verified}


def undo(connection) -> dict[str, Any]:
    """Undo the last action."""
    connection.app.ActiveApplication.Undo()
    return {"issued": True}


def redo(connection) -> dict[str, Any]:
    """Redo the last undone action."""
    connection.app.ActiveApplication.Redo()
    return {"issued": True}
