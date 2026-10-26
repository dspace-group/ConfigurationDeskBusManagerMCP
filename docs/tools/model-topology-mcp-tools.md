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
| `create_application_process` | Create an application process, with or without a default periodic task. | Requires a processing unit application. Send `provide_default_task` whenever the request states it; it is only elicited from the user when omitted, and falls back to `true` when unanswered. Call once per application process when several are requested. |
| `list_models` | List loaded models and file paths. | Read-only. |
| `add_model_to_signal_chain` | Make all model port blocks of one model available for connection. | Use for bulk exposure. |
| `add_model_port_block_to_signal_chain` | Make one named model port block available. | Use `list_model_port_blocks` first when the name is unknown. Rejects names that exist at several hierarchy levels. |
| `list_model_port_blocks` | List available model port blocks, including blocks in subsystems, with their hierarchy paths. | Read-only. |
| `list_model_ports` | List the model ports inside the model port blocks, with their read-only properties. | Read-only; pass `port_block_name` (name or hierarchy path) to scope to matching blocks. `leaf_ports` (paginated with `offset`/`limit`) also lists ports nested in port groups. |
| `connect_model_port_to_model_port` | Map one model port to another model port (model communication), like drawing the mapping line manually. | ConfigurationDesk applies its mapping rules; refused mappings create no link. Not idempotent: a second identical call is refused. |

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
| Connect one model port to another model port | `connect_model_port_to_model_port` |

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

Model ports can be nested in port groups inside a block, for example the bus
hierarchy of a bus simulation container
(`Restbus_BusConfiguration_Out/In/Simulated ECUs/.../CanBodyCommController Enable`).
`list_model_ports` returns two lists:

- `ports` and `count`: the direct children of each block (unchanged behavior; a
  port group appears as one entry without port properties).
- `leaf_ports`: every model port at any depth, with `port_path` (the path inside
  its block, e.g. `Group1/Group2/Speed`), `port_block_path`, and `full_path`.
  `leaf_ports` is paginated; `leaf_ports_page` holds `total_count`,
  `returned_count`, `offset`, `limit`, and `next_offset`.

## Connecting Model Ports to Model Ports

`connect_model_port_to_model_port` creates one mapping line between two model
ports, for example `masterAppl / Data Outport1 / data1` to
`slaveAppl / Data Inport1 / data1`. Each side is given as model name, model port
block (bare name or hierarchy path), and `port_path` from `leaf_ports`.

The tool calls ConfigurationDesk's `ConnectObjects`, which applies the
ConfigurationDesk mapping rules itself. The server does not implement any
mapping rules. The result matches what happens when the mapping line is dropped
in the UI:

| Result | Meaning |
|---|---|
| `status: "compatible"` | The link was created and no conflict appeared with it. |
| `status: "warning"` | The link was created. `warnings` lists every conflict that appeared with it, with `message` in the wording of the Conflicts Viewer (e.g. `Model port mapping: Invalid connection between data port blocks of same model`) and the `effect` ConfigurationDesk reports (e.g. `Generate no code`). |
| `status: "unknown"` | The link was created, but the conflict export after connecting failed, so its conflicts could not be read. `success` is `true`; `verified` reports as usual whether the link was confirmed. `conflicts_read_error` holds the error and `note` says so. Do not repeat the connection; call `check_conflicts` to inspect the conflicts. |
| `success: false`, `status: "error"`, `error_code: "MAPPING_REFUSED"` | ConfigurationDesk refused the mapping (e.g. inport to inport, a duplicate mapping line, or a second source on a connected inport). No link was created. `configurationdesk_message` holds ConfigurationDesk's message unchanged. The ConfigurationDesk COM API does not report the specific reason; the UI shows it only while the mapping line is dragged. |

ConfigurationDesk adds model port blocks that are not yet in the signal chain
when it connects their ports; the tool lists them in
`blocks_added_to_signal_chain`. The texts come from the conflict export
(`ExportConflictsToXML`), the same source as `check_conflicts`.

### Suppressed conflicts

Like the Conflicts Viewer and `check_conflicts`, the tool reports only the
conflicts that ConfigurationDesk generates. Conflicts suppressed in the
ConfigurationDesk options are not generated and therefore not reported, even
though the UI shows a warning for them while a mapping line is dragged.

By default, ConfigurationDesk suppresses the "Mismatching data type" conflict.
A mapping such as UInt32 → Int32 therefore returns `status: "compatible"`,
while the UI shows the yellow warning "Model port mapping: Mismatching data
type" during dragging. To have the conflict reported, clear
**Suppress the 'Mismatching data type' conflict** in **Options → Configuration →
Conflict settings**. The conflict then appears in the Conflicts Viewer, in
`check_conflicts`, and as a warning of this tool.

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
  `add_model_port_block_to_signal_chain`,
  `connect_function_block_port_to_model_port`, and
  `connect_model_port_to_model_port` change nothing and return
  `AMBIGUOUS_TARGET`. The agent must ask the user which path is meant and must
  not pick one itself.
- Blocks with the same name at the same hierarchy level (for example the inport
  and outport blocks of an FMU) are told apart by the `port_path` passed to
  `connect_model_port_to_model_port`.

## Related Guides

- [Bus Access](bus-access-mcp-tools.md)
- [Application Configuration](application-configuration-mcp-tools.md)
- [Prompt Examples](../prompts/README.md)
