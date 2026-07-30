# -*- coding: utf-8 -*-
"""Bus configuration tools for ConfigurationDesk MCP Server."""

from typing import Annotated

from pydantic import Field

from sources.models.property_values import StrictPropertyValue
from sources.server.app import mcp
from sources.server.preconditions import with_preconditions
from sources.services._pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT
from sources.services import bus_config_service as svc


@mcp.tool(
    name="create_bus_configuration",
    description=(
        "[BUS CONFIGURATION] Create a new empty bus configuration in the project. "
        "USE THIS when the user says 'create bus config' or 'create bus configuration'. "
        "A bus configuration has three parts: 'Simulated ECUs' (restbus simulation), "
        "'Inspection' (monitoring RX traffic), and 'Manipulation' (overriding TX traffic). "
        "Typical workflow: create_bus_configuration → assign_ecu_to_bus_config or "
        "assign_matrix_to_bus_config → add_feature_to_bus_element → generate_bus_containers. "
        "Name conventions: use descriptive names like 'CAN_Restbus', 'LIN_DoorConfig', or 'BC_ECU1'. "
        "NOTE: This is NOT create_io_function_block — that tool creates hardware I/O blocks, not bus configs."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application")
async def create_bus_configuration(
    name: Annotated[
        str | None,
        Field(
            description="Name for the new bus configuration, e.g. 'BusConfig1'",
        ),
    ] = None,
) -> str:
    return await svc.create(name)


@mcp.tool(
    name="remove_bus_configuration",
    description=(
        "Remove bus configuration(s) by name. Supports wildcards like 'Bus*' to remove multiple. "
        "This is destructive and removes all assigned ECUs, features, and bus access requests within the configuration."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "bus_config")
async def remove_bus_configuration(
    name: Annotated[
        str,
        Field(
            description="Name or wildcard pattern of bus configuration(s) to remove, e.g. 'BusConfig1' or 'Bus*'",
        ),
    ],
) -> str:
    return await svc.remove(name)


@mcp.tool(
    name="list_bus_configurations",
    description=(
        "List the names of all bus configurations in the project. "
        "Returns top-level bus configuration names only, not the full hierarchy. "
        "Use find_bus_config_elements to inspect assigned elements or discover paths for other tools."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application")
async def list_bus_configurations() -> str:
    return await svc.list_configs()


@mcp.tool(
    name="assign_matrix_to_bus_config",
    description=(
        "Assign communication matrix elements (clusters, ECUs, PDUs, or signals) to a bus configuration. "
        "First use find_matrix_elements or list_matrices to find the element_name. "
        "Provide bus_config_name and either element_name, element_type, or matrix_xpath. "
        "Use matrix_xpath for exact PDU/signal assignment when the user or use case names a specific matrix element and you need to keep that narrow scope. "
        "Do NOT widen exact PDU/signal requests to assign_ecu_to_bus_config unless whole-ECU population was explicitly requested. "
        "Use the optional `part` argument to scope the assignment to a single bus configuration part: "
        "'simulated' (Simulated ECUs), 'inspection', or 'manipulation'. Omit `part` (or pass 'all') "
        "to assign to all three parts at once. "
        "Example: assign_matrix_to_bus_config(bus_config_name='BusConfig1', element_name='LIN/LinDoorCluster', part='simulated') "
        "to assign the LinDoorCluster to the Simulated ECUs part of BusConfig1. "
        'Example precise PDU scope: matrix_xpath=\'//*[@Name="GearboxInfoIPdu" and @Direction="TX" and ancestor::*[@Name="CentralGatewayEcu"]]\'.'
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "bus_config")
async def assign_matrix_to_bus_config(
    bus_config_name: Annotated[
        str,
        Field(
            description="Name of the target bus configuration, e.g. 'BusConfig1'",
        ),
    ],
    element_name: Annotated[
        str | None,
        Field(
            description="Name of the cluster, ECU, PDU, or signal to assign from the communication matrix. Use the path format from list_matrices for clusters, e.g. 'LIN/LinDoorCluster'. Prefer matrix_xpath for exact PDU/signal scope when names may repeat.",
        ),
    ] = None,
    element_type: Annotated[
        str | None,
        Field(
            description="Type of the matrix element: 'BusCluster', 'BusEcu', 'BusISignalIPdu', 'BusISignal', etc.",
        ),
    ] = None,
    matrix_xpath: Annotated[
        str | None,
        Field(
            description='Advanced: raw XPath to find matrix elements, e.g. \'//*[@Name="LinDoorCluster"]\' or \'//*[@Name="GearboxInfoIPdu" and @Direction="TX" and ancestor::*[@Name="CentralGatewayEcu"]]\' for precise PDU scope.',
        ),
    ] = None,
    part: Annotated[
        str | None,
        Field(
            description=(
                "Bus configuration part to assign to: 'simulated', 'inspection', "
                "'manipulation', or 'all' (default). 'all' assigns to all three parts."
            ),
        ),
    ] = None,
) -> str:
    return await svc.assign_matrix(
        bus_config_name,
        element_name,
        element_type,
        matrix_xpath,
        part,
    )


@mcp.tool(
    name="assign_ecu_to_bus_config",
    description=(
        "Assign ECU(s) from the communication matrix to a bus configuration for restbus simulation. "
        "This is the most common way to populate a bus configuration. "
        "Use assign_matrix_to_bus_config instead when the user names exact clusters, PDUs, or signals and wants to keep that narrow scope. "
        "Use ecu_names=['ECU_A','ECU_B'] for specific ECUs, or ecu_xpath='//BusEcu' for all ECUs. "
        "Exclude DUT ECUs with exclude_list='DUT_ECU,Tester'. "
        "Use the optional `part` argument to scope the assignment to a single bus configuration part: "
        "'simulated' (Simulated ECUs, default for restbus), 'inspection', or 'manipulation'. "
        "Omit `part` (or pass 'all') to assign to all three parts at once."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "bus_config")
async def assign_ecu_to_bus_config(
    bus_config_name: Annotated[
        str | None,
        Field(
            description="Target bus configuration name, e.g. 'CAN_Config_1'",
        ),
    ] = None,
    ecu_names: Annotated[
        list[str] | None,
        Field(
            description="List of ECU names to assign, e.g. ['ECU_A', 'ECU_B']",
        ),
    ] = None,
    ecu_xpath: Annotated[
        str | None,
        Field(
            description="Advanced: XPath to find ECUs, e.g. '//BusEcu'",
        ),
    ] = None,
    exclude_list: Annotated[
        str,
        Field(
            description="Comma-separated ECU names to exclude, e.g. 'Tester,Diagnostics'",
        ),
    ] = "",
    part: Annotated[
        str | None,
        Field(
            description=(
                "Bus configuration part to assign to: 'simulated', 'inspection', "
                "'manipulation', or 'all' (default). 'all' assigns to all three parts."
            ),
        ),
    ] = None,
) -> str:
    return await svc.assign_ecu(
        bus_config_name,
        ecu_names,
        ecu_xpath,
        exclude_list,
        part,
    )


@mcp.tool(
    name="add_feature_to_bus_element",
    description=(
        "Add a simulation feature to bus configuration elements (ECUs, PDUs, signals, controllers). "
        "FEATURE NAMES (use exact strings): "
        "- PDU-level: 'BusPduEnableAccess' (enable/disable TX PDUs), 'BusFrameAccess' (raw frame data), "
        "'BusPduRawDataAccess' (raw PDU bytes), 'BusPduTriggerAccess' (trigger transmission), "
        "'BusPduRxStatusAccess' (RX status), 'BusPduCyclicTimingControlAccess' (timing control), "
        "'BusPduUserCodeAccess' (custom code hooks), 'BusPduRxStatusInspection' (inspection RX status). "
        "- Signal-level: 'BusISignalValueAccess' (ISignal Value - most common), "
        "'BusCounterSignalAccess' (counter signals). "
        "- Controller-level: 'BusCommunicationControllerEnableAccess' (Communication Controller Enable), "
        "'BusCommunicationControllerLinScheduleTableAccess' (Lin Scheduling table). "
        "- Bus Config-level: 'BusConfigurationEnableAccess' (enable/disable entire config). "
        "- GTS (Global Time Sync): 'BusGtsTransmissionControlAccess', 'BusGtsTimeBaseDataAccess'. "
        "Scope with element_xpath like '//BusISignalIPdu[@Direction=\"TX\"]' for TX PDUs only."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "bus_config")
async def add_feature_to_bus_element(
    feature_name: Annotated[
        str,
        Field(
            description=(
                "Exact feature name string. Common values: "
                "'BusISignalValueAccess' (signal values - most common), "
                "'BusFrameAccess' (raw frame data), "
                "'BusPduEnableAccess' (enable/disable TX PDUs), "
                "'BusPduTriggerAccess' (trigger TX), "
                "'BusPduRawDataAccess' (raw PDU bytes), "
                "'BusPduRxStatusAccess' (RX status in Simulated ECUs), "
                "'BusPduRxStatusInspection' (RX status in Inspection), "
                "'BusCommunicationControllerEnableAccess' (controller enable), "
                "'BusCommunicationControllerLinScheduleTableAccess' (LIN schedule), "
                "'BusConfigurationEnableAccess' (config-level enable), "
                "'BusGtsTransmissionControlAccess' (GTS transmission), "
                "'BusGtsTimeBaseDataAccess' (GTS time base)"
            ),
        ),
    ],
    element_type: Annotated[
        str | None,
        Field(
            description=(
                "Type of target element(s). Values: 'BusISignal', 'BusISignalIPdu', "
                "'BusContainerIPdu', 'BusMultiplexedIPdu', "
                "'BusCanCommunicationController', 'BusLinCommunicationController', 'BusEcu'"
            ),
        ),
    ] = None,
    element_name: Annotated[
        str | None,
        Field(
            description="Name of target element(s) in the bus configuration, e.g. 'EngineData', 'ECU_A'",
        ),
    ] = None,
    bus_config_name: Annotated[
        str | None,
        Field(
            description="Scope to this bus configuration, e.g. 'CAN_Restbus'. If omitted, applies to all configs.",
        ),
    ] = None,
    element_xpath: Annotated[
        str | None,
        Field(
            description=(
                "XPath to find target elements. Examples: "
                "'//BusISignalIPdu[@Direction=\"TX\"]' (all TX PDUs), "
                "'//BusEcu[@Name=\"ECU_A\"]//BusISignal' (signals in specific ECU), "
                "'/BusConfiguration[@Name=\"MyConfig\"]/BusConfigurationPartSimulatedEcus//BusISignalIPdu'"
            ),
        ),
    ] = None,
) -> str:
    return await svc.add_feature(
        feature_name,
        element_type,
        element_name,
        bus_config_name,
        element_xpath,
    )


@mcp.tool(
    name="remove_bus_config_elements",
    description=(
        "Remove elements from bus configurations by name, type, or XPath query. "
        "Use element_type='BusEcu' with element_name='ECU_A' to remove a specific ECU, "
        "or xpath='//BusISignalIPdu[@Name=\"MyPdu\"]' for XPath-based removal. "
        "Removes the element and all its children (signals, features, function ports)."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "bus_config")
async def remove_bus_config_elements(
    element_name: Annotated[
        str | None,
        Field(
            description="Name of element(s) to remove, e.g. 'ECU_A'",
        ),
    ] = None,
    element_type: Annotated[
        str | None,
        Field(
            description="Type of element(s), e.g. 'BusEcu'",
        ),
    ] = None,
    xpath: Annotated[
        str | None,
        Field(
            description="Advanced: XPath override, e.g. '//BusEcu[@Name=ECU_A]'",
        ),
    ] = None,
) -> str:
    return await svc.remove_elements(
        element_name,
        element_type,
        xpath,
    )


@mcp.tool(
    name="generate_bus_containers",
    description=(
        "Generate Bus Simulation Containers (BSC) from the bus configurations. "
        "BSCs are compiled artifacts for explicit VEOS/BSC delivery or other user-requested "
        "container output. "
        "Do NOT call this just to inspect, list, or set function-port properties — "
        "assigned features already expose those ports for find_bus_config_elements and "
        "set_function_port_property. Do NOT use this as recovery for a failed "
        "set_function_port_property call. "
        "Call this only when the user explicitly asks to generate containers or BSC output, "
        "and only after assigning matrix elements, adding features, and configuring the bus settings "
        "that should be packaged."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "bus_config")
async def generate_bus_containers() -> str:
    return await svc.generate_containers()


@mcp.tool(
    name="find_bus_config_elements",
    description=(
        "Search for elements within bus configurations using name, type, or XPath. "
        "ELEMENT TYPES: 'BusConfiguration', 'BusEcu', 'BusISignalIPdu', 'BusContainerIPdu', "
        "'BusMultiplexedIPdu', 'BusISignal', 'BusCanCommunicationController', "
        "'BusLinCommunicationController', 'FunctionPort', 'BusFrame'. "
        "XPATH EXAMPLES: "
        "'//BusEcu' (all ECUs), "
        "'/BusConfiguration[@Name=\"MyConfig\"]/BusConfigurationPartSimulatedEcus//BusISignalIPdu' (PDUs in simulated ECUs), "
        "'//BusISignalIPdu[@Direction=\"TX\"]' (all TX PDUs), "
        "'//BusISignal[@Name=\"EngineSpeed\"]' (signal by name). "
        "Returns element names, types, and paths. Results are paginated; call again with "
        "next_offset to retrieve later pages."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "bus_config")
async def find_bus_config_elements(
    element_type: Annotated[
        str | None,
        Field(
            description="Type of elements to find, e.g. 'BusFrame'",
        ),
    ] = None,
    element_name: Annotated[
        str | None,
        Field(
            description="Name to search for, e.g. 'EngineData'",
        ),
    ] = None,
    xpath: Annotated[
        str | None,
        Field(
            description="Advanced: XPath override, e.g. '//BusFrame'",
        ),
    ] = None,
    offset: Annotated[
        int,
        Field(
            ge=0,
            description="Zero-based result offset. Use next_offset from the previous response.",
        ),
    ] = 0,
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=MAX_PAGE_LIMIT,
            description="Maximum results per page. Defaults to 100; maximum 1000.",
        ),
    ] = DEFAULT_PAGE_LIMIT,
) -> str:
    return await svc.find_elements(
        element_type,
        element_name,
        xpath,
        offset,
        limit,
    )


@mcp.tool(
    name="assign_bus_config_to_application_process",
    description="Assign a bus configuration to an application process",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "bus_config", "application_process")
async def assign_bus_config_to_application_process(
    bus_config_name: Annotated[
        str,
        Field(
            description="Name of the bus configuration, e.g. 'CAN_Config_1'",
        ),
    ],
    process_name: Annotated[
        str | None,
        Field(
            description="Application process name, e.g. 'AppProcess_1'",
        ),
    ] = None,
) -> str:
    return await svc.assign_to_application_process(
        bus_config_name,
        process_name,
    )


@mcp.tool(
    name="set_function_port_property",
    description=(
        "Set a property on function ports of bus configuration features. "
        "Do NOT generate bus containers just to use this tool; if the relevant features "
        "are already assigned, inspect ports with find_bus_config_elements and set them directly. "
        "If this tool reports missing property nodes or zero ports updated, re-run "
        "find_bus_config_elements to verify the actual function-port names/XPath and the "
        "assigned bus features. Do NOT use generate_bus_containers as recovery for a "
        "failed property write. "
        "Each property has a strict value type: bool properties "
        "('IsMappable', 'IsTestAutomationSupportEnabled') require true/false; "
        "float properties ('InitialValue', 'InitialSubstituteValue', "
        "'StopValue') require a numeric value such as 1.0 — never true/false; "
        "int properties ('InitialSwitchSetting', 'InitialValueUsage', "
        "'StoppedStatusOutput', 'Access_mode') require an integer enum code. "
        "Canonical API names and GUI labels "
        "('Model access', 'Activate test automation support', "
        "'Initial value', 'Initial switch setting', 'Initial substitute "
        "value', 'Initial value usage', 'Stop value', 'Stopped status "
        "output', 'Access mode') are both accepted. "
        "See configurationdesk://reference/function-port-properties for the "
        "full catalog including the expected value type and a concrete "
        "example for every property. Use bus_config_name to scope to a "
        "specific configuration, feature_type as a coarse feature selector "
        "(logical aliases such as 'ISignalValue' and 'LinSchedulingTable' are resolved "
        "to concrete feature nodes internally), and port_xpath when the workflow names exact "
        "function ports and you need precise targeting."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "bus_config")
async def set_function_port_property(
    property_name: Annotated[
        str,
        Field(
            description=(
                "Property name. Canonical API names or GUI labels are "
                "accepted (case- and whitespace-insensitive). Common ones: "
                "'IsMappable' / 'Model access', "
                "'IsTestAutomationSupportEnabled' / 'Activate test "
                "automation support', 'InitialValue' / 'Initial value', "
                "'InitialSwitchSetting' / 'Initial switch setting', "
                "'InitialSubstituteValue' / 'Initial substitute value'. "
                "See resource configurationdesk://reference/"
                "function-port-properties for the full catalog."
            ),
        ),
    ],
    value: Annotated[
        StrictPropertyValue,
        Field(
            description=(
                "Value to assign. ALWAYS read the property's required type "
                "before choosing — do NOT default to true. If the instruction "
                "says a number (e.g. 'set Initial value to 1'), pass a number "
                "(value=1), never value=true.\n"
                "  float (numeric)   : 'InitialValue' e.g. value=1.0, "
                "'InitialSubstituteValue' e.g. value=0.0, "
                "'StopValue' e.g. value=0.0.\n"
                "  int   (enum code) : 'InitialSwitchSetting' "
                "(0=Substitute value, 1=I/O signal, 2=Model signal), "
                "'InitialValueUsage' (0=each start, 1=first start), "
                "'StoppedStatusOutput' (0=stop value, 1=keep last), "
                "'Access_mode' (0=Read, 2=Write).\n"
                "  bool  (true/false): 'IsMappable', "
                "'IsTestAutomationSupportEnabled'.\n"
                "  str               : 'Description', 'Name'."
            ),
        ),
    ],
    bus_config_name: Annotated[
        str | None,
        Field(
            description="Scope to this bus configuration, e.g. 'BusConfig1'",
        ),
    ] = None,
    feature_type: Annotated[
        str | None,
        Field(
            description=(
                "Coarse feature selector, e.g. 'ISignalValue', 'LinSchedulingTable', "
                "or a concrete feature node such as 'BusISignalValueAccess'. "
                "Prefer port_xpath when exact function-port names are known."
            ),
        ),
    ] = None,
    port_xpath: Annotated[
        str | None,
        Field(
            description="Advanced: full XPath to specific port properties",
        ),
    ] = None,
) -> str:
    return await svc.set_function_port_property(
        property_name,
        value,
        bus_config_name,
        feature_type,
        port_xpath,
    )


@mcp.tool(
    name="set_bus_config_element_property",
    description=(
        "Set a property on bus configuration elements or feature nodes. "
        "USE THIS for bus feature and manipulation properties such as "
        "'Countdown start value', 'Length', 'Feature switch', 'Overwrite value', "
        "'Offset value', or feature-node 'Enable'. "
        "NOT for function ports — use set_function_port_property. "
        "NOT for hardware I/O blocks — use set_io_function_block_property. "
        "Prefer xpath for duplicated nodes (for example TX/RX PDUs or repeated "
        "signal names). See configurationdesk://reference/bus-element-properties "
        "for common property names and example values."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@with_preconditions("connection", "project", "application", "bus_config")
async def set_bus_config_element_property(
    property_name: Annotated[
        str,
        Field(
            description=(
                "Property name on the target bus configuration element or feature "
                "node. Common values: 'Countdown start value', 'Length', "
                "'Feature switch', 'Overwrite value', 'Offset value', 'Enable'."
            ),
        ),
    ],
    value: Annotated[
        StrictPropertyValue,
        Field(
            description=(
                "Value to assign. Examples: 15 for 'Countdown start value', 1 "
                "for 'Length' or 'Feature switch', 255 for 'Overwrite value', "
                "3 for 'Offset value', false for 'Recalculate SecOC information'."
            ),
        ),
    ],
    element_name: Annotated[
        str | None,
        Field(
            description="Target element or feature node name, e.g. 'Frame Length' or 'CarLockControlIPdu'",
        ),
    ] = None,
    element_type: Annotated[
        str | None,
        Field(
            description="Optional target element type, e.g. 'BusFrameLengthManipulation', 'BusFeatureSwitch', 'BusISignalIPdu'",
        ),
    ] = None,
    xpath: Annotated[
        str | None,
        Field(
            description="Preferred precise XPath for duplicate names, e.g. '//BusFrameLengthManipulation[ancestor::*[@Name=\"CarLockControlIPdu\"]]'",
        ),
    ] = None,
    bus_config_name: Annotated[
        str | None,
        Field(
            description="Optional bus configuration scope, e.g. 'Restbus_BusConfiguration'",
        ),
    ] = None,
    allow_multiple: Annotated[
        bool,
        Field(
            description="Apply to every matched element. Default false to avoid accidental broad edits.",
        ),
    ] = False,
) -> str:
    return await svc.set_bus_config_element_property(
        property_name,
        value,
        element_name,
        element_type,
        xpath,
        bus_config_name,
        allow_multiple,
    )
