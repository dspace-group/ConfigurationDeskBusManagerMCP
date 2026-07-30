# Compatibility Matrix

This page is the canonical compatibility summary for the ConfigurationDesk MCP Server source release and optional Windows executable.

ConfigurationDesk 2026-A (26.2) is the current tested reference, not a minimum version requirement. The server is not intentionally restricted to the latest ConfigurationDesk release. Earlier or later installations may work when their COM automation API is compatible; those combinations are not covered by this repository's test evidence unless listed below.

## Support Matrix

| Component | Tested/reference values | Status | Evidence or notes |
| --- | --- | --- | --- |
| Operating system | 64-bit Windows 10 and Windows 11 | Supported | COM automation requires Windows and a 64-bit Python process. |
| Python | CPython 3.11, 3.12, and 3.13 | Tested | The CI matrix runs these versions on Windows. |
| [ConfigurationDesk](https://www.dspace.com/en/pub/home/products/sw/impsw/configurationdesk.cfm) | 2026-A (26.2) | Tested | The repository's documented source-development and COM test target. |
| [ConfigurationDesk](https://www.dspace.com/en/pub/home/products/sw/impsw/configurationdesk.cfm) | Earlier or later releases | Not validated by this repository | May work when the installed COM automation API is compatible; validate the target installation before relying on it. |
| Bus Manager | Delivered with the supported ConfigurationDesk installation | Not independently versioned | This repository does not publish a separate Bus Manager compatibility version. |
| MCP transport | Local stdio | Supported | The supported public transport. |
| Streamable HTTP | Loopback-only, explicit opt-in | Limited | LAN, remote, and public HTTP deployment are unsupported. |

## Source and Executable

The source server and optional Windows executable use the same MCP tool surface. The executable, when produced, is Windows x64 and does not include ConfigurationDesk, its license, drivers, helper packages, or project assets.

The source checkout requires `uv`. Runtime setup and contributor setup are shown in the root [README](../README.md). Releases may include a Windows executable; see [Windows Executable](windows-executable.md) for its requirements and verification steps.

## Test Status

The compatibility claims on this page describe the repository's automated test matrix and documented product target. They do not replace the product requirements or release notes supplied with a licensed ConfigurationDesk installation.

When a new ConfigurationDesk release is tested, update the tested row with the release identifier and evidence date. Do not broaden the supported range solely because a release is expected to work.