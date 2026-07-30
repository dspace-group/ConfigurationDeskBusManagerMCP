# configurationdesk-mcp-server

`configurationdesk-mcp-server` is a Windows MCP server for automating a locally
installed dSPACE ConfigurationDesk and Bus Manager through COM.

It is distributed with the `configurationdesk-com-bridge` package in the
[ConfigurationDesk Bus Manager MCP repository](https://github.com/dspace-group/ConfigurationDeskBusManagerMCP).

## Requirements

- Windows x64
- Python 3.11 or later for source/development use
- [dSPACE ConfigurationDesk](https://www.dspace.com/en/pub/home/products/sw/impsw/configurationdesk.cfm)
  installed with a valid license for COM automation

The server can register its tools and run its deterministic tests without a
ConfigurationDesk installation. COM operations require ConfigurationDesk and
its COM registration on the local machine.

## Source Installation

From the repository root:

```powershell
uv sync --frozen --all-packages --no-dev
uv run --frozen --no-dev configurationdesk-mcp --version
uv run --frozen --no-dev configurationdesk-mcp --list-tools
uv run --frozen --no-dev configurationdesk-mcp --list-resources
uv run --frozen --no-dev configurationdesk-mcp --list-prompts
```

Contributors who need Ruff and pytest can install the development group with
`uv sync --frozen --all-packages`.

## Transport

The supported transport is local MCP stdio. The default command starts a stdio
server:

```powershell
uv run configurationdesk-mcp
```

See the repository [README](https://github.com/dspace-group/ConfigurationDeskBusManagerMCP#readme)
for client configuration, executable releases, security guidance, and the full
documentation index.

## License

Licensed under the Apache License, Version 2.0. See the repository
[LICENSE](https://github.com/dspace-group/ConfigurationDeskBusManagerMCP/blob/main/LICENSE).
