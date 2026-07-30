# Project Management Tools

**Domain:** Project management

Use these tools to select a project location, create or open projects, and
create backups. Call `start_configurationdesk` before using this domain.

## Tool Contract

The MCP host exposes the current JSON schema for each tool. The tables below
summarize the user-visible purpose and important safety behavior; use the host
schema for the authoritative input fields and defaults.

| Tool | Purpose | Safety notes |
|---|---|---|
| `set_project_root` | Select a directory where ConfigurationDesk stores projects. | Creates or activates the directory as needed. |
| `create_project` | Create and activate a project. | `replace=true` can overwrite an existing project. |
| `open_project` | Open an existing project. | Reopening the active project is safe. |
| `close_project` | Close the active project. | Use `save=true` to persist pending changes. |
| `remove_project` | Remove a project. | Destructive; `delete_files=true` also removes project files. |
| `list_projects` | List projects in the active project location. | Read-only. |
| `get_project_path` | Return the active project path. | Read-only. |
| `backup_project` | Create a backup archive for the active project. | Writes an archive to the supplied destination. |
| `open_project_from_backup` | Restore or open a backup archive as a project. | `overwrite=true` can replace an existing project. |

## Typical Workflow

1. Call `set_project_root` when projects need a specific storage directory.
2. Call `create_project` for a new project or `open_project` for an existing
   project.
3. Call `add_application` before configuring communication matrices, models, or
  hardware.
4. Call `get_application_status` to verify the active project and application.
5. Use `backup_project` before destructive or experimental changes.

## Examples

Create a project in a dedicated directory:

```json
{
  "name": "VehicleHIL",
  "project_root": "C:\\Projects",
  "replace": false
}
```

Remove a project without deleting its files:

```json
{
  "name": "ObsoletePrototype",
  "delete_files": false
}
```

## Failure Handling

If a project operation returns a structured error, inspect `error_code`,
`recovery_hint`, and `next_action`. Do not retry destructive operations until the
active project state has been checked with `get_application_status`.

## Related Guides

- [Application Management](app-management-mcp-tools.md)
- [Configuration Reference](../configuration.md)
- [Prompt Examples](../prompts/README.md)
