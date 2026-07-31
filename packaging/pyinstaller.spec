# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification for the ConfigurationDesk MCP executable."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

ROOT = Path(SPECPATH).parent
SERVER_ROOT = ROOT / "ConfigurationDeskMCP"
TOOLS_ROOT = SERVER_ROOT / "sources" / "tools"

hiddenimports = (
    collect_submodules("sources")
    + collect_submodules("configurationdesk_com_bridge")
    + [
        "pythoncom",
        "pywintypes",
        "win32com.client",
        "win32com.client.dynamic",
    ]
)

datas = [
    # Runtime discovery uses pkgutil.iter_modules on this package path.
    (str(TOOLS_ROOT), "sources/tools"),
    *copy_metadata("configurationdesk-mcp-server"),
    *copy_metadata("configurationdesk-com-bridge"),
]

a = Analysis(
    [str(SERVER_ROOT / "sources" / "__main__.py")],
    pathex=[str(SERVER_ROOT), str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="configurationdesk-mcp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    version=None,
)
