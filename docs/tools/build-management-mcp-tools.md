# Build Management Tools

**Domain:** Build and result discovery

Use these tools only after confirming that the active application has the required models,
hardware or processing-unit setup, and no blocking conflicts.

## Tool Contract

| Tool | Purpose | Safety notes |
|---|---|---|
| `build_application` | Build the active application and optionally download or start it. | Destructive when unload, download, or start changes deployed state; open-world and can affect connected hardware. |
| `get_build_result` | Return the path to the latest build result. | Read-only. |

The runtime schema for `build_application` accepts `download`, `start`, and
`unload`. Use `download=false` when hardware download is not wanted.

## Safe Build Sequence

1. Call `check_conflicts` after configuration changes.
2. Resolve every error-level conflict before starting a build.
3. Generate bus containers only when the user explicitly requests BSC or
	container output.
4. Call `build_application` with the intended `download`, `start`, and `unload`
	values.
5. Call `get_build_result` after a successful build.

## Failure Handling

A build may take several minutes. Do not blindly retry a failed build. Inspect
its structured error response and current configuration state, then resolve the
reported issue before retrying.

When a build is canceled, the response is non-retryable. Inspect the current
build state and rerun `build_application` only after the user explicitly chooses
to do so.

## Related Guides

- [Working Views and Conflicts](working-view-mcp-tools.md)
- [Hardware Management](hardware-management-mcp-tools.md)
- [Prompt Examples](../prompts/README.md)
