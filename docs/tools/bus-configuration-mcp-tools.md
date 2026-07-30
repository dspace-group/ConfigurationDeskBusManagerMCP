# Bus Configuration Tools

**Domain:** Restbus simulation, inspection, manipulation, features, and exposed
function ports

Use this domain after a communication matrix is loaded. A bus configuration can
contain simulated ECUs, inspection elements, manipulation elements, and gateway
behavior.

## Tool Contract

| Tool | Purpose | Safety notes |
|---|---|---|
| `create_bus_configuration` | Create an empty bus configuration. | Use this for simulation setup, not I/O blocks. |
| `remove_bus_configuration` | Remove configurations by name or pattern. | Destructive. |
| `list_bus_configurations` | List bus configurations. | Read-only. |
| `assign_matrix_to_bus_config` | Assign a cluster, ECU, PDU, or signal by name or XPath. | Keep an explicitly named PDU/signal scope literal. |
| `assign_ecu_to_bus_config` | Assign whole ECUs for a selected part. | Use for whole-ECU restbus scope. |
| `add_feature_to_bus_element` | Add an access or behavior feature to selected elements. | Features can expose function ports. |
| `remove_bus_config_elements` | Remove assigned elements by name, type, or XPath. | Destructive. |
| `generate_bus_containers` | Generate BSC output. | Call only for explicit container or BSC delivery. |
| `find_bus_config_elements` | Find elements and exposed ports by name, type, or XPath. | Read-only; paginated. |
| `assign_bus_config_to_application_process` | Associate a bus configuration with an application process. | Requires an application process. |
| `set_function_port_property` | Change function-port properties. | Use the precise port XPath when scope is ambiguous. |
| `set_bus_config_element_property` | Change feature-node or bus-element properties. | Use for countdown, overwrite, offset, length, or feature values. |

`find_bus_config_elements` accepts `offset` and `limit`; refer to the shared
[pagination contract](README.md#pagination) for defaults and response metadata.

## Assignment Rules

- Use `assign_ecu_to_bus_config` when the requested scope is an entire ECU.
- Use `assign_matrix_to_bus_config` when the requested scope is a named cluster,
	PDU, or signal.
- Use `matrix_xpath` or element XPath for repeated names and deliberate exact
	targeting.
- Use `part` to select `simulated`, `inspection`, or `manipulation` behavior.

## Property Boundaries

| Need | Tool |
|---|---|
| Feature-node or bus-element value | `set_bus_config_element_property` |
| Matrix database value | `set_matrix_element_property` |
| Exposed function-port value | `set_function_port_property` |
| Hardware I/O setting | `set_io_function_block_property` |

## Typical Workflow

1. Create a bus configuration.
2. Assign whole ECUs or exact matrix elements.
3. Add required features.
4. Inspect exposed elements and function ports with `find_bus_config_elements`.
5. Configure properties with the appropriate property tool.
6. Associate an application process and resolve conflicts.
7. Generate BSC output only when explicitly requested.

## Related Guides

- [Communication Matrix](communication-matrix-mcp-tools.md)
- [Bus Access](bus-access-mcp-tools.md)
- `configurationdesk://reference/features`
- `configurationdesk://reference/bus-element-properties`
