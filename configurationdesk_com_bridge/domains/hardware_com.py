"""COM wrappers for ConfigurationDesk hardware topology operations.

All functions must be called on the STA thread via dispatch().

IMPORTANT CONCEPTS:
- Hardware platforms (SCALEXIO, MicroAutoBox III, MicroLabBox II) are registered via
  PlatformManagement.RegisterPlatform and then scanned to create a hardware topology.
  In ConfigurationDesk a "platform" is a registered dSPACE real-time hardware system.
- VEOS is a PC-based simulation platform, not a registered real-time hardware platform,
  so it is not registered here. For VEOS, the Bus Manager generates Bus Simulation
  Containers (BSC) via BusManager.Configure("GenerateContainers", []); the BSCs are then
  imported into VEOS, which builds the offline simulation application. ConfigurationDesk
  itself always builds a real-time application.
- A hardware topology is a separate object from a processing unit application. A hardware
  topology can be created in three ways:
  Mode 0: Scan registered hardware platform
  Mode 1: Import .htfx file
  Mode 2: Create empty topology (no-hardware/VEOS scenarios); a processing unit
          application is added separately to host application processes
"""

from __future__ import annotations

import fnmatch
import logging
import os
import re
from typing import Any, List

from configurationdesk_com_bridge.domains.verify_com import wait_for_state

_log = logging.getLogger(__name__)

# COM enum fallbacks when the dSPACE.COM wrapper is not available.
_PLATFORM_TYPE_MAP = {
    "SCALEXIO": 22,
    "MICROAUTOBOXIII": 33,
    "MICROLABBOXII": 35,
    "DS1403": 33,
    "DS1203": 35,
}
_HW_CREATE_MODE_SCAN = 0
_HW_CREATE_MODE_IMPORT = 1
_HW_CREATE_MODE_EMPTY = 2

_PLATFORM_TYPE_ALIASES = {
    "scalexio": ["SCALEXIO"],
    "microautoboxiii": ["MicroAutoBoxIII", "MicroAutoBox III"],
    "microlabboxii": ["MicroLabBoxII", "MicroLabBox II"],
}


def _normalize_platform_type(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _get_platform_type_enum(connection, platform_type: str):
    enums = connection.enums
    normalized = _normalize_platform_type(platform_type)
    if enums is not None:
        try:
            platform_enum = enums.PlatformType
            for attr_name in dir(platform_enum):
                if attr_name.startswith("_"):
                    continue
                if _normalize_platform_type(attr_name) == normalized:
                    return getattr(platform_enum, attr_name)
            for candidate in _PLATFORM_TYPE_ALIASES.get(normalized, []):
                try:
                    return getattr(platform_enum, candidate)
                except Exception:
                    continue
        except Exception:
            pass
        try:
            return getattr(enums.PlatformType, platform_type)
        except Exception:
            pass
    fallback_key = next(
        (key for key in _PLATFORM_TYPE_MAP if _normalize_platform_type(key) == normalized),
        None,
    )
    val = _PLATFORM_TYPE_MAP.get(fallback_key) if fallback_key else None
    if val is not None:
        return val
    if enums is None and normalized in {"microautoboxiii", "microlabboxii"}:
        raise ValueError(
            f"Platform type '{platform_type}' requires the dSPACE COM Enums helper. "
            "Set CONFIGURATIONDESK_COMMON_PATH so ConfigurationDesk platform enums can be loaded."
        )
    raise ValueError(
        f"Unknown platform type '{platform_type}'. Valid: SCALEXIO, MicroAutoBox III, MicroLabBox II"
    )


def _get_hw_create_mode(connection, mode: int):
    """Get hardware topology create mode. Accepts integer 0/1/2."""
    return mode


def _iter_hardware_items(hw):
    try:
        for item in hw:
            yield item
        return
    except (TypeError, AttributeError):
        pass

    try:
        count = int(hw.Count)
        for index in range(count):
            try:
                yield hw.Item(index)
            except Exception:
                pass
        return
    except Exception:
        pass

    try:
        count = int(hw.Count)
        for index in range(1, count + 1):
            try:
                yield hw.Item(index)
            except Exception:
                pass
    except Exception:
        pass


def _get_hardware_topology_name(connection) -> str:
    try:
        return str(connection.hw_topology.Name)
    except Exception:
        return ""


def list_hardware_names(connection) -> list[str]:
    hw = connection.hw_topology
    names: list[str] = []
    for item in _iter_hardware_items(hw):
        try:
            names.append(item.Name)
        except Exception:
            pass
    return names


def add_hardware_platform(
    connection, ip_addresses: List[str], platform_type: str = "SCALEXIO"
) -> dict[str, Any]:
    """Register and scan a SCALEXIO hardware platform by IP address(es).

    VEOS is not a registered real-time hardware platform. For VEOS workflows:
    - Use generate_bus_containers to create BSC files
    - Import the BSC files into VEOS, which builds the offline simulation application
    - Or use add_processing_unit_application to add a processing unit application for a
      no-hardware build (no download needed)
    """
    if platform_type.upper() == "VEOS":
        return {
            "error": True,
            "detail": (
                "VEOS is not a registered real-time hardware platform and cannot be registered here. "
                "For VEOS workflows: 1) Configure your bus configuration normally, "
                "2) Call generate_bus_containers to generate BSC files, "
                "3) Import the BSC files into VEOS, which builds the offline simulation application. "
                "If you need a processing unit application for the build, use add_processing_unit_application."
            ),
        }

    pm = connection.platform_management
    pm.PlatformAutomationAPIVersion = 2
    before_items = list_hardware_names(connection)

    # Try to refresh platform configuration
    try:
        pm.RefreshPlatformConfiguration()
    except Exception:
        _log.debug("RefreshPlatformConfiguration skipped (dynamic dispatch)")

    if not ip_addresses:
        return {"error": True, "detail": "SCALEXIO platforms require at least one IP address."}

    # Check if platform is already registered
    platform_name = None
    ip_tuple = tuple(ip_addresses)

    try:
        for platform in pm.Platforms:
            if not platform.IsAssignable:
                continue
            try:
                platform_ips = tuple(pu.Identification.IPAddress for pu in platform.ProcessingUnits)
            except Exception:
                platform_ips = ()
            if ip_tuple == platform_ips:
                platform_name = platform.UniqueName
                break
    except Exception:
        pass

    if platform_name is None:
        platform_type_enum = _get_platform_type_enum(connection, platform_type)
        info = pm.CreatePlatformRegistrationInfo(platform_type_enum)

        ri = info.RegistrationInfos
        try:
            ri._FlagAsMethod("Add")
        except Exception:
            pass
        for ip in ip_addresses:
            try:
                reg = ri.Add()
            except Exception:
                import pythoncom

                reg = ri._oleobj_.Invoke(
                    ri._oleobj_.GetIDsOfNames(0, "Add")[0], 0, pythoncom.DISPATCH_METHOD, 1
                )
                import win32com.client

                reg = win32com.client.Dispatch(reg)
            reg.IPAddress = ip

        try:
            platform_obj = pm.RegisterPlatform(info)
            platform_name = platform_obj.UniqueName
        except Exception as exc:
            msg = str(exc)
            if "already registered" in msg.lower():
                try:
                    pm.RefreshPlatformConfiguration()
                    for platform in pm.Platforms:
                        try:
                            platform_ips = tuple(
                                pu.Identification.IPAddress for pu in platform.ProcessingUnits
                            )
                            if ip_tuple == platform_ips:
                                platform_name = platform.UniqueName
                                break
                        except Exception:
                            pass
                except Exception:
                    pass
            if platform_name is None:
                raise

    # Scan the registered platform to create hardware topology
    hw = connection.hw_topology
    try:
        hw.Configure("Create", [_HW_CREATE_MODE_SCAN, "", platform_name])
    except Exception as scan_exc:
        _log.warning("Hardware scan failed for '%s': %s", platform_name, scan_exc)
    verified, hardware_items = wait_for_state(
        lambda: list_hardware_names(connection),
        lambda names: bool(names),
    )
    return {
        "platform_name": platform_name,
        "hardware_items": hardware_items,
        "verified": verified or bool(before_items and hardware_items),
    }


def import_hardware_topology(connection, path: str) -> dict[str, Any]:
    """Import hardware topology from an HTFX file."""
    abs_path = os.path.abspath(path)
    before_items = list_hardware_names(connection)
    hw = connection.hw_topology
    hw.Configure("Create", [_HW_CREATE_MODE_IMPORT, "PredefinedHardware", abs_path])
    verified, hw_items = wait_for_state(
        lambda: list_hardware_names(connection),
        lambda names: bool(names),
    )
    return {
        "path": abs_path,
        "hardware_items": hw_items,
        "verified": verified or bool(before_items and hw_items),
    }


def scan_hardware(connection, platform_name: str) -> dict[str, Any]:
    """Scan a registered platform to create hardware topology."""
    before_items = list_hardware_names(connection)
    hw = connection.hw_topology
    hw.Configure("Create", [_HW_CREATE_MODE_SCAN, "", platform_name])
    verified, hw_items = wait_for_state(
        lambda: list_hardware_names(connection),
        lambda names: bool(names),
    )
    return {
        "platform_name": platform_name,
        "hardware_items": hw_items,
        "verified": verified or bool(before_items and hw_items),
    }


def remove_hardware(connection, name: str) -> dict[str, Any]:
    """Remove hardware element(s) by name (supports wildcards)."""
    hw = connection.hw_topology
    removed = []
    matchers = [name]
    if not any(ch in name for ch in "*?[]"):
        matchers.append(f"{name}*")
        matchers.append(f"*{name}*")

    for item in hw:
        item_name = item.Name
        if any(fnmatch.fnmatchcase(item_name, pattern) for pattern in matchers):
            item.IsInRepository = False
            removed.append(item_name)
    still_in_repo = []
    if removed:
        for item in hw:
            if item.Name in removed:
                try:
                    if item.IsInRepository:
                        still_in_repo.append(item.Name)
                except Exception:
                    pass
    detail = "" if removed else f"No hardware element matching '{name}' found"
    return {
        "removed": removed,
        "still_in_repo": still_in_repo,
        "verified": bool(removed) and not still_in_repo,
        "detail": detail,
    }


def list_platforms(connection) -> list[dict[str, Any]]:
    """List all registered hardware platforms."""
    platforms = []
    pm = connection.platform_management
    try:
        pm.RefreshPlatformConfiguration()
    except Exception:
        _log.debug("RefreshPlatformConfiguration skipped in list_platforms")
    try:
        for platform in pm.Platforms:
            ips = []
            try:
                for pu in platform.ProcessingUnits:
                    try:
                        ips.append(pu.Identification.IPAddress)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                platforms.append(
                    {
                        "name": platform.UniqueName,
                        "assignable": platform.IsAssignable,
                        "ip_addresses": ips,
                    }
                )
            except Exception as e:
                _log.debug("Error reading platform: %s", e)
    except Exception as e:
        _log.warning("Cannot iterate platforms: %s", e)
    return platforms


def refresh_platforms(connection) -> dict[str, Any]:
    """Refresh platform configuration."""
    connection.platform_management.RefreshPlatformConfiguration()
    return {"issued": True}


def add_hardware_element(connection, element_type: str) -> dict[str, Any]:
    """Add a hardware element to the topology by type name.

    element_type can be a name (e.g. 'DS1513', 'VEOS') or an integer index.
    """
    hw = connection.hw_topology
    obj_type = None

    # Try string name lookup first
    try:
        obj_type = hw.DataObjectTypes.Item(element_type)
    except Exception:
        pass

    # If string lookup failed, try to find by iterating available types
    if obj_type is None:
        available_types = []
        try:
            dot = hw.DataObjectTypes
            count = int(dot.Count)
            for i in range(count):
                try:
                    dt = dot.Item(i)
                    dt_name = dt.Name
                    available_types.append(dt_name)
                    if element_type.lower() in dt_name.lower():
                        obj_type = dt
                        break
                except Exception:
                    pass
        except Exception:
            pass
        # Also try 1-based
        if obj_type is None:
            try:
                dot = hw.DataObjectTypes
                count = int(dot.Count)
                for i in range(1, count + 1):
                    try:
                        dt = dot.Item(i)
                        dt_name = dt.Name
                        if dt_name not in available_types:
                            available_types.append(dt_name)
                        if element_type.lower() in dt_name.lower():
                            obj_type = dt
                            break
                    except Exception:
                        pass
            except Exception:
                pass

        if obj_type is None:
            return {
                "error": True,
                "detail": (
                    f"Hardware element type '{element_type}' not found. "
                    f"Available types: {available_types}. "
                    f"Hardware platform must be registered first via add_hardware_platform."
                ),
            }

    before_items = list_hardware_names(connection)
    item = hw.CreateRootObject(obj_type)
    elem_name = item.Name
    before_set = set(before_items)
    verified, hardware_items = wait_for_state(
        lambda: list_hardware_names(connection),
        lambda names: elem_name in names or bool(set(names) - before_set),
    )
    return {
        "element_name": elem_name,
        "hardware_items": hardware_items,
        "verified": verified,
    }
