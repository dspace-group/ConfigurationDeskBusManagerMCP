# Hardware Management Tools

**Domain:** Physical hardware platforms and imported topologies

Use this domain to create the topology required by hardware-facing I/O blocks. Choose a physical platform or an imported `.htfx` topology before assigning channels. For a no-hardware or VEOS build, add a processing unit application via [Application Management](app-management-mcp-tools.md) instead.

## Tool Contract

| Tool | Purpose | Safety notes |
| --- | --- | --- |
| `add_hardware_platform` | Register and scan a supported physical platform. | Open-world; contacts the physical platform. |
| `import_hardware_topology` | Import a topology from an `.htfx` file. | Requires a user-provided file path. |
| `scan_hardware` | Refresh one registered platform topology. | Open-world; contacts hardware. |
| `remove_hardware` | Remove a platform from the active project. | Destructive. |
| `list_platforms` | List registered platforms. | Read-only. |
| `refresh_platforms` | Refresh platform information. | May contact physical hardware. |
| `add_hardware_element` | Add a generic hardware element to a platform. | Use the runtime schema for supported element values. |

## Supported Platform Types

`add_hardware_platform` accepts `SCALEXIO`, `MicroAutoBox III`, and `MicroLabBox II`. Use address such as `192.0.2.10`; supply the real address at runtime.

## Decision Flow

1. **Physical hardware:** Call `add_hardware_platform`, then use its returned platform name for later scan or assignment operations.
2. **Existing topology file:** Call `import_hardware_topology` with an `.htfx`path.
3. **VEOS or no physical hardware:** Add a processing unit application — see [Application Management](app-management-mcp-tools.md).

After physical hardware is available, use the Bus Access tools to assign bus I/O function blocks and channel sets.

## Related Guides

- [Bus Access](bus-access-mcp-tools.md)
- [Build Management](build-management-mcp-tools.md)
- [Prompt Examples](../prompts/README.md)