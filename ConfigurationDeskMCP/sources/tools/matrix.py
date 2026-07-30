# -*- coding: utf-8 -*-
"""Communication matrix tools for ConfigurationDesk MCP Server."""

from typing import Annotated

from pydantic import Field

from sources.models.property_values import StrictPropertyValue
from sources.server.app import mcp
from sources.services._pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT
from sources.services import matrix_service as svc


@mcp.tool(
    name="add_communication_matrix",
    description=(
        "Add a communication matrix file to the project. Supported formats: "
        "ARXML (AUTOSAR, .arxml), DBC (Vector CAN, .dbc), LDF (LIN Description, .ldf). "
        "The matrix defines the bus network: clusters (CAN/LIN/Ethernet/FlexRay), ECUs, "
        "frames, PDUs, and signals. After adding: "
        "1. Use list_matrices to see clusters and ECUs. "
        "2. Use find_matrix_elements to locate specific elements. "
        "3. Use assign_ecu_to_bus_config to assign ECUs for restbus simulation. "
        "Multiple matrices can be loaded simultaneously (e.g., different bus systems)."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def add_communication_matrix(
    path: Annotated[
        str,
        Field(
            description="Absolute path to matrix file. Formats: .arxml (AUTOSAR), .dbc (CAN), .ldf (LIN). E.g. 'D:/Databases/vehicle_can.arxml'",
        ),
    ],
) -> str:
    return await svc.add_communication_matrix(path)


@mcp.tool(
    name="remove_communication_matrix",
    description=(
        "Remove a communication matrix from the project. Provide the matrix name or use "
        "xpath to target specific matrices. Set force=true to remove even if elements are "
        "assigned to bus configurations. Removing a matrix removes all its clusters, ECUs, "
        "frames, and signals from the project."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def remove_communication_matrix(
    name: Annotated[
        str | None,
        Field(
            description="Name of the matrix to remove as shown by list_matrices, e.g. 'powertrain'",
        ),
    ] = None,
    xpath: Annotated[
        str | None,
        Field(
            description="Advanced: XPath to target specific matrix elements",
        ),
    ] = None,
    force: Annotated[
        bool,
        Field(
            description="Force removal even if matrix elements are assigned to bus configurations",
        ),
    ] = False,
) -> str:
    return await svc.remove_communication_matrix(name, xpath, force)


@mcp.tool(
    name="list_matrices",
    description=(
        "List all loaded communication matrices showing two views: "
        "1. BY CLUSTERS: Cluster → PhysicalChannel → Frames/PDUs hierarchy. "
        "2. BY ECUs: ECU → TX/RX → PDUs → Signals hierarchy. "
        "Use the cluster view to understand network topology. "
        "Use the ECU view to identify which ECUs send/receive which PDUs. "
        "Element paths from this output can be used in assign_matrix_to_bus_config. "
        "Each view is paginated; call again with next_offset to retrieve later pages."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def list_matrices(
    offset: Annotated[
        int,
        Field(
            ge=0,
            description="Zero-based result offset for both views. Use next_offset from the previous response.",
        ),
    ] = 0,
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=MAX_PAGE_LIMIT,
            description="Maximum results per view and page. Defaults to 100; maximum 1000.",
        ),
    ] = DEFAULT_PAGE_LIMIT,
) -> str:
    return await svc.list_matrices(offset, limit)


@mcp.tool(
    name="find_matrix_elements",
    description=(
        "Search communication matrix elements by name, type, or XPath. "
        "VIEW: 'clusters' (default, by cluster hierarchy) or 'ecus' (by ECU hierarchy). "
        "ELEMENT TYPES: Prefer user-friendly values like 'cluster', 'ecu', 'pdu', 'frame', or 'signal'. "
        "The server also accepts ConfigurationDesk type names such as 'BusCanCommunicationCluster', 'BusEcu', 'BusISignalIPdu', or 'BusISignal'. "
        "XPATH EXAMPLES: "
        "'//BusEcu' (all ECUs), "
        "'//BusCanCommunicationCluster' (all CAN clusters), "
        "'//BusEcu[@Name=\"ECU_A\"]' (specific ECU), "
        "'//BusISignalIPdu[@Direction=\"TX\"]' (all TX PDUs), "
        "'//BusISignal[@Name=\"EngineSpeed\"]' (signal by name). "
        "PROPERTY ACCESS: Results include properties like Direction, Name, Length. "
        "Results are paginated; call again with next_offset to retrieve later pages."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def find_matrix_elements(
    element_type: Annotated[
        str | None,
        Field(
            description="Element type filter. Prefer 'cluster', 'ecu', 'pdu', 'frame', or 'signal'.",
        ),
    ] = None,
    element_name: Annotated[
        str | None,
        Field(
            description="Name to search for, e.g. 'EngineData', 'ECU_A', or 'PowertrainCAN'",
        ),
    ] = None,
    xpath: Annotated[
        str | None,
        Field(
            description="Advanced: XPath query for direct lookup",
        ),
    ] = None,
    view: Annotated[
        str,
        Field(
            description="Search view: 'clusters' (default) or 'ecus'",
        ),
    ] = "clusters",
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
    return await svc.find_matrix_elements(
        element_type,
        element_name,
        xpath,
        view,
        offset,
        limit,
    )


@mcp.tool(
    name="set_matrix_element_property",
    description=(
        "Set a property on communication-matrix elements such as PDUs, frames, "
        "signals, or ECUs. USE THIS for matrix-level properties like 'Length', "
        "'Initial value', or 'Unused bit pattern'. NOT for bus configuration "
        "feature nodes — use set_bus_config_element_property. NOT for function "
        "ports — use set_function_port_property. Prefer xpath when names are "
        "duplicated across TX/RX or multiple ECUs."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def set_matrix_element_property(
    property_name: Annotated[
        str,
        Field(
            description="Matrix element property name, e.g. 'Length', 'Initial value', or 'Unused bit pattern'.",
        ),
    ],
    value: Annotated[
        StrictPropertyValue,
        Field(
            description="Value to assign. Examples: 1 for 'Length', 1 for 'Initial value', 0 for 'Unused bit pattern'.",
        ),
    ],
    element_name: Annotated[
        str | None,
        Field(
            description="Target matrix element name, e.g. 'DoorLeftStatusCanIPdu' or 'SpeedISignal'",
        ),
    ] = None,
    element_type: Annotated[
        str | None,
        Field(
            description="Optional target element type, e.g. 'pdu', 'frame', 'signal', 'ecu' or a ConfigurationDesk type name.",
        ),
    ] = None,
    xpath: Annotated[
        str | None,
        Field(
            description='Precise XPath for duplicate elements, e.g. \'//*[@Name="DoorLeftStatusCanIPdu" and @Direction="TX"]\'',
        ),
    ] = None,
    view: Annotated[
        str,
        Field(
            description="Matrix view to search first: 'clusters' (default) or 'ecus'",
        ),
    ] = "clusters",
    allow_multiple: Annotated[
        bool,
        Field(
            description="Apply to every matched matrix element. Default false to avoid accidental broad edits.",
        ),
    ] = False,
) -> str:
    return await svc.set_matrix_element_property(
        property_name,
        value,
        element_name,
        element_type,
        xpath,
        view,
        allow_multiple,
    )
