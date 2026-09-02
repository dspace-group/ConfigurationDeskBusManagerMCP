# -*- coding: utf-8 -*-
"""Individual (single-task) prompts for the ConfigurationDesk MCP Server.

Each prompt covers ONE focused task built around a commonly used tool. They are
deliberately lean: no "next steps" or "compose into a flow" sections — the single
end-to-end use case lives in ``configurationdesk_prompts.bus_manager_restbus_simulation``.

The set is chosen to cover the most-used tools across the several use cases
(project, matrix, bus config, features, model, application process, port wiring,
bus/analog hardware, inspection/manipulation, conflicts, build, read-only inspect).

Every prompt starts by ensuring ConfigurationDesk is running so it can be invoked
standalone, in any order.

For domain knowledge (feature catalog, XPath patterns, property names, tool
selection), see the ``configurationdesk://reference/*`` resources.
"""

from sources.server.app import mcp

_ENSURE_RUNNING = """\
## Step 0 — Ensure ConfigurationDesk is running
If ConfigurationDesk is not already running, call `start_configurationdesk`
(visible=true) first. It is idempotent — safe to call if it is already up.
If it FAILS, call `diagnose_connection` (do NOT retry blindly) and report back."""


@mcp.prompt(
    name="create_project",
    description="Single task: create or open a ConfigurationDesk project and add an active application",
)
def create_project(
    project_name: str = "MyProject",
    project_root: str = "D:/Projects",
    application_name: str = "Application1",
) -> str:
    return f"""\
# Create or Open a Project

Goal: get a project with an ACTIVE application — required before any matrix,
bus, model, or hardware work.

{_ENSURE_RUNNING}

## Step 1 — Set the project root (optional)
Call `set_project_root` with path="{project_root}". Skip to use the default
location. The folder is created if it does not exist.

## Step 2 — Create or open the project
- New → `create_project` with name="{project_name}" (set replace=true to overwrite).
- Existing → `open_project` with name="{project_name}".
The project is opened and activated automatically.

## Step 3 — Add an application
Call `add_application` with name="{application_name}". An application is REQUIRED
and is auto-activated. (If applications already exist, use `list_applications`
then `activate_application`.)

## Verify
Call `get_application_status` and confirm the project and application are active.
"""


@mcp.prompt(
    name="load_communication_matrix",
    description="Single task: add a communication database (ARXML/DBC/LDF) and explore its clusters, ECUs, and signals",
)
def load_communication_matrix(
    matrix_path: str = "D:/Databases/vehicle_can.arxml",
    ecu_name: str = "ECU1",
) -> str:
    return f"""\
# Load a Communication Matrix

Goal: import the network definition (clusters, ECUs, frames, PDUs, signals) that
is the basis for any bus configuration.

{_ENSURE_RUNNING}

## Step 1 — Add the matrix file
Call `add_communication_matrix` with path="{matrix_path}".
Formats: .arxml (AUTOSAR, most common), .dbc (CAN), .ldf (LIN).
Multiple matrices can be loaded.

## Step 2 — Explore the hierarchy
- `list_matrices` — all loaded clusters and ECUs.
- `find_matrix_elements` with element_type="BusEcu" — every ECU.
- `find_matrix_elements` with xpath="//BusCanCommunicationCluster" — CAN clusters.
- `find_matrix_elements` with xpath='//BusEcu[@Name="{ecu_name}"]//BusISignalIPdu' — one ECU's PDUs.

See the `configurationdesk://reference/xpath` resource for ready-made patterns.
"""


@mcp.prompt(
    name="create_bus_configuration",
    description="Single task: create a bus configuration and assign ECUs for restbus simulation",
)
def create_bus_configuration(
    bus_config_name: str = "CAN_Restbus",
    dut_ecu_name: str = "DUT_ECU",
) -> str:
    return f"""\
# Create a Bus Configuration

Goal: build the simulation setup for a network. A bus configuration has three
parts: Simulated ECUs (restbus), Inspection (monitor RX), Manipulation (override TX).

{_ENSURE_RUNNING}

## Step 1 — Create the configuration
Call `create_bus_configuration` with name="{bus_config_name}".
(NOT `create_io_function_block` — that creates hardware I/O blocks.)

## Step 2 — Assign ECUs
- All ECUs except the DUT (restbus):
  `assign_ecu_to_bus_config` with bus_config_name="{bus_config_name}", ecu_xpath="//BusEcu", exclude_list="{dut_ecu_name}", part="simulated".
- Specific ECUs:
  `assign_ecu_to_bus_config` with bus_config_name="{bus_config_name}", ecu_names=["ECU_A","ECU_B"].
- Whole cluster, or EXACT PDU/signal (keep named scope literal):
  `assign_matrix_to_bus_config` with a precise matrix_xpath, e.g. '//BusCanCommunicationCluster[@Name="MyCluster"]'.
Use the `part` argument ('simulated' / 'inspection' / 'manipulation') to scope it.

## Verify
Call `find_bus_config_elements` with element_type="BusEcu", bus_config_name="{bus_config_name}".
"""


@mcp.prompt(
    name="add_feature_to_bus_element",
    description="Single task: add and configure a bus configuration feature (signal value, frame, PDU enable, controller enable, etc.) on the correct element",
)
def add_feature_to_bus_element(
    bus_config_name: str = "CAN_Restbus",
    feature_type: str = "signal_values",
) -> str:
    feature_guides = {
        "signal_values": (
            "BusISignalValueAccess",
            "BusISignal",
            "Physical value access for signals. In ports for TX signals, Out ports for RX signals. MOST COMMON.",
        ),
        "frame_access": (
            "BusFrameAccess",
            "BusISignalIPdu",
            "Raw frame access (ID, length, raw bytes, CAN-FD flags). Applies to TX and RX PDUs.",
        ),
        "pdu_enable": (
            "BusPduEnableAccess",
            "BusISignalIPdu",
            "Runtime enable/disable of TX PDU transmission. TX direction only.",
        ),
        "controller_enable": (
            "BusCommunicationControllerEnableAccess",
            "BusCanCommunicationController",
            "Runtime enable/disable of the bus communication controller (CAN or LIN).",
        ),
        "rx_status": (
            "BusPduRxStatusAccess",
            "BusISignalIPdu",
            "Reception status monitoring for RX PDUs. Use BusPduRxStatusInspection in the Inspection part.",
        ),
    }
    feature_name, target_type, description = feature_guides.get(
        feature_type, feature_guides["signal_values"]
    )

    return f"""\
# Add & Configure a Bus Feature: {feature_type}

Goal: add run-time capability to bus configuration elements. Each feature exposes
function ports for model connection.

Selected feature: **{feature_name}** (target element: {target_type})
{description}

{_ENSURE_RUNNING}

## Step 1 — Confirm the target exists
Call `find_bus_config_elements` with element_type="{target_type}",
bus_config_name="{bus_config_name}". If empty, assign ECUs first
(see the `create_bus_configuration` prompt).

## Step 2 — Add the feature
Call `add_feature_to_bus_element` with feature_name="{feature_name}",
element_type="{target_type}", bus_config_name="{bus_config_name}".

### Targeting options
- By name: element_name="EngineData".
- By XPath: element_xpath='//BusISignalIPdu[@Name="EngineData" and @Direction="TX"]'.
- TX only: element_xpath='//BusISignalIPdu[@Direction="TX"]'.

## Step 3 — Configure feature values (when required)
- Feature-node values (Countdown start value, Feature switch, Overwrite value,
  Offset value, manipulation Length) → `set_bus_config_element_property`.
- Communication-matrix values (PDU/signal Length, signal Initial value) → `set_matrix_element_property`.
- Function-port values (IsMappable, IsTestAutomationSupportEnabled, InitialValue) → `set_function_port_property`.

## Verify
Call `find_bus_config_elements` with xpath="//FunctionPort" to inspect the exposed
ports. Do NOT call `generate_bus_containers` just to make ports visible.

The full feature catalog is in the `configurationdesk://reference/features` resource.
"""


@mcp.prompt(
    name="add_behavior_model",
    description="Single task: add a behavior model (.slx/.mdl/.sic/.bsc), analyze it, and expose its ports in the signal chain",
)
def add_behavior_model(
    model_path: str = "D:/Models/plant_model.slx",
    model_name: str = "plant_model",
) -> str:
    return f"""\
# Add a Behavior Model

Goal: bring a plant/controller model into the application so its ports can be
wired to bus or I/O function ports.

{_ENSURE_RUNNING}

## Step 1 — Add the model
Call `add_model` with path="{model_path}".
- .slx / .mdl — Simulink (analysis required).
- .sic — Simulink implementation container.
- .bsc — Bus Simulation Container.

## Step 2 — Analyze (Simulink only)
Call `analyze_models` to detect input/output ports and create model port blocks.
Skip for .sic/.bsc (already analyzed).

## Step 3 — Inspect
- `list_models` — confirm the model and its analysis state.
- `list_model_ports` with model_name="{model_name}" — the available model ports.

## Step 4 — Expose ports in the signal chain
- All ports → `add_model_to_signal_chain` with model_name="{model_name}".
- One port → `add_model_port_to_signal_chain` with model_name="{model_name}" and the exact port_name.
"""


@mcp.prompt(
    name="create_application_process",
    description="Single task: create an application process (default periodic task), optionally assigned to bus configurations or a specific model",
)
def create_application_process(
    process_name: str = "Restbus_ApplicationProcess",
    bus_config_name: str = "CAN_Restbus",
) -> str:
    return f"""\
# Create an Application Process

Goal: provide execution scheduling — mirrors the UI command
'New → Application Process (Providing Default Task)'.

{_ENSURE_RUNNING}

## Prerequisite
A ProcessingUnitApplication must exist: register a hardware platform
(`add_hardware_platform`) or, for VEOS/no-hardware, call `add_application_processing_unit`.

## Step 1 — Create the process (default periodic task)
Call `create_application_process` with name="{process_name}". This sets
'Provide default task' = true, so a periodic default task with a resolved runnable
function is created automatically.

## Bus-config assignment
- Omit `bus_config_names` → assigned to ALL existing bus configurations.
- Scope it → pass bus_config_names=["{bus_config_name}"].
- Skip assignment → pass an empty list [].

## Model-driven alternative
For a process pre-configured for ONE behavior model, call
`create_preconfigured_application_process` with model_name="<model>" instead.
"""


@mcp.prompt(
    name="connect_model_ports",
    description="Single task: wire bus/I/O function ports to behavior-model ports (automatic name matching or a specific pair)",
)
def connect_model_ports(
    model_name: str = "plant_model",
    bus_config_name: str = "CAN_Restbus",
) -> str:
    return f"""\
# Connect Model Ports

Goal: establish the data flow between function ports (bus or analog/digital I/O)
and the behavior model's ports in the signal chain.

{_ENSURE_RUNNING}

## Prerequisite
- The model's ports are in the signal chain (see `add_behavior_model`).
- Function blocks/ports exist (bus features or I/O function blocks).
- An application process exists (see `create_application_process`).

## Step 1 — Make bus function ports mappable (if needed)
Call `set_function_port_property` with property_name="IsMappable", value=true,
bus_config_name="{bus_config_name}". When exact ports are named, prefer `port_xpath`
over the coarse `feature_type` selector. If this fails, re-run
`find_bus_config_elements` to verify the actual port names/XPath — do NOT use
`generate_bus_containers` as recovery.

## Step 2 — Auto-connect by name (recommended)
Call `auto_connect_matching_io_function_blocks_to_model_ports` to match function
ports to model ports by name across the project.

## Step 3 — Connect a specific pair
1. `list_model_ports` with model_name="{model_name}" for exact names.
2. `connect_function_block_port_to_model_port` with function_block_name="...",
   function_block_port_name="...", model_name="{model_name}", model_port_name="...".

## Verify
Call `check_conflicts` to confirm nothing is left unconnected.
"""


@mcp.prompt(
    name="check_and_resolve_conflicts",
    description="Single task: run the conflict check and apply the common fixes before generating containers or building",
)
def check_and_resolve_conflicts() -> str:
    return f"""\
# Check & Resolve Conflicts

Goal: surface configuration issues and fix them before container generation or build.

{_ENSURE_RUNNING}

## Step 1 — Check
Call `check_conflicts`. It returns each conflict with its name, context, property,
current value, suggested values, and effect.

## Step 2 — Apply the common fixes
- "No hardware assigned" → `assign_hardware_automatically` (or `auto_assign_channel_set`).
- "Baud rate mismatch" → `set_io_function_block_property` with property_name="BaudRate".
- "Port not mappable" → `set_function_port_property` with property_name="IsMappable", value=true.
- "Model analysis required" → `analyze_models`.
- "Bus access not assigned" → `assign_bus_access`.
- "Bus containers outdated" → call `generate_bus_containers` only if the user asked for BSC/container output.

## Step 3 — Re-check
Call `check_conflicts` again and repeat until clean.
"""


@mcp.prompt(
    name="build_application",
    description="Single task: verify conflicts and build the real-time application, optionally downloading and starting it",
)
def build_application(
    download: str = "true",
    start: str = "true",
) -> str:
    return f"""\
# Build the Real-Time Application

Goal: compile the application into a real-time application (.rta) and optionally
download and start it.

{_ENSURE_RUNNING}

## Step 1 — Check for conflicts first
Call `check_conflicts`; resolve any reported issues (see the
`check_and_resolve_conflicts` prompt).

## Step 2 — Regenerate containers if the bus config changed
Call `generate_bus_containers` only if a bus configuration changed since the last
generate AND container/BSC output is required.

## Step 3 — Build
Call `build_application` with:
- download={download} → download to hardware (set false for offline builds).
- start={start} → start the application after download.
- unload=true → unload any previously loaded application first.
NOTE: `build_application` accepts ONLY download, start, and unload — there is no
build_model or target_architecture argument.

## Step 4 — Get the result
Call `get_build_result` to retrieve the build output directory (contains the .rta).
"""


@mcp.prompt(
    name="register_hardware",
    description="Single task: provide the hardware topology — register a SCALEXIO/MicroAutoBox III/MicroLabBox II platform, import an .htfx file, or add a VEOS processing unit",
)
def register_hardware(
    platform_type: str = "SCALEXIO",
    platform_ip: str = "192.000.000.1",
) -> str:
    return f"""\
# Register Hardware

Goal: provide the hardware topology that bus and I/O function blocks are assigned to.

{_ENSURE_RUNNING}

## Choose an approach (ASK the user which applies)

### Option A — Physical platform
Call `add_hardware_platform` with ip_addresses=["{platform_ip}"], platform_type="{platform_type}".
Valid types: "SCALEXIO", "MicroAutoBox III", "MicroLabBox II".
Returns the unique platform name used by later hardware operations.

### Option B — Import a topology file
Call `import_hardware_topology` with path="C:/HW/topology.htfx".

### Option C — VEOS / no hardware
Call `add_application_processing_unit`. VEOS is NOT a platform — do NOT call
`add_hardware_platform` for it. The deliverable is the generated BSC.

## Verify / maintain
- `list_platforms` — confirm the registered hardware and its I/O boards.
- `refresh_platforms` — refresh platform information.
- `scan_hardware` with platform_name="..." — re-scan after boards changed.
"""


@mcp.prompt(
    name="add_io_function",
    description="Single task: add an analog/digital I/O function block (Voltage/PWM/Digital) from the I/O Functions Library and connect it to the model",
)
def add_io_function(
    function_type: str = "Voltage Out",
    block_name: str = "Voltage1",
    model_name: str = "plant_model",
) -> str:
    return f"""\
# Add an Analog/Digital I/O Function

Goal: add I/O Functions Library blocks (Voltage In/Out, PWM, Digital) to the signal
chain. This is for ELECTRICAL I/O — NOT for CAN/LIN/Ethernet buses (use bus tools
for those).

{_ENSURE_RUNNING}

## Step 1 — Discover available types
Call `list_io_function_block_types` to enumerate valid function_type_name values
(e.g. 'Voltage Out', 'Voltage In', 'PWM Out', 'Digital In').

## Step 2 — Add the function block
Call `add_io_function_block` with function_type_name="{function_type}", block_name="{block_name}".

## Step 3 — Connect it to the model
- Single pair: `connect_function_block_port_to_model_port` with function_block_name="{block_name}",
  function_block_port_name="Voltage", model_name="{model_name}", model_port_name="..."
  (use `list_model_ports` for the exact model port name).
- Bulk by name: `auto_connect_matching_io_function_blocks_to_model_ports`.

## Step 4 — Assign hardware resources
Call `assign_hardware_automatically` (all blocks) or `auto_assign_channel_set`
(per block), then `check_conflicts`.
"""


@mcp.prompt(
    name="assign_bus_hardware",
    description="Single task: connect a bus configuration to physical channels — create a CAN/LIN I/O function block, set its baud rate, assign bus access requests, and assign a hardware channel",
)
def assign_bus_hardware(
    bus_type: str = "CAN",
    baud_rate: str = "500000",
    function_block_name: str = "CAN_Channel1",
) -> str:
    return f"""\
# Assign Bus Hardware

Goal: link a bus configuration's access requests to a physical hardware channel.
This is the CAN/LIN/Ethernet path — for analog/digital I/O use the `add_io_function` prompt.

{_ENSURE_RUNNING}

## Prerequisite
- A bus configuration with assigned ECUs (see `create_bus_configuration`).
- Hardware present: `add_hardware_platform` / `import_hardware_topology`, or
  `add_application_processing_unit` for VEOS (then skip channel assignment).

## Step 1 — Inspect what needs hardware
Call `list_bus_access_requests` — each cluster/part generates one request to assign.

## Step 2 — Create the bus I/O function block
Call `create_io_function_block` with name="{function_block_name}", bus_type="{bus_type}".
Create ONE function block per physical bus channel (cluster).
(NOT `create_bus_configuration` — that creates the simulation setup, not hardware.)

## Step 3 — Set the baud rate
Call `set_io_function_block_property` with function_block_name="{function_block_name}",
property_name="BaudRate", value="{baud_rate}".
- CAN: 500000   - LIN: 19200   - CAN-FD: also set "DataPhaseBaudRate" to "2000000" or "4000000".
Use `list_io_function_block_properties` to discover all settable properties.

## Step 4 — Assign bus access requests
Call `assign_bus_access` with function_block_name="{function_block_name}"
(optionally scope with bus_config_name / cluster_name).

## Step 5 — Assign a hardware channel
- Automatic (recommended): `auto_assign_channel_set` with function_block_name="{function_block_name}".
- Manual: `list_assignable_channel_sets` then `assign_channel_set` with the chosen channel_set_index.
- All function blocks at once: `assign_hardware_automatically`.

## Verify
Call `check_conflicts` to confirm no hardware assignment conflicts remain.
"""


@mcp.prompt(
    name="configure_inspection_manipulation",
    description="Single task: set up the Inspection (monitor RX) and Manipulation (override TX) parts of a bus configuration, including the manipulation feature-node properties",
)
def configure_inspection_manipulation(
    bus_config_name: str = "CAN_Config",
) -> str:
    return f"""\
# Configure Inspection & Manipulation

Goal: go beyond restbus simulation — monitor received traffic (Inspection) and
override transmitted traffic (Manipulation).

{_ENSURE_RUNNING}

## Prerequisite
A bus configuration exists and a matrix is loaded (see `create_bus_configuration`).

## Inspection — monitor RX traffic
1. Assign ECUs to the Inspection part:
   `assign_ecu_to_bus_config` with bus_config_name="{bus_config_name}", ecu_xpath="//BusEcu", part="inspection".
2. Read received signal values:
   `add_feature_to_bus_element` with feature_name="BusISignalValueAccess",
   element_type="BusISignal", bus_config_name="{bus_config_name}".
3. Reception status (Inspection-specific feature name):
   `add_feature_to_bus_element` with feature_name="BusPduRxStatusInspection",
   element_xpath='/BusConfiguration[@Name="{bus_config_name}"]/BusConfigurationPartInspection//BusISignalIPdu'.

## Manipulation — override TX traffic
1. Assign ECUs to the Manipulation part:
   `assign_ecu_to_bus_config` with bus_config_name="{bus_config_name}", ecu_xpath="//BusEcu", part="manipulation".
2. Enable/disable TX PDUs at runtime:
   `add_feature_to_bus_element` with feature_name="BusPduEnableAccess",
   element_xpath='/BusConfiguration[@Name="{bus_config_name}"]/BusConfigurationPartManipulation//BusISignalIPdu[@Direction="TX"]'.
3. Configure manipulation feature-node values with `set_bus_config_element_property`:
   `Countdown start value`, `Feature switch`, `Overwrite value`, `Offset value`, manipulation `Length`.

## Matrix edits (when required)
If a step changes the communication matrix itself, use `set_matrix_element_property`
for PDU/signal `Length` or signal `Initial value`.

## Verify
Call `find_bus_config_elements` with xpath="//FunctionPort" to inspect the exposed ports.
The full feature catalog is in the `configurationdesk://reference/features` resource.
"""


@mcp.prompt(
    name="inspect_configuration",
    description="Single task (read-only): overview of the active application — status, configuration tree, and inventory of models, matrices, bus configs, and hardware",
)
def inspect_configuration() -> str:
    return f"""\
# Inspect the Configuration (read-only)

Goal: build a complete, read-only picture of the active application. Safe to run
at any time to understand the current state.

{_ENSURE_RUNNING}

## Status
Call `get_application_status` — project name, project root, and active application.

## Configuration tree
Call `list_configuration` — executable applications, processing units, tasks, events.

## Inventory
- `list_applications` — applications in the project.
- `list_models` — loaded behavior models and analysis state.
- `list_matrices` — communication matrices, clusters, and ECUs.
- `list_bus_configurations` — bus configurations and their parts.
- `list_platforms` — registered hardware.
- `list_bus_access_requests` — requests awaiting hardware assignment.

## Drill down
- `find_matrix_elements` with an XPath (e.g. "//BusEcu") for matrix elements.
- `find_bus_config_elements` with an XPath (e.g. "//FunctionPort") for bus config elements.
See the `configurationdesk://reference/xpath` resource for ready-made patterns.
"""
