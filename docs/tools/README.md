# Public MCP Tool Reference

This directory documents the ConfigurationDesk MCP tool contract. It is a usage reference for MCP hosts and users, not a replacement for ConfigurationDesk product documentation.

## Contract Boundary

Each MCP host exposes the current JSON schema, tool description, and annotations at runtime. Treat that schema as authoritative for fields, defaults, and allowed values. These pages summarize tool purpose, prerequisites, safety behavior, and common call sequences.

For ConfigurationDesk product concepts, use the documentation delivered with your licensed ConfigurationDesk release.

## Start Here

1. Call `start_configurationdesk` before domain tools.
2. Create or open a project, then add or activate an application.
3. Use the domain pages below to choose tools by outcome.
4. Check `success`, `verified`, `error_code`, `recovery_hint`, and `next_action`on every response.

The server exposes 77 tools across the 12 domains below.

## Domain Index

| Domain | Public tools | Use it for |
| --- | --- | --- |
| [Application Lifecycle](application-lifecycle-mcp-tools.md) | 7 | Server startup, status, save, undo/redo, diagnostics |
| [Project Management](project-management-mcp-tools.md) | 9 | Project locations, projects, backups |
| [Application Management](app-management-mcp-tools.md) | 4 | Applications inside a project |
| [Application Configuration](application-configuration-mcp-tools.md) | 1 | Read-only configuration-tree inspection |
| [Model Topology](model-topology-mcp-tools.md) | 9 | Behavior models, ports, application processes |
| [Hardware Management](hardware-management-mcp-tools.md) | 8 | Physical platforms, imported topology, VEOS setup |
| [Communication Matrix](communication-matrix-mcp-tools.md) | 5 | ARXML/DBC/LDF data and matrix properties |
| [Bus Configuration](bus-configuration-mcp-tools.md) | 12 | Restbus assignment, features, ports, BSC output |
| [Bus Access](bus-access-mcp-tools.md) | 11 | Bus I/O blocks, bus access, channel assignment |
| [Build Management](build-management-mcp-tools.md) | 2 | Conflict-checked build and result discovery |
| [Working Views and Conflicts](working-view-mcp-tools.md) | 6 | Working-view files and conflict reporting |
| I/O Functions | 3 | `list_io_function_block_types`, `add_io_function_block`, and `connect_function_block_port_to_model_port` |

## Response Contract

All tools return a JSON string with `success`.

```json
{
  "success": false,
  "error_code": "COM_DISCONNECTED",
  "retryable": true,
  "recovery_hint": "Call start_configurationdesk first.",
  "next_action": "Call start_configurationdesk."
}
```

Use `retryable` with `recovery_hint` and `next_action`; do not repeatedly retry a permanent failure.

## Pagination

Potentially large read operations accept `offset` and `limit`: `list_bus_access_requests`, `find_bus_config_elements`, `list_matrices`, `find_matrix_elements`, and `list_configuration`. `offset` is zero-based; `limit` defaults to 100 and cannot exceed 1000. When `next_offset` is not `null`, pass it as the next call's `offset` to retrieve the following page.

Successful paginated responses include `count` and `total_count` for the full result size, `returned_count` for the current page, plus `offset`, `limit`, and `next_offset`. `list_matrices` applies the requested page independently to its `clusters` and `ecus` views; `view_counts` reports the complete size of each view.

## Safety Annotations

| Annotation | Meaning |
| --- | --- |
| `readOnlyHint` | The tool does not change project state. |
| `destructiveHint` | The tool can delete, replace, overwrite, unload, deploy, or activate existing project or deployed state. |
| `idempotentHint` | Repeating the same call reaches the same end state. |
| `openWorldHint` | The tool interacts with external hardware or another open system. |

## Related Guides

- [Prompt Examples](../prompts/README.md)
- [Tool-to-Prompt Map](../prompts/tool-map.md)
- [Configuration Reference](../configuration.md)
- [MCP Clients](../clients.md)
- [MCP Inspector](../mcp-inspector.md)