# Communication Matrix Tools

**Domain:** Communication matrix management

Use this domain to import a network definition, inspect clusters, ECUs, PDUs,
frames, and signals, and make controlled edits to writable matrix properties.

## Supported File Types

| Format | Extension |
|---|---|
| AUTOSAR system description | `.arxml` |
| CAN database | `.dbc` |
| LIN description | `.ldf` |

## Tool Contract

| Tool | Purpose | Safety notes |
|---|---|---|
| `add_communication_matrix` | Import a matrix file. | Requires an active application. |
| `remove_communication_matrix` | Remove a loaded matrix. | Destructive; `force=true` can remove assignments that depend on it. |
| `replace_communication_matrix_assignment` | Replace a matrix assigned to a bus configuration with another loaded matrix. | Destructive; user-defined matrix element settings of replaced elements are lost. |
| `list_matrices` | List loaded clusters and ECUs. | Read-only; paginated independently for clusters and ECUs. |
| `find_matrix_elements` | Find elements by friendly type, name, or XPath. | Read-only; paginated; prefer `cluster`, `ecu`, `pdu`, `frame`, or `signal`. |
| `set_matrix_element_property` | Change writable matrix-level properties. | Use a precise XPath for duplicate names or deliberate bulk edits. |

Both read tools accept `offset` and `limit`; refer to the shared
[pagination contract](README.md#pagination) for defaults and response metadata.

## Typical Workflow

1. Call `add_communication_matrix` with the supplied file path.
2. Call `list_matrices` to discover clusters and ECUs.
3. Call `find_matrix_elements` before assigning exact elements to a bus
	configuration.
4. Use `set_matrix_element_property` only for matrix-level values such as signal
	initial values or PDU/signal length.

Use `set_bus_config_element_property` for bus-configuration feature values and
`set_function_port_property` for exposed function port values.


## Replacing an Assigned Matrix

Use `replace_communication_matrix_assignment` to move a bus configuration to an
updated version of a communication matrix, for example after the ARXML file was
changed outside ConfigurationDesk. The tool wraps the Bus Manager command
`ReplaceCommunicationMatrixAssignment`.

1. Load the updated file with `add_communication_matrix`. The new matrix must
   not already be assigned to the bus configuration.
2. Call `replace_communication_matrix_assignment` with `bus_config_name` and
   `new_matrix_name` (as shown by `list_matrices`). Pass
   `assigned_matrix_name` when more than one matrix is assigned to the bus
   configuration.
3. Review `deprecated_nodes` and `warnings`, then call `check_conflicts`.

The new matrix name must identify exactly one loaded matrix. Duplicate loaded
names return `AMBIGUOUS_MATRIX_NAME` without changing the configuration or the
additional replacing conditions setting. Use distinct filenames for matrix
versions before importing them and select a unique loaded name. Inspect
assignments before removing or reloading duplicates; loaded matrix names may
not be editable. An assigned name that identifies
different source files is also rejected, with `AMBIGUOUS_MATRIX_ASSIGNMENT`.
Repeated instances of the same source across bus configuration parts are allowed.
If the requested source is already assigned, `MATRIX_ALREADY_ASSIGNED` is
returned before changing any setting or assignment.

Verification compares the source file name, file path, and content hash of
every retained matrix-node instance with the requested loaded matrix. An
unchanged node name alone is not proof of replacement. Missing source metadata
before replacement returns `MATRIX_SOURCE_UNAVAILABLE` without making changes.
A no-op, partial update, or unreadable source metadata after the call returns
`VERIFICATION_FAILED`; inspect the configuration before continuing or retrying.

Replacement behavior:

- Every part of the bus configuration that contains elements of the replaced
   matrix is affected (Simulated ECUs, Inspection, Manipulation, Bus Access
   Requests). Other matrices and other bus configurations remain unchanged.
- Elements that are identified in the new matrix are replaced and take their
  settings from it. User-defined settings of matrix elements are lost;
  user-defined function-port initial and saturation values are preserved, but
  may be automatically saturated (clamped) if the function-port data type changes.
- Elements that cannot be identified stay unchanged in a node named
   `<matrix node name> (deprecated <number>)`, reported as `deprecated_nodes`.
- New elements of the new matrix are not assigned automatically.
- The matrix node name in the bus configuration stays unchanged, so existing
   XPath queries and scripts keep working.
- Model port blocks mapped to the bus configuration are not updated.

`use_additional_replacing_conditions` optionally enables or disables the
application-wide additional replacing conditions for this call only; the
original value must be readable before any setting or assignment is changed.
An unreadable original value returns `REPLACING_CONDITIONS_UNAVAILABLE` without
mutation. Omit the argument to use the current setting without reading or
overriding it.

When an override is requested, restoration is attempted even if the option
setter or replacement fails, and the original value is verified by read-back.
The requested value is also read back before replacement. If the write fails
or its value cannot be confirmed, replacement is not attempted and the tool
returns `REPLACING_CONDITIONS_SET_FAILED` after confirming restoration. If
restoration also fails, `REPLACING_CONDITIONS_RESTORE_FAILED` takes precedence.
`additional_replacing_conditions` is included in both success and failure
responses once option handling begins. If restoration fails, the tool returns
the non-retryable error `REPLACING_CONDITIONS_RESTORE_FAILED`, preserving any
replacement error and restoration error. This is a failure even if
`replacement_verified` is true. Restore the original value in ConfigurationDesk
Options and inspect the configuration before continuing; do not retry the
replacement automatically.

## Related Guides

- [Bus Configuration](bus-configuration-mcp-tools.md)
- [Prompt Examples](../prompts/README.md)
- `configurationdesk://reference/xpath`
- `configurationdesk://reference/valid-values`
