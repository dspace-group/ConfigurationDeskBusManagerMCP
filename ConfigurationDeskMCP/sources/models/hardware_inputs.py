# -*- coding: utf-8 -*-
"""Pydantic input models for hardware management tools."""

from typing import List

from pydantic import BaseModel, Field


class AddHardwarePlatformInput(BaseModel):
    ip_addresses: List[str] = Field(
        description="Address(es) of the platform to register, e.g. ['192.0.2.10']. VEOS is NOT a platform - do not use this for VEOS."
    )
    platform_type: str = Field(
        default="SCALEXIO",
        description="Platform type: 'SCALEXIO', 'MicroAutoBox III', or 'MicroLabBox II'. VEOS is NOT a platform - use add_application_processing_unit / generate_bus_containers instead.",
    )


class ImportHardwareTopologyInput(BaseModel):
    path: str = Field(
        description="Path to the hardware topology file (.htfx), e.g. 'C:/HW/topology.htfx'"
    )


class ScanHardwareInput(BaseModel):
    platform_name: str = Field(
        description="Unique name of the registered platform to scan, e.g. 'SCALEXIO Processing Unit at 192.0.2.10'"
    )


class RemoveHardwareInput(BaseModel):
    name: str = Field(
        description="Name or wildcard pattern of hardware element(s) to remove, e.g. 'SCALEXIO*'"
    )


class ListPlatformsInput(BaseModel):
    pass


class RefreshPlatformsInput(BaseModel):
    pass


class AddHardwareElementInput(BaseModel):
    element_type: str = Field(description="Type of hardware element to add, e.g. 'DS6311'")


class CreateEmptyHardwareTopologyInput(BaseModel):
    name: str = Field(
        default="EmptyTopology", description="Display name for the empty hardware topology"
    )
