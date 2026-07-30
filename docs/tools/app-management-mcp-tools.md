# Application Management Tools

**Domain:** Applications within a project

A project can contain multiple applications. Exactly one application is active
for project-scoped model, matrix, bus, hardware, and build work.

## Tool Contract

| Tool | Purpose | Safety notes |
|---|---|---|
| `add_application` | Create and activate an application in the active project. | Requires an open project. |
| `activate_application` | Make an existing application active. | Safe when the named application is already active. |
| `remove_application` | Remove an application from the project. | Destructive; inspect current state first. |
| `list_applications` | List applications and their active status. | Read-only. |

## Typical Workflow

1. Create or open a project.
2. Call `list_applications` when the target application is uncertain.
3. Call `add_application` for a new application or `activate_application` for an
	existing one.
4. Call `get_application_status` to verify the active application before adding
	models, matrices, bus configurations, or hardware.

## Failure Handling

If the project prerequisite is missing, resolve it with `create_project` or
`open_project`. Do not remove an application until you have confirmed that it is
not needed by the current workflow.

## Related Guides

- [Project Management](project-management-mcp-tools.md)
- [Model Topology](model-topology-mcp-tools.md)
- [Prompt Examples](../prompts/README.md)
