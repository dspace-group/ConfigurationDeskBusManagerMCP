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


def _create_processing_unit_application(connection) -> tuple[bool, str]:
    """Create a ProcessingUnitApplication child under the top ApplicationConfiguration node.

    Returns (created, detail). ``created=False`` means the call did not succeed
    but was not fatal.
    """
    try:
        atm_relation = connection.relations.Item("ApplicationConfiguration")
    except Exception as exc:
        return False, f"ApplicationConfiguration relation not available: {exc}"

    try:
        top_nodes = atm_relation.GetTopNodes()
        if top_nodes.Count == 0:
            return False, "ApplicationConfiguration has no top-level execution application"
        exec_application = top_nodes.Item(0)
    except Exception as exc:
        return False, f"Cannot read execution application: {exc}"

    # Preferred path: GetCreatableTypes + CreateDataObject (matches COM examples).
    try:
        creatable = atm_relation.GetCreatableTypes(exec_application)
        target_type = None
        for idx in range(1, creatable.Count + 1):
            cand = creatable.Item(idx)
            try:
                cand_name = cand.Name
            except Exception:
                continue
            if cand_name == "ProcessingUnitApplication":
                target_type = cand
                break
        if target_type is None and creatable.Count > 0:
            target_type = creatable.Item(1)
        if target_type is not None:
            atm_relation.CreateDataObject(target_type, exec_application)
            return True, "Created via GetCreatableTypes/CreateDataObject"
    except Exception as exc:
        _log.debug("CreateDataObject path failed: %s", exc)

    # Fallback: CreateChild on the execution application using DataObjectTypes.
    try:
        type_obj = exec_application.DataObjectTypes.Item("ProcessingUnitApplication")
        exec_application.CreateChild(type_obj)
        return True, "Created via CreateChild"
    except Exception as exc:
        return False, f"Cannot create ProcessingUnitApplication: {exc}"


def add_processing_unit_application(connection) -> dict[str, Any]:
    """Add a processing unit application to the executable application.

    A processing unit application is a component of every executable application
    that hosts one or more application processes. This adds one explicitly under
    the top-level ApplicationConfiguration node, which is needed when no registered
    hardware or imported topology already provides one — typically a no-hardware or
    VEOS/BSC build.
    """
    pu_created, pu_detail = _create_processing_unit_application(connection)
    return {
        "processing_unit_created": pu_created,
        "processing_unit_detail": pu_detail,
    }
