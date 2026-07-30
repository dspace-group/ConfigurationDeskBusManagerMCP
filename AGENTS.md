# Agent Guidance

This file contains only repository-specific rules that are not obvious from the
source tree.

## Package Boundary

- `configurationdesk_com_bridge` is a standalone SDK and must not import from
  `ConfigurationDeskMCP/sources`.
- All COM access must use `configurationdesk_com_bridge.dispatch(...)` so it
  executes on the dedicated STA thread.
- Domain decisions such as XPath resolution and verification policy belong in
  `ConfigurationDeskMCP/sources/services`, not in the bridge.

## Tool Registration

- Public modules under `ConfigurationDeskMCP/sources/tools/` are discovered at
  startup. Add a tool domain by adding its public tool module; do not add a
  separate manifest.
- Helper modules start with `_` and are excluded from discovery.

## Validation

- Install the workspace: `uv sync --all-packages`.
- Run deterministic tests: `uv run pytest ConfigurationDeskMCP/tests`.
- Check tool registration: `uv run configurationdesk-mcp --list-tools`.
- Build the Windows executable: `uv sync --all-packages --group build` followed
  by `./scripts/build-exe.ps1`.
- Run the release audit before creating a tag: `./scripts/validate-release.ps1`.

## Release Constraints

- Do not add proprietary ConfigurationDesk installation files, dSPACE helper
  binaries, test assets, credentials, or local IDE settings to the repository
  or executable.
- Stdio is the supported public transport. Streamable HTTP is disabled by
  default and must remain loopback-only until an authenticated deployment mode
  is implemented.