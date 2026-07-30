"""COM wrappers for ConfigurationDesk build management operations.

All functions must be called on the STA thread via dispatch().
"""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)


def build_application(
    connection, download: bool = True, start: bool = True, unload: bool = True
) -> dict[str, Any]:
    """Build the ConfigurationDesk application with options download, and start."""
    bm = connection.build_management
    bm.Properties.Item("UnloadLoadedApplication").Value = unload
    bm.Properties.Item("DownloadAfterBuild").Value = download
    bm.Properties.Item("StartAfterDownload").Value = start

    build_result = bm.Build()
    if build_result.Success:
        return {
            "success": True,
            "result_folder": str(build_result.ResultFolderFullPath),
            "rta_path": str(build_result.RtaFullPath),
        }
    if build_result.Canceled:
        return {"success": False, "canceled": True}
    return {"success": False, "canceled": False}


def get_build_result(connection) -> str:
    """Get the path to the build result directory."""
    return str(connection.build_management.DirectoryName)
