# Working View and Conflict Tools

**Domain:** Working views, exported view files, and configuration conflicts

Use this domain to organize a signal-chain view, export a selected view to a
file, and inspect conflicts before a build or other high-impact operation.

## Tool Contract

| Tool | Purpose | Safety notes |
|---|---|---|
| `create_working_view` | Create a named working view. | Changes project state. |
| `list_working_views` | List available working views. | Read-only. |
| `remove_working_view` | Remove one working view by name. | Destructive. |
| `clear_all_working_views` | Remove all removable working views. | Destructive; inspect first. |
| `export_working_view` | Write a working view to a file. | Writes to the requested path; not read-only. |
| `check_conflicts` | Return configuration conflicts and suggested values. | Read-only; call before build or deployment. |

## Conflict Workflow

1. Call `check_conflicts` after changing matrices, bus configurations, models,
   I/O blocks, or hardware assignments.
2. Inspect each returned conflict's context, property, current value, suggested
   values, and effect.
3. Use the owning domain tool to resolve the issue.
4. Call `check_conflicts` again before `build_application`.

## Working-View Workflow

1. Call `create_working_view` when a workflow needs a named subset of the signal
   chain.
2. Call `list_working_views` to discover available names.
3. Call `export_working_view` only when a file artifact is needed.
4. Use `remove_working_view` or `clear_all_working_views` only after confirming
   the views are no longer needed.
5. Treat a successful `remove_working_view` response as confirmation that the
   removal was verified. If removal is not confirmed, inspect the working views
   before deciding whether to try again.

## Related Guides

- [Build Management](build-management-mcp-tools.md)
- [Model Topology](model-topology-mcp-tools.md)
- [Prompt Examples](../prompts/README.md)
