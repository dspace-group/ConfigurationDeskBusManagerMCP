"""COM wrappers for ConfigurationDesk model topology operations.

All functions must be called on the STA thread via dispatch().
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from configurationdesk_com_bridge.domains.verify_com import (
    list_application_process_names,
    list_model_names,
    wait_for_new_names,
    wait_for_state,
)

_log = logging.getLogger(__name__)


def add_model(
    connection, path: str, analyze: bool = True, create_preconfigured: bool = True
) -> dict[str, Any]:
    """Add a model file to the project."""
    abs_path = os.path.abspath(path)
    mt = connection.model_topology
    if abs_path.endswith((".sic", ".bsc", ".fmu")):
        analyze = False
    before = list_model_names(connection)
    mt.Configure("AddModel", [abs_path, analyze, "", create_preconfigured])
    verified, added, all_models = wait_for_new_names(
        lambda: list_model_names(connection),
        before,
        timeout_s=120.0,
    )
    return {
        "path": abs_path,
        "added": added,
        "verified": verified,
        "all_models": sorted(all_models),
    }


def replace_model(
    connection, path: str, model_name: Optional[str] = None, analyze: bool = True
) -> dict[str, Any]:
    """Replace model(s) with a new model file."""
    abs_path = os.path.abspath(path)
    mt = connection.model_topology
    if model_name:
        mt.Configure("ReplaceModel", [abs_path, analyze, "", model_name])
    else:
        if abs_path.endswith((".sic", ".bsc")):
            mt.Configure("Replace", [6, "ModelTopology", abs_path, False])
        else:
            mt.Configure("Replace", [abs_path, analyze, ""])
    return {"path": abs_path, "model_name": model_name}


def remove_model(connection, name: str) -> dict[str, Any]:
    """Remove a model from the project."""
    connection.model_topology.Configure("RemoveModel", [name])
    remaining = list_model_names(connection)
    verified = name not in remaining
    return {"name": name, "verified": verified, "remaining": remaining}


def analyze_models(connection) -> dict[str, Any]:
    """Analyze all models for ports and interfaces."""
    connection.model_topology.Configure("AnalyzeComplete", [])
    return {"issued": True}


def _create_data_object(rel, parent, type_name: str):
    """Create a child DataObject of ``type_name`` under ``parent`` via *rel*.

    Preferred path is via the relation's ``GetCreatableTypes`` and ``CreateDataObject`` methods:
        creatable = relation.GetCreatableTypes(parent)
        relation.CreateDataObject(creatable.Item(<TypeName>), parent)

    Falls back to ``parent.CreateChild(parent.DataObjectTypes.Item(<TypeName>))``
    when the relation does not expose ``GetCreatableTypes``/``CreateDataObject``
    or the named type is not found there. Returns the created object or
    ``None`` if both paths fail.
    """
    # Preferred relation-based path.
    try:
        creatable = rel.GetCreatableTypes(parent)
    except Exception:
        creatable = None

    if creatable is not None:
        target_type = None
        try:
            for idx in range(1, creatable.Count + 1):
                cand = creatable.Item(idx)
                try:
                    if cand.Name == type_name:
                        target_type = cand
                        break
                except Exception:
                    continue
        except Exception:
            target_type = None
        if target_type is not None:
            try:
                return rel.CreateDataObject(target_type, parent)
            except Exception as exc:
                _log.debug("CreateDataObject(%s) failed: %s", type_name, exc)

    # Fallback: CreateChild via the parent's DataObjectTypes collection.
    try:
        type_obj = parent.DataObjectTypes.Item(type_name)
    except Exception:
        return None
    try:
        return parent.CreateChild(type_obj)
    except Exception as exc:
        _log.debug("CreateChild(%s) failed: %s", type_name, exc)
        return None


def _iter_relation_descendants(rel, parent):
    try:
        children = rel.GetElements(parent)
    except Exception:
        return []

    collected = []
    for child in children:
        collected.append(child)
        collected.extend(_iter_relation_descendants(rel, child))
    return collected


def _resolve_processing_unit_application(connection, atm_relation):
    """Locate the ProcessingUnitApplication under the executable application.

    Returns ``(pu_application, error_detail)``. When the PU cannot be found,
    ``pu_application`` is ``None`` and ``error_detail`` describes the cause.
    """
    try:
        top_nodes = atm_relation.GetTopNodes()
    except Exception as exc:
        return None, f"Cannot read ApplicationConfiguration top nodes: {exc}"
    try:
        if top_nodes.Count == 0:
            return None, (
                "ApplicationConfiguration has no top-level executable application. "
                "Register a hardware platform or call add_application_processing_unit first."
            )
        exec_app = top_nodes.Item(0)
    except Exception as exc:
        return None, f"Cannot access executable application: {exc}"

    try:
        descendants = _iter_relation_descendants(atm_relation, exec_app)
    except Exception as exc:
        return None, f"Cannot enumerate ApplicationConfiguration descendants: {exc}"

    pu_application = None
    for el in descendants:
        try:
            roles = list(el.Roles)
        except Exception:
            roles = []
        if "ProcessingUnitApplication" in roles:
            pu_application = el
            break

    if pu_application is None:
        return None, (
            "No ProcessingUnitApplication is available under the active executable application. "
            "ConfigurationDesk treats hardware topology and processing-unit applications as separate "
            "configuration objects; register/import hardware for processing-unit assignment, then add a "
            "ProcessingUnitApplication explicitly before creating an application process."
        )
    return pu_application, ""


def _set_provide_default_task(process) -> tuple[bool, str]:
    """Set the ``ProvideDefaultTask`` property on an application process.

    Mirrors the UI checkbox *Provide default task* on the Application Process
    Properties pane. When set to ``True``, ConfigurationDesk automatically
    creates a periodic default task with a resolved runnable function on the
    application process (or converts an existing periodic task into the
    default task). This is the canonical, documented way to obtain an
    "application process providing default task" via the automation API.

    Returns ``(success, detail)``. The detail string identifies which
    property name was matched (the COM identifier is not always the same
    PascalCase string across releases, so we probe a few well-known
    spellings and finally enumerate ``Properties`` for any name that
    contains "DefaultTask").
    """
    candidates = ("ProvideDefaultTask", "ProvidesDefaultTask", "HasDefaultTask")
    for prop_name in candidates:
        try:
            prop = process.Properties.Item(prop_name)
        except Exception:
            continue
        try:
            if prop.TrySetValue(True):
                return True, prop_name
        except Exception:
            try:
                prop.Value = True
                return True, prop_name
            except Exception:
                continue

    # Fallback: enumerate properties and look for any with "DefaultTask" in
    # the name. This is defensive against COM identifier renames.
    try:
        for prop in process.Properties:
            try:
                pname = prop.Name
            except Exception:
                continue
            if "DefaultTask" not in pname:
                continue
            try:
                if prop.TrySetValue(True):
                    return True, pname
            except Exception:
                try:
                    prop.Value = True
                    return True, pname
                except Exception:
                    continue
    except Exception:
        pass
    return False, ""


def _find_default_task_name(process) -> Optional[str]:
    """Return the name of the (default) task on *process*, if any."""
    try:
        for child in process:
            try:
                roles = list(child.Roles)
            except Exception:
                roles = []
            if "Task" in roles or "DefaultTask" in roles:
                try:
                    return child.Name
                except Exception:
                    continue
        # Fallback: first child.
        try:
            if process.Count > 0:
                return process.Item(0).Name
        except Exception:
            pass
    except Exception:
        pass
    return None


def _assign_process_to_bus_configs(
    connection,
    process,
    process_name: Optional[str],
    bus_config_names: Optional[list[str]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Assign the freshly created application process to bus configurations.

    * ``bus_config_names is None`` → assign to *all* existing bus configurations
      (so the freshly created application-process-with-default-task becomes
      immediately usable for bus simulation, mirroring the UX expectation).
    * ``bus_config_names == []`` → skip assignment.
    * Specific names → only those configurations are targeted; missing names
      are reported back.

    Returns ``(assignments, missing_names)``.
    """
    assignments: list[dict[str, Any]] = []
    missing: list[str] = []

    try:
        bc_props_rel = connection.relations.Item("BusConfigurationsWithProperties")
    except Exception as exc:
        assignments.append(
            {"error": True, "detail": f"BusConfigurationsWithProperties not available: {exc}"}
        )
        return assignments, missing

    try:
        top_bcs = list(bc_props_rel.GetTopNodes())
    except Exception as exc:
        assignments.append({"error": True, "detail": f"Cannot enumerate bus configurations: {exc}"})
        return assignments, missing

    bcs_by_name: dict[str, Any] = {}
    for node in top_bcs:
        try:
            bcs_by_name[node.Name] = node
        except Exception:
            continue

    if bus_config_names is None:
        # Assign to every existing bus configuration.
        targets = list(bcs_by_name.items())
    elif not bus_config_names:
        return assignments, missing
    else:
        targets = []
        for bc_name in bus_config_names:
            bc = bcs_by_name.get(bc_name)
            if bc is None:
                missing.append(bc_name)
                assignments.append(
                    {
                        "bus_config": bc_name,
                        "verified": False,
                        "error": True,
                        "detail": f"Bus configuration '{bc_name}' not found.",
                    }
                )
                continue
            targets.append((bc_name, bc))

    for bc_name, bc in targets:
        try:
            bc.Properties.Item("ManuallyAssignedApplicationProcess").Value = process
        except Exception as exc:
            assignments.append(
                {
                    "bus_config": bc_name,
                    "verified": False,
                    "error": True,
                    "detail": f"Assignment failed: {exc}",
                }
            )
            continue

        assigned_name: Optional[str] = None
        try:
            readback = bc.Properties.Item("ManuallyAssignedApplicationProcess").Value
            if readback is not None:
                assigned_name = readback.Name
        except Exception:
            assigned_name = None
        assignments.append(
            {
                "bus_config": bc_name,
                "verified": bool(assigned_name) and assigned_name == process_name,
                "assigned_process": assigned_name,
            }
        )

    return assignments, missing


def create_application_process(
    connection,
    name: Optional[str] = None,
    bus_config_names: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Create an application process that provides a default task.

    Mirrors the ConfigurationDesk UI command
    *New → Application Process (Providing Default Task)*:

      1. Create an ``ApplicationProcess`` on the ``ProcessingUnitApplication``
         of the active executable application via the
         ``ApplicationConfiguration`` relation.
      2. Set the application process's ``ProvideDefaultTask`` property to
         ``True``. ConfigurationDesk then automatically creates a periodic
         default task with a resolved runnable function on the application
         process — exactly what the UI command produces.
      3. Optionally assign the freshly created application process to bus
         configurations (sets ``ManuallyAssignedApplicationProcess`` on each
         target bus configuration).

    This is the canonical way to set up scheduling when working *without* a
    behavior model (e.g. pure restbus simulation that is only accessed from
    experiment software). Use :func:`create_preconfigured_application_process`
    instead when an application process should be created for a specific
    behavior model.

    Parameters
    ----------
    name
        Optional human-readable name for the new application process. When
        omitted, the ConfigurationDesk default name is kept.
    bus_config_names
        Controls bus configuration assignment of the new application process:

        * ``None`` (default) → assign to **every** existing bus configuration.
          This mirrors the expectation that an application-process-with-default-
          task should immediately drive the existing bus configurations.
        * Non-empty list → assign only to the named bus configurations.
          Unknown names are returned in ``missing_bus_configs``.
        * Empty list (``[]``) → skip bus configuration assignment entirely.
    """
    try:
        atm_relation = connection.relations.Item("ApplicationConfiguration")
    except Exception as exc:
        return {"error": True, "detail": f"ApplicationConfiguration relation not available: {exc}"}

    pu_application, detail = _resolve_processing_unit_application(connection, atm_relation)
    if pu_application is None:
        return {"error": True, "detail": detail}

    before_processes = set(list_application_process_names(connection))

    # 1) Create the application process.
    process = _create_data_object(atm_relation, pu_application, "ApplicationProcess")
    if process is None:
        return {
            "error": True,
            "detail": (
                "Could not create an ApplicationProcess child on the "
                "ProcessingUnitApplication via either GetCreatableTypes/"
                "CreateDataObject or CreateChild."
            ),
        }

    # 2) Optional rename (do this before flipping ProvideDefaultTask so the
    # auto-created default task can pick up a meaningful default name based
    # on the application process name).
    if name:
        try:
            process.Name = name
        except Exception as exc:
            _log.warning("Could not rename application process to '%s': %s", name, exc)

    # 3) Turn it into an "Application Process providing default task" by
    # toggling the dedicated property. ConfigurationDesk creates the
    # periodic task + runnable function automatically.
    default_task_set, default_task_property = _set_provide_default_task(process)

    # Wait until the new process becomes observable.
    verified, processes_after = wait_for_state(
        lambda: list_application_process_names(connection),
        lambda names: bool(set(names) - before_processes),
        timeout_s=120.0,
    )

    try:
        process_name = process.Name
    except Exception:
        process_name = name

    default_task_name = _find_default_task_name(process) if default_task_set else None

    # 4) Assign the new application process to bus configurations.
    bus_config_assignments, missing_bus_configs = _assign_process_to_bus_configs(
        connection, process, process_name, bus_config_names
    )

    result: dict[str, Any] = {
        "process_name": process_name,
        "default_task_set": default_task_set,
        "default_task_property": default_task_property,
        "default_task_name": default_task_name,
        "verified": verified,
        "created_processes": sorted(set(processes_after) - before_processes),
    }
    if bus_config_assignments:
        result["bus_config_assignments"] = bus_config_assignments
    if missing_bus_configs:
        result["missing_bus_configs"] = missing_bus_configs
    return result


def list_models(connection) -> list[str]:
    """List all models in the current project topology."""
    return list_model_names(connection)


def add_model_to_signal_chain(connection, model_name: str) -> dict[str, Any]:
    """Add all ports of a model to the signal chain.

    Sets ``IsInApplication = True`` on the model's root port block, which
    causes ConfigurationDesk to include every port of that model in the
    signal chain.
    """
    mt = connection.model_topology
    model_block = mt.Item(model_name)
    model_block.IsInApplication = True
    _log.info("Added all ports of model '%s' to the signal chain", model_name)
    return {"model_name": model_name, "scope": "all_ports"}


def add_model_port_to_signal_chain(connection, model_name: str, port_name: str) -> dict[str, Any]:
    """Add a single named port of a model to the signal chain.

    Sets ``IsInApplication = True`` on the specific port block identified by
    *port_name* within the model's port block collection.
    """
    mt = connection.model_topology
    port_block = mt.Item(model_name).Item(port_name)
    port_block.IsInApplication = True
    _log.info("Added port '%s' of model '%s' to the signal chain", port_name, model_name)
    return {"model_name": model_name, "port_name": port_name, "scope": "single_port"}


def list_model_ports(connection, model_name: str) -> list[str]:
    """Return the names of all port blocks available for *model_name*.

    Iterates over the items directly under the model's root block in the
    model topology, which correspond to the model port blocks exposed by
    ConfigurationDesk after model analysis.
    """
    mt = connection.model_topology
    model_block = mt.Item(model_name)
    ports: list[str] = []
    for item in model_block:
        try:
            ports.append(item.Name)
        except Exception:
            _log.warning("Could not enumerate ports for model '%s'", model_name)

    return ports
