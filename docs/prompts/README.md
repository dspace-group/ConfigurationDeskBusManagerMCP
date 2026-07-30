# Prompt Examples

The server exposes 15 MCP prompts. Prompts are outcome-oriented templates that
help an MCP host select and sequence tools; they do not replace the runtime tool
schemas. Use the prompt list in your MCP host to invoke one, then provide the
parameters requested by that host.

## Before You Begin

- Use 64-bit Windows with a licensed local ConfigurationDesk installation for
  automation calls.
- Call `start_configurationdesk` before a project workflow.
- Create or open a project and activate an application before matrix, model,
  hardware, bus, or build work.
- Stop when a tool returns `success=false`. Read `error_code`, `recovery_hint`,
  and `next_action` before proceeding.

## Prompt Coverage

| Prompt | Main outcome | Main tool domains |
|---|---|---|
| `bus_manager_restbus_simulation` | Complete restbus simulation workflow | Project, matrix, bus configuration, model, hardware, build |
| `create_project` | Create or open a project and activate an application | Lifecycle, project, application |
| `load_communication_matrix` | Import and inspect ARXML/DBC/LDF data | Matrix |
| `create_bus_configuration` | Create a restbus, inspection, or manipulation configuration | Bus configuration |
| `add_feature_to_bus_element` | Add a signal, PDU, frame, or controller feature | Bus configuration |
| `add_behavior_model` | Add, analyze, and expose a behavior model | Model topology |
| `create_application_process` | Create scheduling for a workflow | Model topology, hardware |
| `connect_model_ports` | Connect model ports and function ports | Model topology, bus access |
| `check_and_resolve_conflicts` | Inspect and resolve configuration conflicts | Working views, bus access, hardware |
| `build_application` | Run a conflict-checked build | Build management |
| `register_hardware` | Choose physical, imported, or no-hardware topology | Hardware management |
| `add_io_function` | Add analog or digital I/O functions | I/O functions |
| `assign_bus_hardware` | Assign bus access and channel sets | Bus access, hardware |
| `configure_inspection_manipulation` | Configure inspection or manipulation scope | Bus configuration |
| `inspect_configuration` | Inspect current project configuration | Lifecycle, configuration, matrix, bus |

Together, these prompts cover the major user outcomes and every public tool
domain. Use the [Public MCP Tool Reference](../tools/README.md) for exact input
schemas and annotations.

## Tool-to-Prompt Map

For a compact entry point for every registered tool, see the
[Tool-to-Prompt Map](tool-map.md). It lists all 77 tools exactly once with the
closest prompt or domain guide and a short copy-and-adapt example request. The
map is checked by the test suite so it stays aligned with the live MCP registry.

## Featured End-to-End Request

Use `bus_manager_restbus_simulation` when the request is a complete restbus
workflow. A host can adapt this user request to the prompt parameters:

```text
Create a CAN restbus simulation from D:/Databases/vehicle_can.arxml.
Exclude ECU_under_Test, name the configuration CAN_Restbus, connect
D:/Models/Restbus_Model.sic, and generate BSC output without downloading to
physical hardware.
```

## Copy and Adapt Requests

### Model and Signal-Chain Setup

```text
Add D:/Models/plant_model.slx, analyze it, expose all model ports, create an
application process, and connect matching function ports. Stop if conflicts
remain.
```

Use `add_behavior_model`, `create_application_process`, and
`connect_model_ports`.

### Physical Bus Hardware Assignment

```text
Register a SCALEXIO platform at 192.0.2.10, create a CAN I/O function block for
CAN_Body, set its baud rate to 500000, assign its bus access, choose an eligible
channel set, and report conflicts before building.
```

Use `register_hardware` and `assign_bus_hardware`. Replace the documentation
address with the real platform address only at runtime.

### Inspection and Manipulation

```text
For bus configuration CAN_Restbus, configure inspection for received PDUs and
manipulation for the exact TX signal named EngineSpeed. Keep the signal scope
literal and show the exposed function ports afterward.
```

Use `configure_inspection_manipulation`. When a user names an exact PDU or
signal, do not widen the operation to whole-ECU assignment.

### Property Setting Boundary

```text
I need to update a signal's initial value, set an overwrite value on a bus
feature, and make the exposed function port mappable. Keep the exact signal and
PDU scope and tell me which property tool applies to each change before making
the update.
```

Choose the property tool by ownership:

- Matrix database value: `set_matrix_element_property`.
- Bus feature or manipulation value: `set_bus_config_element_property`.
- Exposed function-port value: `set_function_port_property`.
- Hardware I/O block setting: `set_io_function_block_property`.

Use `configurationdesk://reference/valid-values`,
`configurationdesk://reference/bus-element-properties`, and
`configurationdesk://reference/function-port-properties` when the property name
or value type is uncertain.

### Conflict Check and Build

```text
Check this application for configuration conflicts. Stop and explain every
error-level conflict. If none remain, build without downloading to hardware and
return the build result directory.
```

Use `check_and_resolve_conflicts` first, then `build_application` with the
runtime schema's `download=false` option. Do not retry a failed build until the
returned error and current configuration state have been reviewed. A canceled
build requires an explicit user decision before it is run again.

### Destructive Cleanup

```text
List the projects and applications first. Remove only the application named
ObsoletePrototype, then verify that the intended application remains active.
Do not delete project files.
```

Use read-only discovery tools before `remove_application`, `remove_project`,
`remove_model`, `remove_hardware`, or other destructive tools. Confirm exact
names and scope before calling a destructive operation.

## Safety Rules

- Ask which hardware-topology approach applies when the workflow could use
  physical hardware, an imported topology, or a no-hardware path.
- Run `check_conflicts` before building or downloading to hardware.
- Generate bus containers only when BSC or container output is explicitly
  requested.
- Treat destructive tools as confirmation-worthy even when a prompt recommends
  a workflow.

## Related Resources

- `configurationdesk://reference/tool-selection`
- `configurationdesk://reference/valid-values`
- `configurationdesk://reference/error-recovery`
- `configurationdesk://reference/xpath`
- `configurationdesk://reference/features`
- [MCP Inspector](../mcp-inspector.md)
