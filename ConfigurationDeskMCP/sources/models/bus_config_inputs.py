# -*- coding: utf-8 -*-
"""Pydantic input models for bus configuration tools."""

from typing import List, Optional

from pydantic import BaseModel, Field

from sources.models.property_values import StrictPropertyValue


class CreateBusConfigurationInput(BaseModel):
    name: Optional[str] = Field(
        default=None, description="Name for the new bus configuration, e.g. 'BusConfig1'"
    )


class RemoveBusConfigurationInput(BaseModel):
    name: str = Field(
        description="Name or wildcard pattern of bus configuration(s) to remove, e.g. 'BusConfig1' or 'Bus*'"
    )


class ListBusConfigurationsInput(BaseModel):
    pass


class AssignMatrixInput(BaseModel):
    bus_config_name: str = Field(
        description="Name of the target bus configuration, e.g. 'BusConfig1'"
    )
    element_name: Optional[str] = Field(
        default=None,
        description="Name of the cluster or ECU to assign from the communication matrix. Use the path format from list_matrices, e.g. 'LIN/LinDoorCluster'",
    )
    element_type: Optional[str] = Field(
        default=None, description="Type of the matrix element: 'BusCluster', 'BusEcu', etc."
    )
    matrix_xpath: Optional[str] = Field(
        default=None,
        description="Advanced: raw XPath to find matrix elements, e.g. '//*[@Name=\"LinDoorCluster\"]'",
    )


class AssignEcuInput(BaseModel):
    bus_config_name: Optional[str] = Field(
        default=None, description="Target bus configuration name, e.g. 'CAN_Config_1'"
    )
    ecu_names: Optional[List[str]] = Field(
        default=None, description="List of ECU names to assign, e.g. ['ECU_A', 'ECU_B']"
    )
    ecu_xpath: Optional[str] = Field(
        default=None, description="Advanced: XPath to find ECUs, e.g. '//BusEcu'"
    )
    exclude_list: str = Field(
        default="", description="Comma-separated ECU names to exclude, e.g. 'Tester,Diagnostics'"
    )


class AddFeatureInput(BaseModel):
    feature_name: str = Field(
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
        )
    )
    element_type: Optional[str] = Field(
        default=None,
        description=(
            "Type of target element(s). Values: 'BusISignal', 'BusISignalIPdu', "
            "'BusContainerIPdu', 'BusMultiplexedIPdu', "
            "'BusCanCommunicationController', 'BusLinCommunicationController', 'BusEcu'"
        ),
    )
    element_name: Optional[str] = Field(
        default=None,
        description="Name of target element(s) in the bus configuration, e.g. 'EngineData', 'ECU_A'",
    )
    bus_config_name: Optional[str] = Field(
        default=None,
        description="Scope to this bus configuration, e.g. 'CAN_Restbus'. If omitted, applies to all configs.",
    )
    element_xpath: Optional[str] = Field(
        default=None,
        description=(
            "XPath to find target elements. Examples: "
            "'//BusISignalIPdu[@Direction=\"TX\"]' (all TX PDUs), "
            "'//BusEcu[@Name=\"ECU_A\"]//BusISignal' (signals in specific ECU), "
            "'/BusConfiguration[@Name=\"MyConfig\"]/BusConfigurationPartSimulatedEcus//BusISignalIPdu'"
        ),
    )


class RemoveBusConfigElementsInput(BaseModel):
    element_name: Optional[str] = Field(
        default=None, description="Name of element(s) to remove, e.g. 'ECU_A'"
    )
    element_type: Optional[str] = Field(
        default=None, description="Type of element(s), e.g. 'BusEcu'"
    )
    xpath: Optional[str] = Field(
        default=None, description="Advanced: XPath override, e.g. '//BusEcu[@Name=ECU_A]'"
    )


class GenerateContainersInput(BaseModel):
    pass


class FindBusConfigElementsInput(BaseModel):
    element_type: Optional[str] = Field(
        default=None, description="Type of elements to find, e.g. 'BusFrame'"
    )
    element_name: Optional[str] = Field(
        default=None, description="Name to search for, e.g. 'EngineData'"
    )
    xpath: Optional[str] = Field(
        default=None, description="Advanced: XPath override, e.g. '//BusFrame'"
    )


class AssignToApplicationProcessInput(BaseModel):
    bus_config_name: str = Field(description="Name of the bus configuration, e.g. 'CAN_Config_1'")
    process_name: Optional[str] = Field(
        default=None, description="Application process name, e.g. 'AppProcess_1'"
    )


class SetFunctionPortPropertyInput(BaseModel):
    property_name: str = Field(
        description="Property name: 'IsMappable' (enable port mapping) or 'IsTestAutomationSupportEnabled' (enable real-time testing)"
    )
    value: StrictPropertyValue = Field(
        description=(
            "Property value. Use true/false for bool properties like 'IsMappable' or "
            "'IsTestAutomationSupportEnabled'; use numbers for numeric properties like "
            "'InitialValue' or 'InitialSwitchSetting'; use strings for text properties "
            "like 'Description'."
        )
    )
    bus_config_name: Optional[str] = Field(
        default=None, description="Scope to this bus configuration, e.g. 'BusConfig1'"
    )
    feature_type: Optional[str] = Field(
        default=None,
        description=(
            "Coarse feature selector, e.g. 'ISignalValue', 'LinSchedulingTable', or a concrete "
            "feature node such as 'BusISignalValueAccess'. Prefer port_xpath when exact function "
            "ports are named in the workflow."
        ),
    )
    port_xpath: Optional[str] = Field(
        default=None, description="Advanced: full XPath to specific port properties"
    )


class ConnectFunctionPortsToModelPortsInput(BaseModel):
    bus_config_name: Optional[str] = Field(
        default=None, description="Bus configuration name, or all if omitted, e.g. 'CAN_Config_1'"
    )
    auto: bool = Field(default=True, description="Use automatic connection algorithm, e.g. true")


class ConnectPortsInput(BaseModel):
    source_xpath: str = Field(
        description="XPath to the source port, e.g. '//FunctionPort[@Name=Tx]'"
    )
    target_xpath: str = Field(
        description="XPath to the target port, e.g. '//ModelPort[@Name=CAN_In]'"
    )
    remove_existing_links: bool = Field(
        default=True, description="Remove existing links before connecting, e.g. true"
    )
