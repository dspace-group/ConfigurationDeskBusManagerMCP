# Windows Executable

A GitHub Release may include `configurationdesk-mcp.exe` for Windows x64. The executable bundles the Python server and its open-source Python dependencies. It does not include dSPACE ConfigurationDesk, a ConfigurationDesk license, hardware drivers, dSPACE helper packages, project assets, or communication databases.

## Requirements

See the [compatibility matrix](compatibility.md) for the complete source and executable support summary.

- 64-bit Windows 10 or Windows 11
- [dSPACE ConfigurationDesk](https://www.dspace.com/en/pub/home/products/sw/impsw/configurationdesk.cfm)installed with a valid license and registered for COM automation on the same machine when using COM tools

See the [compatibility matrix](compatibility.md) for tested product versions.

You can print the version and list tools without ConfigurationDesk installed. COM automation calls require the local ConfigurationDesk installation.

## Verify a Download

Download the executable and its matching `configurationdesk-mcp.exe.sha256` checksum from the GitHub Release.

```powershell
Get-FileHash .\configurationdesk-mcp.exe -Algorithm SHA256
Get-Content .\configurationdesk-mcp.exe.sha256
.\configurationdesk-mcp.exe --version
.\configurationdesk-mcp.exe --list-tools
```

The hash printed by `Get-FileHash` must match the first value in the checksum file. 

## Configure an MCP Host

The executable starts an MCP stdio server when invoked with no arguments. Add its absolute path to the MCP host configuration.

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

Run the executable file without any arguments, exclusively from an MCP host. It waits for via MCP protocol and does not provide an interactive shell.

## Inspector

Use MCP Inspector to inspect the executable without a full MCP host:

```powershell
npx -y @modelcontextprotocol/inspector "C:\path\to\configurationdesk-mcp.exe"
```

See [MCP Inspector](mcp-inspector.md) for the development workflow.