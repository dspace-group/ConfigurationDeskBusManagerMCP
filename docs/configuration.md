# Configuration Reference

Every setting has a safe default - the server runs with **no configuration** in
stdio mode. Override settings only when you need to (HTTP transport, verbose
logging, a non-default ConfigurationDesk version, longer COM timeouts).

---

## 1. Where configuration comes from

See the [compatibility matrix](compatibility.md) for supported Windows, Python,
ConfigurationDesk, Bus Manager, and transport combinations.

Settings are read by [`sources/config/settings.py`](../ConfigurationDeskMCP/sources/config/settings.py)
(via `pydantic-settings`) in this precedence order (highest first):

1. **Process environment variables** - set in your shell, MCP host, or
  container.
2. `.env` **file** in the working directory — auto-loaded if present.
3. **Built-in defaults** - defined in `Settings`.

Variable names are **case-insensitive**. Copy [`.env.example`](../.env.example) to
`.env` to start from a documented template.

---

## 2. Server settings

These are validated on startup; an invalid value fails fast with a clear error.

| Variable | Default | Allowed values | Description |
|---|---|---|---|
| `MCP_TRANSPORT` | `stdio` | `stdio`, `streamable-http` | `stdio` is the supported public transport. HTTP requires explicit local opt-in. |
| `MCP_ENABLE_STREAMABLE_HTTP` | `false` | `true`, `false` | Required to enable streamable HTTP. |
| `MCP_HOST` | `127.0.0.1` | `127.0.0.1`, `::1`, `localhost` | Loopback host for optional HTTP. Ignored for stdio. |
| `MCP_PORT` | `8000` | `1`–`65535` | TCP port for the HTTP transport. Ignored for stdio. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | Python logging level for all server-side (stderr) output. |

> **stdio logging rule:** in stdio mode, **stdout is the protocol channel**. All
> logs go to **stderr** - never print to stdout from a tool. Use `DEBUG` only for
> troubleshooting; it is noisy.

---

## 3. COM bridge settings

These tune how the bridge talks to ConfigurationDesk over COM.

| Variable | Default | Range | Description |
|---|---|---|---|
| `COM_TIMEOUT_MS` | `30000` | `500`–`120000` | Wall-clock timeout (ms) for any single COM method call. Exceeding it raises a `BridgeTimeoutError`. Keep it above the verification window used by mutating operations. |
| `COM_LAUNCH_TIMEOUT_MS` | `30000` | `5000`–`120000` | Max ms to wait for ConfigurationDesk to finish initializing after launch. |
| `COM_RECONNECT_ATTEMPTS` | `3` | `1`–`10` | Number of reconnect attempts after `RPC_E_DISCONNECTED` before the circuit opens. |
| `CONFIGURATIONDESK_PROGID` | `ConfigurationDesk.Application` | COM ProgID | Override the COM ProgID - e.g. to pin a specific installed version. |
| `CONFIGURATIONDESK_COMMON_PATH` | *(unset)* | path | Path to the dSPACE COM `Enums` helper package, when not auto-discoverable. |

> `CONFIGURATIONDESK_PROGID` and `CONFIGURATIONDESK_COMMON_PATH` are read by the
> COM bridge ([connection.py](../configurationdesk_com_bridge/connection.py)), so
> they apply whether you use the server or the bridge SDK directly.

---

## 4. Transports

### stdio (default)

The host launches the server as a child process and speaks MCP over
stdin/stdout. This is what VS Code and Claude Desktop use. No host/port needed.

```powershell
uv run configurationdesk-mcp          # MCP_TRANSPORT defaults to stdio
```

### streamable-http (local opt-in)

Streamable HTTP is disabled by default. It is supported only for a local,
loopback-bound process; LAN, remote, and public HTTP deployments are unsupported
in this release.

```powershell
$env:MCP_TRANSPORT = "streamable-http"
$env:MCP_ENABLE_STREAMABLE_HTTP = "true"
$env:MCP_HOST = "127.0.0.1"
$env:MCP_PORT = "8000"
uv run configurationdesk-mcp
```

> **Security:** startup rejects a non-loopback HTTP host. Remote HTTP requires
> OAuth-based authentication, least-privilege authorization, and TLS at a
> trusted boundary before it can be supported.

---

## 5. MCP client configuration

Configure an MCP host to launch the server as a local stdio child process:

```jsonc
{
  "servers": {
    "configurationdesk-mcp": {
      "type": "stdio",
      "command": "C:\\path\\to\\configurationdesk-mcp.exe"
    }
  }
}
```

For source development, use the absolute path to the local `.venv` entry point.
For a GitHub Release, use the absolute executable path. For ConfigurationDesk
concepts and COM APIs, use the documentation delivered with your licensed
ConfigurationDesk release.

To pass settings to the server from a host, add them under `env`:

```jsonc
"configurationdesk-mcp": {
  "type": "stdio",
  "command": "${workspaceFolder}/.venv/Scripts/configurationdesk-mcp.exe",
  "env": { "LOG_LEVEL": "DEBUG", "COM_TIMEOUT_MS": "60000" }
}
```

Other hosts use the same idea with their own config file - see [clients.md](clients.md).

---

## 6. Verifying configuration

```powershell
uv run configurationdesk-mcp --version          # server version
uv run configurationdesk-mcp --list-tools       # confirm tools register (no COM needed)
uv run configurationdesk-mcp --list-resources   # confirm resources register (no COM needed)
uv run configurationdesk-mcp --list-prompts     # confirm prompts register (no COM needed)
```

At run time, read the `configurationdesk://status` resource (connection + active
project) to inspect the local ConfigurationDesk state.

---

## Related documentation

- [README](../README.md) — install and run
- [Extending guide](extending.md)
- [MCP clients](clients.md)
- [Architecture](../ARCHITECTURE.md)