# Bus Access Tools

**Domain:** Bus I/O function blocks, bus access, and channel assignment

Use this domain after confirming that a bus configuration exists and when a workflow needs to
connect bus communication to physical hardware channels or model ports.

## Tool Contract

| Tool | Purpose | Safety notes |
|---|---|---|
| `create_io_function_block` | Create a CAN, LIN, or Ethernet bus I/O function block. | This is not a bus-configuration tool. |
| `set_io_function_block_property` | Set a property such as a baud rate. | Use `list_io_function_block_properties` first when values are uncertain. |
| `list_io_function_block_properties` | List configurable I/O block properties and values. | Read-only. |
| `list_bus_access_requests` | List unassigned or assigned bus access requests. | Read-only; paginated. |
| `assign_bus_access` | Link bus access requests to an I/O function block. | Scope to a bus configuration or cluster when needed. |
| `list_assignable_channel_sets` | List channel sets that can be assigned to a function block. | Read-only. |
| `assign_channel_set` | Assign a channel set by its returned index. | Changes the hardware mapping. |
| `auto_assign_channel_set` | Choose an eligible channel set automatically. | Requires a registered physical platform. |
| `assign_hardware_automatically` | Assign remaining eligible hardware resources. | Changes multiple assignments. |
| `auto_connect_matching_io_function_blocks_to_model_ports` | Connect matching I/O and model ports by name. | Ensure the model and application process are ready first. |
| `create_preconfigured_application_process` | Create a model-specific application process. | Use when the workflow names one behavior model. |

`list_bus_access_requests` accepts `offset` and `limit`; see the shared
[pagination contract](README.md#pagination) for defaults and response metadata.

## Typical Bus Hardware Sequence

1. Create a bus configuration and assign matrix elements or ECUs.
2. Create an I/O function block for the intended bus channel.
3. Set required properties, such as `BaudRate`.
4. List bus access requests and assign them to the I/O function block.
5. List eligible channel sets, then assign one manually or automatically.
6. Call `check_conflicts`.
7. Connect model ports when a behavior model participates in the workflow.

## Important Boundaries

- `create_io_function_block` creates hardware-facing I/O blocks; use
	`create_bus_configuration` for a bus simulation configuration.
- Use `set_io_function_block_property` for hardware I/O settings, not
	`set_bus_config_element_property` or `set_function_port_property`.
- Do not generate bus containers simply to discover or change function ports.

## Related Guides

- [Bus Configuration](bus-configuration-mcp-tools.md)
- [Hardware Management](hardware-management-mcp-tools.md)
- [Prompt Examples](../prompts/README.md)
