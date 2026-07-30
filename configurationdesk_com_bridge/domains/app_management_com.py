"""COM wrappers for ConfigurationDesk application management.

All functions must be called on the STA thread via dispatch().
"""

from __future__ import annotations

import logging
from typing import Any

from configurationdesk_com_bridge.domains.verify_com import (
    verify_active_application,
    verify_not_contains,
)

_log = logging.getLogger(__name__)


def add_application(connection, name: str) -> dict[str, Any]:
    """Add and activate a new application within the active project."""
    app = connection.app
    if app is None:
        return {
            "name": name,
            "verified": False,
            "detail": "COM connection lost. Call start_configurationdesk first.",
        }
    active_project = app.ActiveProject
    if active_project is None:
        return {
            "name": name,
            "verified": False,
            "detail": "No active project. Call create_project or open_project first.",
        }
    applications = active_project.Applications
    if applications is None:
        return {
            "name": name,
            "verified": False,
            "detail": "Cannot access Applications collection. Call create_project first.",
        }
    if not applications.Contains(name):
        applications.Add(name, True)
    else:
        item = applications.Item(name)
        if item is not None:
            item.Activate(True)
    ok, detail = verify_active_application(connection, name)
    return {"name": name, "verified": ok, "detail": detail}


def activate_application(connection, name: str) -> dict[str, Any]:
    """Activate an existing application."""
    app = connection.app
    applications = app.ActiveProject.Applications
    if not applications.Contains(name):
        return {"name": name, "verified": False, "detail": f"Application '{name}' not found"}
    applications.Item(name).Activate(True)
    ok, detail = verify_active_application(connection, name)
    return {"name": name, "verified": ok, "detail": detail}


def remove_application(connection, name: str, delete: bool = True) -> dict[str, Any]:
    """Remove an application from the active project."""
    applications = connection.app.ActiveProject.Applications
    if not applications.Contains(name):
        return {"name": name, "verified": False, "detail": f"Application '{name}' not found"}
    applications.Item(name).Remove(delete)
    ok, detail = verify_not_contains(applications, name)
    return {"name": name, "verified": ok, "detail": detail}


def list_applications(connection) -> dict[str, Any]:
    """List all applications in the active project."""
    apps = []
    applications = connection.app.ActiveProject.Applications
    count = applications.Count
    # Try 1-based indexing first; fall back to 0-based if it fails
    if count > 0:
        try:
            applications.Item(1).Name
            for i in range(1, count + 1):
                apps.append(applications.Item(i).Name)
        except Exception:
            # 0-based indexing fallback
            try:
                for i in range(count):
                    apps.append(applications.Item(i).Name)
            except Exception:
                # Last resort: iterate the COM collection directly
                for app_item in applications:
                    try:
                        apps.append(app_item.Name)
                    except Exception:
                        pass
    active = None
    try:
        active = connection.app.ActiveApplication.Name
    except Exception:
        try:
            active = connection.app.ActiveApplication.Application.Name
        except Exception:
            pass
    return {"applications": apps, "active": active}
