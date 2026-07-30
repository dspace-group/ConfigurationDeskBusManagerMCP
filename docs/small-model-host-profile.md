# Small-Model Host Profile

Use this profile in the MCP host's workspace, project, or server-scoped
instructions when ConfigurationDesk MCP is available. It is host guidance, not
an MCP server contract: the live tool schemas and tool results remain
authoritative.

## Operating Rules

1. Call `start_configurationdesk` before a domain tool. If startup fails, call
   `diagnose_connection` once, inspect its result, and do not blindly retry.
2. For a multi-step task, use the closest existing workflow prompt before
   assembling an ad hoc tool sequence.
3. Do not invent project names, application names, model ports, matrix paths,
   XPath expressions, hardware addresses, or channel indexes. Use a list or
   find tool when an identifier is unknown.
4. Stop when a tool returns `success=false`. Treat `verified=false` as
   unconfirmed. Do not retry when `retryable=false`; follow `next_action` and
   `recovery_hint`.
5. Before a build, run `check_conflicts`. For an offline build, explicitly set
   `download=false` and `start=false`.

## Routing Rules

- A bus simulation/restbus setup uses `create_bus_configuration`; a physical
  CAN, LIN, or Ethernet channel uses `create_io_function_block`.
- For an application inside a project, use `add_application` after creating or
  opening the project. Use `create_application_process` only for execution
  scheduling, a periodic task, or a process for a model.
- Assign whole ECUs with `assign_ecu_to_bus_config`. Assign an exact cluster,
  PDU, or signal with `assign_matrix_to_bus_config`; never widen an exact
  PDU/signal request to whole-ECU scope.
- Set a communication-matrix value with `set_matrix_element_property`, a bus
  feature or bus-element value with `set_bus_config_element_property`, an
  exposed function-port value with `set_function_port_property`, and a
  hardware I/O value with `set_io_function_block_property`.
- Use `add_hardware_platform` only for physical SCALEXIO, MicroAutoBox III, or
  MicroLabBox II hardware with an address. Use `import_hardware_topology` for
  an `.htfx` file. Use `add_application_processing_unit` for VEOS or a
  no-hardware workflow.
- Use `add_model_to_signal_chain` for every port of one model and
  `add_model_port_to_signal_chain` only for a named port. Use
  `create_preconfigured_application_process` only when one specific model is
  named; otherwise use `create_application_process`.
- Use `create_io_function_block` for CAN, LIN, or Ethernet hardware channels.
  Use `add_io_function_block` for analog or digital functions such as Voltage,
  PWM, or Digital I/O.
- Use `assign_channel_set` after reviewing a specific returned channel index.
  Use `auto_assign_channel_set` for one function block or
  `assign_hardware_automatically` for all eligible function blocks.
- Use `auto_connect_matching_io_function_blocks_to_model_ports` for bulk
  name-matched connections. Use `connect_function_block_port_to_model_port`
  for one explicit function-block/model-port pair.

## Discovery and Validation Rules

- Use `list_matrices` to enumerate loaded clusters and ECUs. Use
  `find_matrix_elements` to locate a specific cluster, ECU, PDU, frame, or
  signal. Continue with the returned offset when results are paginated.
- Use `list_bus_configurations` for top-level configuration names. Use
  `find_bus_config_elements` to inspect elements or exposed ports inside a
  selected configuration.
- Use `list_configuration` to inspect processing units, application processes,
  tasks, and events before changing them.
- Use `analyze_models` to discover model interfaces and ports. Use
  `check_conflicts` to validate the configured application before a build or
  hardware download; neither tool substitutes for the other.
- Use `build_application` only to start a build. Use `get_build_result` only
  to inspect the latest output after a successful build; it does not prove a
  failed or canceled build succeeded.

## Safety Boundaries

- Confirm exact names and scope before destructive tools, including removals
  and clear-all operations. Use the owner-specific removal tool: a project
  uses `remove_project`, an application uses `remove_application`, a model uses
  `remove_model`, a bus configuration uses `remove_bus_configuration`, and
  bus elements use `remove_bus_config_elements`.
- Generate BSC output with `generate_bus_containers` only when the user
  explicitly requests containers or BSC delivery.
- After an unverified removal or a canceled build, inspect current state and
  ask the user before continuing.

## Host Adoption

Inject this profile only for ConfigurationDesk requests or whenever the
ConfigurationDesk MCP server is available. Do not apply it to unrelated tasks.
For a complete copy-and-adapt request catalog, see
[Tool-to-Prompt Map](prompts/tool-map.md).
