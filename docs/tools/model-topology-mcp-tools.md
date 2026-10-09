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
| `create_application_process` | Create an application process with a default periodic task. | Requires a processing unit application. |
| `list_models` | List loaded models and file paths. | Read-only. |
| `add_model_to_signal_chain` | Make all model port blocks of one model available for connection. | Use for bulk exposure. |
| `add_model_port_block_to_signal_chain` | Make one named model port block available. | Use `list_model_port_blocks` first when the name is unknown. Rejects names that exist at several hierarchy levels. |
| `list_model_port_blocks` | List available model port blocks, including blocks in subsystems, with their hierarchy paths. | Read-only. |
| `list_model_ports` | List the model ports inside the model port blocks, with their read-only properties. | Read-only; pass `port_block_name` (name or hierarchy path) to scope to matching blocks. |

## Typical Workflow

1. Call `add_model` with a supported model file path.
2. Call `analyze_models` when the model type requires analysis.
3. Call `list_models` and `list_model_port_blocks` to discover available names.
4. Use `add_model_to_signal_chain` for all model port blocks or
   `add_model_port_block_to_signal_chain` for a selected one.
5. Create an application process and connect function ports to model ports.
6. Call `check_conflicts` before building.

## Bulk and Selective Exposure

| Need | Tool |
|---|---|
| All model port blocks from one model | `add_model_to_signal_chain` |
| One named model port block | `add_model_port_block_to_signal_chain` |
| Discover exact model port block names | `list_model_port_blocks` |
| Inspect port direction, data type, or width | `list_model_ports` |

## Model Port Blocks and Model Ports

A model port block is the graphical representation of the ConfigurationDesk
model interface in the signal chain. Each block contains one or more model
ports of the same data direction: data inports, data outports, runnable
function ports, or configuration ports.

Use `list_model_port_blocks` when another tool needs a block name. Use
`list_model_ports` to inspect the ports themselves. Model port and model port
block properties are read-only in ConfigurationDesk; except for the names of
unresolved blocks created via function blocks, they can only be changed in the
behavior model.

## Hierarchy and Ambiguous Names

The model topology is hierarchical: model port blocks can sit at the model's
root level or inside subsystems, so the same block name can occur at several
hierarchy levels (for example `demosmd_io/Wavetable` and
`demosmd_io/Subsystem/Wavetable`). The model topology tools search every level:

- `list_model_port_blocks` returns each block's full path in
  `port_block_paths`. Names that occur at several levels are listed under
  `ambiguous_names`, and `port_blocks` uses their full paths as identifiers.
- Tools that take a model port block name accept a bare name or a hierarchy
  path. The path can be relative to the model (`Subsystem/Wavetable`) or
  prefixed with the model name (`demosmd_io/Wavetable` addresses the
  root-level block).
- If a bare name matches blocks at several hierarchy levels,
  `add_model_port_block_to_signal_chain` and
  `connect_function_block_port_to_model_port` change nothing and return
  `AMBIGUOUS_TARGET`. The agent must ask the user which path is meant and must
  not pick one itself.

## Related Guides

- [Bus Access](bus-access-mcp-tools.md)
- [Application Configuration](application-configuration-mcp-tools.md)
- [Prompt Examples](../prompts/README.md)
