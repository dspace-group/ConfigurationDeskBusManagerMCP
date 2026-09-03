# -*- coding: utf-8 -*-
"""The single end-to-end use-case prompt for the ConfigurationDesk MCP Server.

Per the repository prompt strategy, exactly ONE prompt describes a complete
end-to-end use case. Every other prompt (see ``individual_setup_prompts``) is a
focused, single-task prompt for one commonly used tool.

The end-to-end use case is the Bus Manager **restbus simulation** flow — the
flagship scenario for this server: load a communication matrix, build a restbus
configuration, add the signal-value feature, wire a behavior model, resolve
conflicts, and produce the deliverable (real-time build or bus simulation
container).
"""

from sources.server.app import mcp


@mcp.prompt(
    name="bus_manager_restbus_simulation",
    description="End-to-end use case: build a Bus Manager restbus simulation from a communication matrix — matrix, restbus configuration, signal feature, behavior model, conflict resolution, and build/BSC output",
)
def bus_manager_restbus_simulation(
    matrix_path: str = "D:/Databases/vehicle_can.arxml",
    bus_config_name: str = "CAN_Restbus",
    dut_ecu_name: str = "ECU_under_Test",
    model_path: str = "D:/Models/Restbus_Model_64-bit.sic",
    deliverable: str = "bsc",
) -> str:
    return f"""\
# End-to-End Use Case: Bus Manager Restbus Simulation

Simulate every ECU on a network EXCEPT the device(s) under test ("{dut_ecu_name}"),
exchange the simulated signals with a behavior model, and produce the deliverable.
This mirrors the dSPACE Bus Manager restbus workflow.

## Failure policy
If any step fails, STOP, explain the failure in plain language, and ask the user
whether to continue. Do NOT silently skip a failed step or invent an alternate path.

## Step 0 — Ensure ConfigurationDesk is running
If ConfigurationDesk is not already running, call `start_configurationdesk`
(visible=true). It is idempotent — safe to call if it is already up. Confirm a
project with an ACTIVE application exists with `get_application_status`; if not,
create one (`set_project_root` → `create_project` → `add_application`).

## Step 1 — Load the communication matrix
Call `add_communication_matrix` with path="{matrix_path}"
(.arxml / .dbc / .ldf). Then `list_matrices` to review clusters and ECUs.

## Step 2 — Create the bus configuration
Call `create_bus_configuration` with name="{bus_config_name}".
(NOT `create_io_function_block` — that creates hardware I/O blocks.)

## Step 3 — Assign the restbus (all ECUs except the DUT)
Call `assign_ecu_to_bus_config` with bus_config_name="{bus_config_name}",
ecu_xpath="//BusEcu", exclude_list="{dut_ecu_name}", part="simulated".

If the user instead names EXACT PDUs or signals, keep that scope literal: use
`assign_matrix_to_bus_config` with a precise `matrix_xpath`. Do NOT widen to a
whole-ECU assignment unless whole-ECU population was explicitly requested.

## Step 4 — Add the signal-value feature (most common)
Call `add_feature_to_bus_element` with feature_name="BusISignalValueAccess",
element_type="BusISignal", bus_config_name="{bus_config_name}".
This exposes function ports: In ports for TX signals, Out ports for RX signals.
For other features, see the `configurationdesk://reference/features` resource.

## Step 5 — Add the behavior model
Call `add_model` with path="{model_path}".
For .slx/.mdl also call `analyze_models`; .sic/.bsc are already analyzed.
Then `add_model_to_signal_chain` to expose the model ports.

## Step 6 — Provide scheduling
A processing unit application must exist. For real hardware, register a platform with
`add_hardware_platform`; for a VEOS/no-hardware build, call `add_processing_unit_application`.
Then `create_application_process` (auto-assigned to "{bus_config_name}").

## Step 7 — Connect the ports
Call `auto_connect_matching_io_function_blocks_to_model_ports` to wire matching
function ports to model ports by name.

## Step 8 — Resolve conflicts
Call `check_conflicts` and fix any reported issues before producing the deliverable
(see the `check_and_resolve_conflicts` prompt for the common fixes).

## Step 9 — Produce the deliverable
- deliverable="bsc" (VEOS / offline): call `generate_bus_containers`, then
  `find_bus_config_elements` with xpath="//FunctionPort" to confirm the packaged
  interface. The BSC packages the existing function ports; it does not create them.
- deliverable="rta" (real hardware): assign bus hardware
  (`create_io_function_block` → `set_io_function_block_property` BaudRate →
  `assign_bus_access` → `auto_assign_channel_set`), then `build_application`
  (download=true, start=true, unload=true) and `get_build_result`.

Selected deliverable: **{deliverable}**.
"""
