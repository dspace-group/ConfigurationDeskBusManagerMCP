# Model Topology Tools

**Domain:** Behavior models, application processes, and signal-chain ports

Use this domain to add supported behavior-model files, inspect their ports, make
ports available for connection, and create application processes.

## Tool Contract

| Tool | Purpose | Safety notes |
|---|---|---|
| `add_model` | Add a supported model file to the active application. | Use the runtime schema for supported file types and options. |
| `replace_model` | Replace an existing model with another file. | Destructive because it changes the active model topology. |
| `remove_model` | Remove a model from the project. | Destructive; related connections can be removed. |
| `analyze_models` | Analyze loaded models and prepare their public interfaces. | May take time for large models. |
| `create_application_process` | Create an application process with a default periodic task. | Requires a processing-unit path. |
| `list_models` | List loaded models and file paths. | Read-only. |
| `add_model_to_signal_chain` | Make all ports of one model available for connection. | Use for bulk port exposure. |
| `add_model_port_to_signal_chain` | Make one named model port available. | Use `list_model_ports` first when the port name is unknown. |
| `list_model_ports` | List available model port names. | Read-only. |

## Typical Workflow

1. Call `add_model` with a supported model file path.
2. Call `analyze_models` when the model type requires analysis.
3. Call `list_models` and `list_model_ports` to discover available names.
4. Use `add_model_to_signal_chain` for all ports or
   `add_model_port_to_signal_chain` for a selected port.
5. Create an application process and connect function ports to model ports.
6. Call `check_conflicts` before building.

## Bulk and Selective Port Exposure

| Need | Tool |
|---|---|
| All ports from one model | `add_model_to_signal_chain` |
| One named port | `add_model_port_to_signal_chain` |
| Discover exact port names | `list_model_ports` |

## Related Guides

- [Bus Access](bus-access-mcp-tools.md)
- [Application Configuration](application-configuration-mcp-tools.md)
- [Prompt Examples](../prompts/README.md)
