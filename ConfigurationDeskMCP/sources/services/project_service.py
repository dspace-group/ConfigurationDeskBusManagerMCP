# -*- coding: utf-8 -*-
"""Project management service."""

from __future__ import annotations

from configurationdesk_com_bridge import dispatch, ensure_connected, get_connection
from configurationdesk_com_bridge.domains import project_com
from configurationdesk_com_bridge.errors import BridgeError

from sources.models.envelope_builder import tool_error_result
from sources.services._observations import dispatch_observation
from sources.tools._responses import error_response, success_response
from sources.utils.logger import get_logger

logger = get_logger(__name__)


async def _get_live_connection():
    """Return a connected COM bridge, auto-connecting if needed."""
    conn = get_connection()
    if not conn.is_connected:
        logger.info("Connection not active — calling ensure_connected()")
        await ensure_connected()
        conn = get_connection()
    return conn


async def create_project(name: str, project_root: str | None = None, replace: bool = True) -> str:
    try:
        conn = await _get_live_connection()
        result = await dispatch(project_com.create_project, conn, name, project_root, replace)
        if result.get("verified"):
            return success_response(message=f"Project '{name}' created", verified=True)
        return error_response(result.get("detail", "Project creation failed"), transient=False)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error creating project")
        return error_response(str(e), transient=False)


async def open_project(name: str) -> str:
    try:
        conn = await _get_live_connection()
        result = await dispatch(project_com.open_project, conn, name)
        if result.get("verified"):
            return success_response(message=f"Project '{name}' opened", verified=True)
        return error_response(result.get("detail", "Project open failed"), transient=False)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error opening project")
        return error_response(str(e), transient=False)


async def close_project(save: bool = True) -> str:
    try:
        conn = get_connection()
        result = await dispatch(project_com.close_project, conn, save)
        if result.get("verified"):
            return success_response(message="Project closed", verified=True)
        return error_response(result.get("detail", "Project close failed"), transient=False)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error closing project")
        return error_response(str(e), transient=False)


async def remove_project(name: str, delete_files: bool = False) -> str:
    try:
        conn = get_connection()
        result = await dispatch(project_com.remove_project, conn, name, delete_files)
        if result.get("verified"):
            return success_response(message=f"Project '{name}' removed", verified=True)
        return error_response(result.get("detail", "Project removal failed"), transient=False)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error removing project")
        return error_response(str(e), transient=False)


async def list_projects() -> str:
    try:
        conn = get_connection()
        projects = await dispatch_observation(project_com.list_projects, conn)
        return success_response(projects=projects)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error listing projects")
        return error_response(str(e), transient=False)


async def set_project_root(path: str) -> str:
    try:
        conn = await _get_live_connection()
        result = await dispatch(project_com.set_project_root, conn, path)
        if result.get("verified"):
            return success_response(message=f"Project root set to '{path}'", verified=True)
        return error_response(result.get("detail", "Failed to set project root"), transient=False)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error setting project root")
        return error_response(str(e), transient=False)


async def get_project_path() -> str:
    try:
        conn = get_connection()
        path = await dispatch_observation(project_com.get_project_path, conn)
        return success_response(path=path)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error getting project path")
        return error_response(str(e), transient=False)


async def backup_project(path: str) -> str:
    try:
        conn = get_connection()
        result = await dispatch(project_com.backup_project, conn, path)
        if result.get("verified"):
            return success_response(
                message=f"Project backed up to '{result.get('path')}'",
                verified=True,
                path=result.get("path"),
            )
        return error_response(result.get("detail", "Backup failed"), transient=False)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error backing up project")
        return error_response(str(e), transient=False)


async def open_project_from_backup(backup_path: str, name: str, overwrite: bool = False) -> str:
    try:
        conn = get_connection()
        result = await dispatch(
            project_com.open_project_from_backup, conn, backup_path, name, overwrite
        )
        if result.get("verified"):
            return success_response(
                message="Project restored from backup",
                verified=True,
                backup_path=result.get("path"),
            )
        return error_response(result.get("detail", "Restore failed"), transient=False)
    except BridgeError as exc:
        return tool_error_result(exc)
    except Exception as e:
        logger.exception("Error restoring from backup")
        return error_response(str(e), transient=False)
