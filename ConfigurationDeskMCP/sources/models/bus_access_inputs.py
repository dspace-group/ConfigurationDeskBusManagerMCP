# -*- coding: utf-8 -*-
"""Pydantic input models for bus access tools."""

from typing import Optional

from pydantic import BaseModel, Field


class CreateBusFunctionBlockInput(BaseModel):
    name: str = Field(
        description="Descriptive name for the function block, e.g. 'CAN_Engine', 'LIN_Door', 'CANFD_Body'. Use cluster or channel name."
    )
    bus_type: str = Field(
        default="CAN", description="Bus type: 'CAN' (for CAN and CAN-FD), 'LIN', or 'Ethernet'"
    )


class SetBusFunctionBlockPropertyInput(BaseModel):
    function_block_name: str = Field(
        description="Name of the function block to configure, e.g. 'CAN_Engine'"
    )
    property_name: str = Field(
        description="Property name. Common: 'BaudRate' (CAN:500000, LIN:19200), 'DataPhaseBaudRate' (CAN-FD:2000000/4000000), 'Termination' (0/1)"
    )
    value: str = Field(
        description="Property value as string, e.g. '500000', '19200', '4000000', '0'"
    )
    bus_type: str = Field(default="CAN", description="Bus type: 'CAN', 'LIN', or 'Ethernet'")


class ListBusFunctionBlockPropertiesInput(BaseModel):
    function_block_name: str = Field(
        description="Name of the function block, e.g. 'CanPowertrainCluster'"
    )
    bus_type: str = Field(default="CAN", description="Bus type, e.g. 'CAN'")


class ListBusAccessRequestsInput(BaseModel):
    bus_config_name: Optional[str] = Field(
        default=None, description="Limit to a specific bus configuration, e.g. 'CAN_Config_1'"
    )


class AssignBusAccessInput(BaseModel):
    function_block_name: str = Field(
        description="Name of the function block to assign bus access requests to, e.g. 'LinDoorFB'"
    )
    bus_config_name: Optional[str] = Field(
        default=None, description="Limit to a specific bus configuration, e.g. 'BusConfig1'"
    )
    cluster_name: Optional[str] = Field(
        default=None, description="Limit to a specific communication cluster, e.g. 'LinDoorCluster'"
    )


class ListAssignableChannelSetsInput(BaseModel):
    function_block_name: str = Field(
        description="Name of the function block, e.g. 'CanPowertrainCluster'"
    )
    bus_type: str = Field(default="CAN", description="Bus type, e.g. 'CAN'")


class AssignChannelSetInput(BaseModel):
    function_block_name: str = Field(
        description="Name of the function block, e.g. 'CanPowertrainCluster'"
    )
    channel_set_index: int = Field(default=0, description="Index of the channel set, e.g. 0")
    bus_type: str = Field(default="CAN", description="Bus type, e.g. 'CAN'")


class AutoAssignChannelSetInput(BaseModel):
    function_block_name: str = Field(
        description="Name of the function block, e.g. 'CanPowertrainCluster'"
    )
    bus_type: str = Field(default="CAN", description="Bus type, e.g. 'CAN'")


class AssignHardwareAutomaticallyInput(BaseModel):
    pass


class ConnectIoFunctionBlocksToModelPortsInput(BaseModel):
    pass


class CreatePreconfiguredApplicationProcessInput(BaseModel):
    model_name: str = Field(
        description="Name of the model to create a pre-configured application process for, e.g. 'demosmd_io'"
    )
