# Communication Matrix Tools

**Domain:** Communication matrix management

Use this domain to import a network definition, inspect clusters, ECUs, PDUs,
frames, and signals, and make controlled edits to writable matrix properties.

## Supported File Types

| Format | Extension |
|---|---|
| AUTOSAR system description | `.arxml` |
| CAN database | `.dbc` |
| LIN description | `.ldf` |

## Tool Contract

| Tool | Purpose | Safety notes |
|---|---|---|
| `add_communication_matrix` | Import a matrix file. | Requires an active application. |
| `remove_communication_matrix` | Remove a loaded matrix. | Destructive; `force=true` can remove assignments that depend on it. |
| `list_matrices` | List loaded clusters and ECUs. | Read-only; paginated independently for clusters and ECUs. |
| `find_matrix_elements` | Find elements by friendly type, name, or XPath. | Read-only; paginated; prefer `cluster`, `ecu`, `pdu`, `frame`, or `signal`. |
| `set_matrix_element_property` | Change writable matrix-level properties. | Use a precise XPath for duplicate names or deliberate bulk edits. |

Both read tools accept `offset` and `limit`; refer to the shared
[pagination contract](README.md#pagination) for defaults and response metadata.

## Typical Workflow

1. Call `add_communication_matrix` with the supplied file path.
2. Call `list_matrices` to discover clusters and ECUs.
3. Call `find_matrix_elements` before assigning exact elements to a bus
	configuration.
4. Use `set_matrix_element_property` only for matrix-level values such as signal
	initial values or PDU/signal length.

Use `set_bus_config_element_property` for bus-configuration feature values and
`set_function_port_property` for exposed function-port values.

## Related Guides

- [Bus Configuration](bus-configuration-mcp-tools.md)
- [Prompt Examples](../prompts/README.md)
- `configurationdesk://reference/xpath`
- `configurationdesk://reference/valid-values`
