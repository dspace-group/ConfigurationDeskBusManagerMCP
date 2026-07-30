# Documentation Index

Guides for the **ConfigurationDesk MCP Server**. Start with the [project README](../README.md) to install and run the server, then use the map below to learn more.

## Guides

| Document | What it covers |
| --- | --- |
| [../README.md](../README.md) | Project overview: install, run, configure, extend |
| [../ARCHITECTURE.md](../ARCHITECTURE.md) | Server architecture, layers, and data flow |
| [com-bridge-architecture.md](com-bridge-architecture.md) | STA thread, `dispatch()`, COM connection lifecycle |
| [configuration.md](configuration.md) | All settings, transports, and client configuration |
| [compatibility.md](compatibility.md) | Supported Windows, Python, ConfigurationDesk, Bus Manager, and transport combinations |
| [extending.md](extending.md) | Add a tool, a domain, resources, and prompts |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Dev setup, coding standards, testing, PR workflow |
| [clients.md](clients.md) | Connect VS Code, Claude Desktop, and custom clients |
| [mcp-inspector.md](mcp-inspector.md) | Test tools, resources, and prompts interactively |
| [windows-executable.md](windows-executable.md) | Download and verify the Windows executable |
| [small-model-host-profile.md](small-model-host-profile.md) | Host-side tool-selection and safety guidance for small models |
| prompts/README.md | Prompt coverage and copy-and-adapt workflow requests |
| prompts/tool-map.md | All 77 tools mapped to a prompt or domain guide |
| [../GOVERNANCE.md](../GOVERNANCE.md) | Ownership, contribution, and release policy |

## Tool reference

The per-domain tool specification lives under tools/. Start at tools/README.md for the domain index, the ConfigurationDesk MCP Server glossary, the common response envelope, and the annotation reference. Each domain has its own page with terminology, COM API details, and workflow diagrams.

## Domain knowledge

This repository documents the **MCP Server**, not ConfigurationDesk itself. For ConfigurationDesk domain knowledge, refer to the documentation delivered with your licensed ConfigurationDesk release.