"""FastMCP instance and COM bridge lifespan."""

from __future__ import annotations

import logging
import platform
import struct
import sys
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

from sources.config.settings import get_settings
from sources.utils.logger import configure_root_level, get_logger

_log = get_logger(__name__)

# Suppress FastMCP internal logging
logging.getLogger("mcp.server").setLevel(logging.WARNING)
logging.getLogger("mcp.server.fastmcp").setLevel(logging.WARNING)


def _validate_runtime() -> None:
    if sys.version_info < (3, 11):
        msg = f"Python 3.11+ required; running {sys.version}. Upgrade the Python interpreter."
        raise RuntimeError(msg)
    if platform.system() == "Windows" and struct.calcsize("P") != 8:
        msg = (
            "A 64-bit Python interpreter is required on Windows. "
            "The COM ConfigurationDesk automation interface does not support 32-bit clients."
        )
        raise RuntimeError(msg)


@asynccontextmanager
async def _lifespan(server: FastMCP) -> Any:  # type: ignore[type-arg]
    """Configure logging, validate runtime, and bracket COM bridge lifecycle."""
    cfg = get_settings()
    configure_root_level(cfg.log_level)

    _log.debug(
        "ConfigurationDesk MCP Server starting (transport=%s, log_level=%s)",
        cfg.mcp_transport,
        cfg.log_level,
    )

    _validate_runtime()
    _log.debug("Runtime validation passed (Python %s, 64-bit OK)", sys.version.split()[0])

    import configurationdesk_com_bridge as com_bridge  # noqa: PLC0415

    await com_bridge.startup(
        default_timeout_ms=cfg.com_timeout_ms,
        launch_timeout_ms=cfg.com_launch_timeout_ms,
        reconnect_attempts=cfg.com_reconnect_attempts,
    )
    _log.info("STA thread started; COM connection deferred until first tool call")

    try:
        yield {}
    finally:
        _log.debug("ConfigurationDesk MCP Server shutting down")
        await com_bridge.shutdown()


_cfg = get_settings()

mcp = FastMCP(
    name="ConfigurationDesk MCP Server",
    instructions="""\
Automates dSPACE ConfigurationDesk and BusManager via COM.

## RULES (follow strictly)
1. Call `start_configurationdesk` before ANY other domain tool.
2. If `start_configurationdesk` fails, call `diagnose_connection` — do NOT retry blindly.
3. Never retry the SAME failing tool call more than 2 times. If it fails twice, try a different approach or call `get_application_status` to understand the current state.
4. All tools return JSON with `success` field. Check it EVERY time. On failure, read `error_code`, `recovery_hint`, and `next_action` fields for what to do next.
5. If any tool returns `"retryable": false`, do NOT retry it. Follow the `recovery_hint` instead.
6. In a multi-step workflow, if any step returns `success=false` or a required verification fails, STOP. Explain the failure to the user and ask whether to continue with later steps. Do NOT skip ahead, reinterpret the step, or choose an alternate path without explicit user approval.

## WORKFLOW POLICY 
Honor the user's requested operation. Do not require unrelated workflow steps.

Before calling a tool, satisfy only its stated preconditions. Typical shared
prerequisites.

## COMMON WORKFLOW RECIPE
1. `start_configurationdesk` → establishes COM connection
2. `set_project_root` → set folder for projects (e.g., "D:/Projects")
3. `create_project` or `open_project` → project must exist before anything else
4. `add_application` → required container for all configuration
5. `add_communication_matrix` → load ARXML/DBC/LDF file
6. `create_bus_configuration` → creates empty bus config
7. `assign_ecu_to_bus_config` → assign whole ECUs for restbus simulation
7b. `assign_matrix_to_bus_config` → assign exact clusters, PDUs, or signals when the user or use case names them explicitly
8. `add_feature_to_bus_element` → add signal/PDU/controller features
8b. `set_bus_config_element_property` → set feature-node or bus-element properties like countdown, overwrite, offset, or frame-length values
8c. `set_matrix_element_property` → set communication-matrix element properties like PDU/signal Length or Initial value
9. `add_model` → load behavior model (.slx/.sic/.bsc)
10. `create_application_process` → set up execution scheduling
11. `auto_connect_matching_io_function_blocks_to_model_ports` → wire bus ports to model
12. `generate_bus_containers` → OPTIONAL: generate BSC/container output only when the user explicitly asks for it
13. Hardware topology → ASK USER which approach:
    - `add_hardware_platform` → register SCALEXIO, MicroAutoBox III, or MicroLabBox II hardware (needs address from user)
    - `import_hardware_topology` → import .htfx file (needs file path from user)
    - `add_application_processing_unit` → no physical hardware / VEOS workflow
    - VEOS does NOT need platform registration. Use generate_bus_containers for BSC files.
14. `create_io_function_block` → create CAN/LIN/Ethernet I/O block
15. `set_io_function_block_property` → set BaudRate
16. `assign_bus_access` → link bus access requests to function block
17. `auto_assign_channel_set` or `assign_channel_set` → assign hardware channel
18. `check_conflicts` → verify no issues remain
19. `build_application` → compile and optionally deploy

## KEY FEATURE NAMES (exact strings for add_feature_to_bus_element)
- Signal values: `BusISignalValueAccess` (most common)
- Frame access: `BusFrameAccess`
- PDU enable: `BusPduEnableAccess` (TX only)
- Controller enable: `BusCommunicationControllerEnableAccess`
- LIN schedule: `BusCommunicationControllerLinScheduleTableAccess`
- Config enable: `BusConfigurationEnableAccess`
- RX status: `BusPduRxStatusAccess`

## COMMON BAUD RATES (for set_io_function_block_property)
- CAN: BaudRate=500000
- CAN-FD: BaudRate=500000, DataPhaseBaudRate=2000000 or 4000000
- LIN: BaudRate=19200

## COMMON CONFUSIONS (read carefully — avoid these mistakes)
- "Create a bus configuration" → `create_bus_configuration` (NOT `create_io_function_block`)
- "Create a function block" or "create I/O block" → `create_io_function_block` (NOT `create_bus_configuration`)
- "Generate containers" for bus config → `generate_bus_containers`
- "Generate bus containers (BSC files)" → `generate_bus_containers`
- "Assign ECU" to bus config → `assign_ecu_to_bus_config` (NOT `assign_matrix_to_bus_config`)
- "Assign exact PDU(s)" or "assign exact signal(s)" to a bus config → `assign_matrix_to_bus_config` with a precise `matrix_xpath` (NOT `assign_ecu_to_bus_config`)
- If the user or use case names exact PDUs or signals, keep that scope literal. Do NOT widen to whole-ECU assignment unless explicitly requested.
- Ask the user only when the named PDU/signal scope is materially ambiguous across multiple ECUs/clusters or the instructions conflict.
- "Set baud rate" → `set_io_function_block_property` (this is a hardware I/O setting, not bus config)
- "Set function port property" or "set IsMappable / InitialValue on a port" → `set_function_port_property`
- Do NOT call `generate_bus_containers` just to inspect, list, or set function-port properties. Function ports are exposed by assigned bus features; use `find_bus_config_elements` and `set_function_port_property` first.
- If `set_function_port_property` fails because ports or property nodes are missing, call `find_bus_config_elements` and verify the assigned bus features / exact port XPath. Do NOT use `generate_bus_containers` as recovery for that failure.
- "Set feature property", "set manipulation property", "set countdown", "set overwrite value", "set offset value", or "set frame length feature" → `set_bus_config_element_property` (NOT `set_function_port_property`)
- "Set matrix property", "set signal length", "set PDU length", or "set matrix initial value" → `set_matrix_element_property` (NOT `set_bus_config_element_property`)
- "Set baud rate" → `set_io_function_block_property` (this is a hardware I/O setting, not bus config)
- "Assign bus access" → `assign_bus_access` (links requests to I/O function blocks)
- "Load communication database (.arxml/.dbc/.ldf)" → `add_communication_matrix`
- "Add .arxml file" or "add .dbc file" or "add .ldf file" → `add_communication_matrix`
- "Import bus network definition" → `add_communication_matrix`

## DOMAIN HIERARCHY (understand what each artifact is)
- **Communication Matrix** (.arxml/.dbc/.ldf) = network definition file → `add_communication_matrix`
- **Bus Configuration** = simulation setup (create, assign ECUs, add features) → `create_bus_configuration`
- **Bus Config Element / Feature Node Property** = run-time configuration on bus-config elements such as manipulation countdowns, overwrite values, or frame-length feature values → `set_bus_config_element_property`
- **Function Port Property** = port interface property such as `IsMappable`, `IsTestAutomationSupportEnabled`, or `InitialValue` on a function port exposed by bus features → `set_function_port_property`
- **Matrix Element Property** = communication-database property such as PDU/signal `Length` or signal `Initial value` → `set_matrix_element_property`
- **I/O Function Block Property** = hardware access setting such as `BaudRate` → `set_io_function_block_property`
- **Bus Simulation Container** (.bsc) = compiled artifact for explicit BSC delivery, VEOS consumption, or other user-requested container output → `generate_bus_containers`
- Most workflows use: matrix → bus config → features/property edits → model/app-process/hardware setup, with optional BSC generation only when the user asks for it.

## ERROR RECOVERY
- `COM_DISCONNECTED` → call `start_configurationdesk`
- `COM_TIMEOUT` → retry once after short pause
- `COM_UI_BLOCKING` → tell user to dismiss ConfigurationDesk dialog, then retry
- `BRIDGE_PRECONDITION` → call `get_application_status` to check what's missing
- `BRIDGE_CIRCUIT_OPEN` → call `stop_configurationdesk` then `start_configurationdesk`
- `BRIDGE_NOT_INSTALLED` → stop; ConfigurationDesk is not installed on this machine

## WORKFLOW FAILURE POLICY
- On any non-retryable step failure, stop the workflow, explain the error in plain language, and ask the user whether to continue with later steps.
- On a retryable failure, retry at most once when the recovery guidance says to do so; if it still fails, stop and ask the user before proceeding.
- Do not silently continue past a failed step just because a later step might still work.
""",
    lifespan=_lifespan,
    log_level=_cfg.log_level,
)


# ── Domain tool registration ──────────────────────────────────────────────────
# Importing registry triggers all @mcp.tool decorators, registering every domain tool.

import sources.server.registry  # noqa: E402, F401
