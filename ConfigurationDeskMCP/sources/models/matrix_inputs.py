# -*- coding: utf-8 -*-
"""Pydantic input models for communication matrix tools."""

from typing import Optional

from pydantic import BaseModel, Field


class AddCommunicationMatrixInput(BaseModel):
    path: str = Field(
        description="Absolute path to matrix file. Formats: .arxml (AUTOSAR), .dbc (CAN), .ldf (LIN). E.g. 'D:/Databases/vehicle_can.arxml'"
    )


class RemoveCommunicationMatrixInput(BaseModel):
    name: Optional[str] = Field(
        default=None,
        description="Name of the matrix to remove (as shown by list_matrices), e.g. 'powertrain'",
    )
    xpath: Optional[str] = Field(
        default=None,
        description="XPath to target specific matrix, e.g. '//BusCommunicationMatrix[@Name=\"powertrain\"]'",
    )
    force: bool = Field(
        default=False,
        description="Force removal even if matrix elements are assigned to bus configurations",
    )


class ListMatricesInput(BaseModel):
    pass


class FindMatrixElementsInput(BaseModel):
    element_type: Optional[str] = Field(
        default=None,
        description=(
            "Element type filter. Values: 'BusCommunicationCluster', 'BusCanCommunicationCluster', "
            "'BusLinCommunicationCluster', 'BusEcu', 'BusISignalIPdu', 'BusContainerIPdu', "
            "'BusMultiplexedIPdu', 'BusISignal', 'BusFrame'"
        ),
    )
    element_name: Optional[str] = Field(
        default=None,
        description="Name to search for, supports wildcards. E.g. 'EngineData', 'ECU_*', 'Signal_Speed'",
    )
    xpath: Optional[str] = Field(
        default=None,
        description=(
            "XPath query. Examples: '//BusEcu' (all ECUs), "
            "'//BusCanCommunicationCluster' (CAN clusters), "
            "'//BusEcu[@Name=\"ECU_A\"]//BusISignalIPdu' (ECU's PDUs), "
            "'//BusISignal[@Name=\"EngineSpeed\"]' (signal by name)"
        ),
    )
    view: str = Field(
        default="clusters",
        description="Search view: 'clusters' (by cluster hierarchy) or 'ecus' (by ECU hierarchy)",
    )
