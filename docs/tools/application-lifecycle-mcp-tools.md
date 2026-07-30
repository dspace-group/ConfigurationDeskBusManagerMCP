# Application Lifecycle Tools

**Domain:** Application lifecycle

Use these tools to start a local ConfigurationDesk session, inspect state, save
work, and recover from startup problems.

## Tool Contract

| Tool | Purpose | Safety notes |
|---|---|---|
| `start_configurationdesk` | Start or attach to a local ConfigurationDesk session. | Call before every domain workflow; safe to call again. |
| `stop_configurationdesk` | Close the session, optionally saving work. | Destructive because it closes the application. |
| `get_application_status` | Return the active project root, project, and application state. | Read-only. |
| `save_project` | Save the active project. | Requires an active project. |
| `undo` | Reverse the most recent supported configuration action. | Changes state; do not use as a recovery substitute. |
| `redo` | Reapply the most recently undone supported action. | Changes state. |
| `diagnose_connection` | Report startup environment diagnostics. | Read-only; call after startup failure. |

## Standard Startup Sequence

1. Call `start_configurationdesk`.
2. If startup fails, call `diagnose_connection` once and inspect its structured
   result.
3. Call `get_application_status` before selecting a project workflow.

## Failure Handling

`start_configurationdesk` returns structured errors when the local product is
not installed, unavailable, or blocked. Use `diagnose_connection` instead of
repeating the same failing call. The server can be installed and its tools listed
without ConfigurationDesk, but domain operations require a licensed local
ConfigurationDesk installation.

## Related Guides

- [Project Management](project-management-mcp-tools.md)
- [Configuration Reference](../configuration.md)
- [Prompt Examples](../prompts/README.md)
