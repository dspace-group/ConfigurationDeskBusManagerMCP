# Tool-to-Prompt Map

This map gives every tool a discoverable starting point without duplicating its runtime JSON schema. Each row includes a short copy-and-adapt request that shows how a user can ask an MCP host for that outcome. Use the linked domain guide for the tool contract and invoke the named prompt when a guided workflow is useful.

Example requests are natural-language seeds, not literal JSON payloads. The live MCP schema remains authoritative for required fields, defaults, and valid values.

The table is checked by `ConfigurationDeskMCP/tests/test_prompt_tool_map.py` so it must contain every registered tool exactly once.

## Bootstrap and Lifecycle

| Tool | Domain | Start with | Example request |
| --- | --- | --- | --- |
| `start_configurationdesk` | Application lifecycle | [Prompt Examples](README.md#before-you-begin) | Start or attach to ConfigurationDesk, make the window visible, then confirm that it is ready before continuing. |
| `stop_configurationdesk` | Application lifecycle | [Application Lifecycle](../tools/application-lifecycle-mcp-tools.md) | After confirming no more work is needed, save changes and close ConfigurationDesk. |
| `get_application_status` | Application lifecycle | Prompt: `inspect_configuration` | After startup, show the active project location, project, and application before choosing the next workflow. |
| `save_project` | Application lifecycle | [Application Lifecycle](../tools/application-lifecycle-mcp-tools.md) | Save the active ConfigurationDesk project before a backup, close, or other high-impact change. |
| `undo` | Application lifecycle | [Application Lifecycle](../tools/application-lifecycle-mcp-tools.md) | Undo the most recent supported configuration change; do not use this to recover project or file operations. |
| `redo` | Application lifecycle | [Application Lifecycle](../tools/application-lifecycle-mcp-tools.md) | Redo the most recently undone supported configuration change after confirming that reapplying it is intended. |
| `diagnose_connection` | Application lifecycle | [Application Lifecycle](../tools/application-lifecycle-mcp-tools.md) | Startup failed. Diagnose the ConfigurationDesk connection environment once, inspect the result, and do not retry startup blindly. |

## Projects and Applications

| Tool | Domain | Start with | Example request |
| --- | --- | --- | --- |
| `set_project_root` | Project management | Prompt: `create_project` | Set `C:/Projects` as the active project location for projects created or opened in this session. |
| `create_project` | Project management | Prompt: `create_project` | Create new project `VehicleHIL` in `C:/Projects`; do not replace an existing project with that name. |
| `open_project` | Project management | Prompt: `create_project` | List projects in the active project location, then open the existing project named `VehicleHIL`. |
| `close_project` | Project management | [Project Management](../tools/project-management-mcp-tools.md) | Save and close only the active project; do not remove its files. |
| `remove_project` | Project management | [Project Management](../tools/project-management-mcp-tools.md) | Remove only project `ObsoletePrototype` from ConfigurationDesk, keeping its files on disk. |
| `list_projects` | Project management | Prompt: `create_project` | After starting ConfigurationDesk, list the projects available in the active project location. |
| `get_project_path` | Project management | [Project Management](../tools/project-management-mcp-tools.md) | Show the folder of the active project, not the general project location. |
| `backup_project` | Project management | [Project Management](../tools/project-management-mcp-tools.md) | Create a backup archive of the active project in `C:/Backups`, then report the archive path. |
| `open_project_from_backup` | Project management | [Project Management](../tools/project-management-mcp-tools.md) | Restore `C:/Backups/VehicleHIL.zip` as project `VehicleHIL_Restore`; do not overwrite an existing project. |
| `add_application` | Application management | Prompt: `create_project` | In the active project, add and activate a new application named `SimulationApp`. |
| `activate_application` | Application management | [Application Management](../tools/app-management-mcp-tools.md) | List applications in the active project, then activate the existing application `SimulationApp`. |
| `remove_application` | Application management | [Application Management](../tools/app-management-mcp-tools.md) | List applications, then remove only application `ObsoletePrototype`; do not remove the project. |
| `list_applications` | Application management | Prompt: `create_project` | List applications in the active project and identify which application is active before changing it. |
| `list_configuration` | Application configuration | Prompt: `inspect_configuration` | With the intended application active, show its configuration tree before making configuration changes. |

## Communication Matrix and Bus Configuration

| Tool | Domain | Start with | Example request |
| --- | --- | --- | --- |
| `add_communication_matrix` | Communication matrix | Prompt: `load_communication_matrix` | Load `D:/Databases/vehicle_can.arxml`, then list its clusters and ECUs before assigning matrix elements. |
| `remove_communication_matrix` | Communication matrix | [Communication Matrix](../tools/communication-matrix-mcp-tools.md) | Check assignments, then remove only matrix `vehicle_can`; do not force removal unless dependent assignments are intentionally removed. |
| `list_matrices` | Communication matrix | Prompt: `load_communication_matrix` | List loaded matrices by clusters and ECUs; continue with the returned offset if more results are available. |
| `find_matrix_elements` | Communication matrix | Prompt: `load_communication_matrix` | In the ECU hierarchy, find TX PDUs for `ECU_A`; use a precise XPath when repeated names make the scope ambiguous. |
| `set_matrix_element_property` | Communication matrix | [Property Setting Boundary](README.md#property-setting-boundary) | In the loaded matrix, set initial value `0` on the exact signal `EngineSpeed`; do not change a bus-configuration feature or function port. |
| `create_bus_configuration` | Bus configuration | Prompt: `create_bus_configuration` | Create bus configuration `CAN_Restbus`, then verify that the created configuration has that requested name. |
| `remove_bus_configuration` | Bus configuration | [Bus Configuration](../tools/bus-configuration-mcp-tools.md) | Remove only bus configuration `OldRestbus`; do not use a wildcard unless every matching configuration is intended. |
| `list_bus_configurations` | Bus configuration | Prompt: `create_bus_configuration` | List the current bus configurations before selecting one for assignment, property changes, or removal. |
| `assign_matrix_to_bus_config` | Bus configuration | Prompt: `create_bus_configuration` | Assign only PDU `GearboxInfoIPdu` to the manipulation part of `CAN_Restbus`, keeping the exact PDU scope rather than assigning its whole ECU. |
| `assign_ecu_to_bus_config` | Bus configuration | Prompt: `create_bus_configuration` | Assign whole ECUs except `DUT_ECU` to the simulated part of `CAN_Restbus`; do not use this for an exact PDU or signal. |
| `add_feature_to_bus_element` | Bus configuration | Prompt: `add_feature_to_bus_element` | Add exact feature `BusISignalValueAccess` to signal `EngineSpeed` in `CAN_Restbus`, then inspect the exposed function ports. |
| `remove_bus_config_elements` | Bus configuration | [Bus Configuration](../tools/bus-configuration-mcp-tools.md) | Remove only ECU `ECU_A` from `CAN_Restbus`; confirm its type and scope first because its child signals and features are also removed. |
| `generate_bus_containers` | Bus configuration | Prompt: `bus_manager_restbus_simulation` | After configuring the required bus configurations and features, generate BSC output only because container delivery was explicitly requested. |
| `find_bus_config_elements` | Bus configuration | Prompt: `add_feature_to_bus_element` | In `CAN_Restbus`, find exposed function ports; use the returned XPath and next offset for precise property work or additional pages. |
| `assign_bus_config_to_application_process` | Bus configuration | Prompt: `create_application_process` | After creating `RestbusProcess`, assign bus configuration `CAN_Restbus` to that exact application process. |
| `set_function_port_property` | Bus configuration | [Property Setting Boundary](README.md#property-setting-boundary) | On the exposed function port in `CAN_Restbus`, set `IsMappable=true`; use this only for function-port interface properties. |
| `set_bus_config_element_property` | Bus configuration | Prompt: `configure_inspection_manipulation` | In `CAN_Restbus`, set an overwrite value on the exact TX signal `EngineSpeed`; use this for a bus feature, not a matrix value or function port. |

## Models and Signal Chain

| Tool | Domain | Start with | Example request |
| --- | --- | --- | --- |
| `add_model` | Model topology | Prompt: `add_behavior_model` | Add `D:/Models/plant_model.slx` and analyze it so its ports can be configured for connection. |
| `replace_model` | Model topology | [Model Topology](../tools/model-topology-mcp-tools.md) | Replace only model `plant_model` with `D:/Models/plant_v2.slx`, then review affected ports and connections. |
| `remove_model` | Model topology | [Model Topology](../tools/model-topology-mcp-tools.md) | Check connections, then remove only model `obsolete_model`; do not remove other configured models. |
| `analyze_models` | Model topology | Prompt: `add_behavior_model` | Analyze loaded Simulink models before exposing or connecting their ports; skip this for already analyzed SIC or BSC files. |
| `create_application_process` | Model topology | Prompt: `create_application_process` | For the VEOS/no-hardware application, create periodic process `RestbusProcess` and assign only `CAN_Restbus` to it. |
| `list_models` | Model topology | Prompt: `add_behavior_model` | List loaded models and their file paths before selecting one for a process, port exposure, replacement, or removal. |
| `add_model_to_signal_chain` | Model topology | Prompt: `add_behavior_model` | Expose every port of model `plant_model` in the signal chain; use this only when all of its ports are intended. |
| `add_model_port_to_signal_chain` | Model topology | Prompt: `add_behavior_model` | List ports for `plant_model`, then expose only its named port `EngineSpeed` in the signal chain. |
| `list_model_ports` | Model topology | Prompt: `connect_model_ports` | List exact available port names for `plant_model` before exposing one port or creating an explicit connection. |
| `list_io_function_block_types` | I/O functions | Prompt: `add_io_function` | List available analog and digital I/O function block types before choosing one for `ThrottleCommand`. |
| `add_io_function_block` | I/O functions | Prompt: `add_io_function` | Add analog I/O function `Voltage Out` named `ThrottleCommand`; do not use this for a CAN, LIN, or Ethernet bus channel. |
| `connect_function_block_port_to_model_port` | I/O functions | Prompt: `connect_model_ports` | After both endpoints exist, connect `Voltage Out` port `Voltage` to the exact model port `Throttle`. |

## Hardware and Bus Access

| Tool | Domain | Start with | Example request |
| --- | --- | --- | --- |
| `add_hardware_platform` | Hardware management | Prompt: `register_hardware` | For physical SCALEXIO hardware at `192.0.2.10`, register and scan the platform; do not use this for VEOS or an `.htfx` file. |
| `import_hardware_topology` | Hardware management | Prompt: `register_hardware` | Import the existing hardware topology `C:/Hardware/topology.htfx`; use this instead of registering a platform by IP address. |
| `scan_hardware` | Hardware management | Prompt: `register_hardware` | After a physical platform changes, rescan the exact platform name returned by `list_platforms`. |
| `remove_hardware` | Hardware management | [Hardware Management](../tools/hardware-management-mcp-tools.md) | Remove only platform `OldSCALEXIO` from the active project after confirming it is no longer required. |
| `list_platforms` | Hardware management | Prompt: `register_hardware` | List registered physical platforms before choosing one to rescan, modify, or remove. |
| `refresh_platforms` | Hardware management | Prompt: `register_hardware` | Refresh information for registered platforms when their current status must be checked. |
| `add_hardware_element` | Hardware management | [Hardware Management](../tools/hardware-management-mcp-tools.md) | Add the supported hardware element `DS6311` to the active hardware topology only when the required element type is known. |
| `add_processing_unit_application` | Application management | [Application Management](../tools/app-management-mcp-tools.md) | For a VEOS or no-hardware workflow, add a processing unit application; do not register a physical platform. |
| `create_io_function_block` | Bus access | Prompt: `assign_bus_hardware` | After creating `CAN_Restbus`, create physical CAN I/O function block `CAN_Body` for one bus channel. |
| `set_io_function_block_property` | Bus access | Prompt: `assign_bus_hardware` | Set hardware I/O property `BaudRate=500000` on CAN function block `CAN_Body`; do not use a bus-feature property tool. |
| `list_io_function_block_properties` | Bus access | Prompt: `assign_bus_hardware` | List the supported properties and current values of `CAN_Body` before setting an uncertain hardware I/O value. |
| `list_bus_access_requests` | Bus access | Prompt: `assign_bus_hardware` | List bus access requests for `CAN_Restbus`, continuing with the returned offset if more requests are available. |
| `assign_bus_access` | Bus access | Prompt: `assign_bus_hardware` | Assign requests for `CAN_Restbus` and its `CAN_Body` cluster to function block `CAN_Body`, without changing other configurations. |
| `list_assignable_channel_sets` | Bus access | Prompt: `assign_bus_hardware` | On the configured hardware topology, list eligible CAN channel sets for `CAN_Body` before choosing a specific one. |
| `assign_channel_set` | Bus access | Prompt: `assign_bus_hardware` | Assign the reviewed channel-set index `0` to `CAN_Body` when a specific physical channel is required. |
| `auto_assign_channel_set` | Bus access | Prompt: `assign_bus_hardware` | With a registered physical platform, automatically choose an eligible channel set for the single function block `CAN_Body`. |
| `assign_hardware_automatically` | Bus access | Prompt: `assign_bus_hardware` | With the hardware topology reviewed, automatically assign remaining eligible resources to all I/O function blocks. |
| `auto_connect_matching_io_function_blocks_to_model_ports` | Bus access | Prompt: `connect_model_ports` | After the model, process, signal-chain ports, and I/O blocks are ready, connect ports whose names match and inspect the resulting links. |
| `create_preconfigured_application_process` | Bus access | Prompt: `create_application_process` | Create a model-specific preconfigured application process for `plant_model`; use the generic process tool when no model is named. |

## Working Views and Build

| Tool | Domain | Start with | Example request |
| --- | --- | --- | --- |
| `create_working_view` | Working views | [Working Views and Conflicts](../tools/working-view-mcp-tools.md) | Create working view `BrakeSystem` to organize and inspect the related signal-chain connections. |
| `list_working_views` | Working views | [Working Views and Conflicts](../tools/working-view-mcp-tools.md) | List available working views before choosing one to export or remove. |
| `remove_working_view` | Working views | [Working Views and Conflicts](../tools/working-view-mcp-tools.md) | Remove only working view `ObsoleteView`; confirm that removal was verified before taking further cleanup action. |
| `clear_all_working_views` | Working views | [Working Views and Conflicts](../tools/working-view-mcp-tools.md) | List working views, confirm every view is disposable, then clear all removable working views. |
| `export_working_view` | Working views | [Working Views and Conflicts](../tools/working-view-mcp-tools.md) | Export working view `BrakeSystem` to `C:/Exports/BrakeSystem.xml` without changing the view configuration. |
| `check_conflicts` | Working views | Prompt: `check_and_resolve_conflicts` | After configuration changes, inspect every conflict; resolve error-level conflicts and run this check again before building. |
| `build_application` | Build management | Prompt: `build_application` | After conflicts are clear, build without download or start (`download=false`, `start=false`); if the build is canceled, stop and ask the user before rerunning. |
| `get_build_result` | Build management | Prompt: `build_application` | After a successful build, show the latest build-result directory; do not treat a result path as proof that a canceled or failed build succeeded. |

## Related Resources

- `configurationdesk://reference/tool-selection`
- `configurationdesk://reference/valid-values`
- `configurationdesk://reference/error-recovery`
- [Public MCP Tool Reference](../tools/README.md)