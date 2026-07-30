# Application Configuration Tools

**Domain:** Configuration-tree inspection

This domain provides a read-only view of configuration elements in the active
application. It helps an MCP host inspect scheduling-related and structural state
before it changes models, hardware, or bus configuration.

## Tool Contract

| Tool | Purpose | Safety notes |
|---|---|---|
| `list_configuration` | Return the application configuration tree. | Read-only; requires an active application; paginated. |

`list_configuration` accepts `offset` and `limit`; see the shared
[pagination contract](README.md#pagination) for defaults and response metadata.

## Typical Use

Call `list_configuration` when a workflow needs to discover existing processing
units, application processes, tasks, or related configuration elements. Use the
returned names and paths as inputs to the domain-specific tools that perform
changes.

## Related Guides

- [Model Topology](model-topology-mcp-tools.md)
- [Hardware Management](hardware-management-mcp-tools.md)
- [Prompt Examples](../prompts/README.md)
