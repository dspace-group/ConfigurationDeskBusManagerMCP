# MCP Clients

Describes minimal clients and how to connect to the ConfigurationDesk MCP server.

## Supported Clients

| Client | Transport | Status |
|---|---|---|
| VS Code (GitHub Copilot) | stdio | Supported through host configuration |
| Claude Desktop | stdio | Supported |
| MCP Inspector | stdio | Supported via `scripts/inspect.ps1` |
| Custom client | stdio | Supported |

## VS Code Configuration

Configure VS Code to launch the server through local stdio. Use either the
workspace entry point or a downloaded executable:

```json
{
  "servers": {
    "configurationdesk-mcp": {
      "type": "stdio",
      "command": "C:\\path\\to\\configurationdesk-mcp.exe"
    }
  }
}
```

For source development, replace the executable path with the absolute path to
`.venv\Scripts\configurationdesk-mcp.exe` after running `uv sync --all-packages`.
For ConfigurationDesk concepts and COM APIs, use the documentation delivered
with your licensed ConfigurationDesk release.

## Small-Model Guidance

This repository includes a [Small-Model Host Profile](small-model-host-profile.md)
with tool-selection and safety rules for ConfigurationDesk work. For VS Code
GitHub Copilot, Claude Desktop, or a custom client, add the profile to project,
workspace, or server-scoped instructions when this MCP server is available. Do
not apply it to unrelated work. The profile complements the live MCP schema and
tool results; it does not replace them.

## Claude Desktop Configuration

Add the server to `claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "configurationdesk-mcp": {
      "command": "C:\\path\\to\\configurationdesk-mcp.exe"
    }
  }
}
```

Use the absolute path to the entry point. Claude Desktop does not expand
workspace variables.

## MCP Inspector

For interactive, host-free testing of tools, resources, and prompts:

```powershell
.\scripts\inspect.ps1
```

See the [MCP Inspector guide](mcp-inspector.md).

## Custom client

Any MCP client can connect over stdio by launching `configurationdesk-mcp` or
`configurationdesk-mcp.exe`. Streamable HTTP is disabled by default and is only
available as an explicit loopback opt-in. See the
[Configuration reference](configuration.md) for the transport restriction.
