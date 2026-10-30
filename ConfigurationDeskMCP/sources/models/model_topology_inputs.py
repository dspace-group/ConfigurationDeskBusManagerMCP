# -*- coding: utf-8 -*-
"""Pydantic input models for model topology tools."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from sources.services._pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT


class AddModelInput(BaseModel):
    path: str = Field(
        description="Path to the model file (.slx, .mdl, .sic, .bsc, or .fmu), e.g. 'C:/Models/Restbus_Model_64-bit.sic'"
    )
    analyze: bool = Field(
        default=True,
        description="Analyze model after adding. Set false for .sic/.bsc/.fmu files, e.g. true",
    )
    create_preconfigured: bool = Field(
        default=True,
        description=(
            "Whether to create a pre-configured application process. "
            "If true, a new application process with the same name as the model file (without extension) is created."
            "Set to false to only add the model to the model topology and to assingn the model to an existing application process manually."
        ),
    )


class ReplaceModelInput(BaseModel):
    path: str = Field(
        description="Path to the replacement model file, e.g. 'C:/Models/Controller_v2.slx'"
    )
    model_name: Optional[str] = Field(
        default=None,
        description="Name of the model to replace. If omitted, replaces by file match, e.g. 'Controller'",
    )
    analyze: bool = Field(default=True, description="Analyze model after replacing, e.g. true")


class RemoveModelInput(BaseModel):
    name: str = Field(description="Name of the model to remove, e.g. 'Controller'")


class AnalyzeModelsInput(BaseModel):
    pass


class CreateApplicationProcessInput(BaseModel):
    """Compatibility wrapper for hosts that nest tool arguments under `input`."""

    name: Optional[str] = Field(
        default=None,
        description="Optional name for the new application process, e.g. 'Restbus_ApplicationProcess'",
    )
    provide_default_task: Optional[bool] = Field(
        default=None,
        description=(
            "true = create the periodic default task; false = bare application process. "
            "Omit only when the request says nothing about a default task."
        ),
    )
    bus_config_names: Optional[list[str]] = Field(
        default=None,
        description=(
            "Bus configurations to assign the application process to. Omit = all existing ones, "
            "empty list = skip assignment."
        ),
    )
    processing_unit_application: Optional[str] = Field(
        default=None,
        description=(
            "Processing unit application that hosts the application process. Omit = create one "
            "if none exists, use the only one, or ask the user when several exist."
        ),
    )


class ListModelsInput(BaseModel):
    pass


class AddModelToSignalChainInput(BaseModel):
    model_name: str = Field(
        description="Name of the model whose ALL model port blocks should be added to the signal chain (e.g. 'SineWaves'). No port_block_name is used — all model port blocks are exposed at once."
    )


class AddModelPortBlockToSignalChainInput(BaseModel):
    model_name: str = Field(
        description="Name of the model that contains the target model port block (e.g. 'SineWaves')."
    )
    port_block_name: str = Field(
        description="Name of the ONE specific model port block to add to the signal chain (e.g. 'Sine_t'), or its hierarchy path when the name exists at several hierarchy levels (e.g. 'SineWaves/Subsystem/Sine_t'; prefix the model name to address a root-level block exactly). Use list_model_port_blocks to discover valid names."
    )


class ListModelPortBlocksInput(BaseModel):
    model_name: str = Field(
        description="Name of the model whose model port block names should be listed, e.g. 'SineWaves'"
    )


class ListModelPortsInput(BaseModel):
    model_name: str = Field(
        description="Name of the model whose model ports should be listed, e.g. 'SineWaves'"
    )
    port_block_name: Optional[str] = Field(
        default=None,
        description="Optional model port block to restrict the listing to (e.g. 'Sine_t' or the hierarchy path 'SineWaves/Subsystem/Sine_t'). A bare name lists the matching blocks at every hierarchy level. Omit to list the model ports of every model port block. Use list_model_port_blocks to discover valid names.",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Zero-based offset into `leaf_ports`, e.g. 0. Use `leaf_ports_page.next_offset` from the previous response.",
    )
    limit: int = Field(
        default=DEFAULT_PAGE_LIMIT,
        ge=1,
        le=MAX_PAGE_LIMIT,
        description="Maximum `leaf_ports` entries per page, e.g. 100. Defaults to 100; maximum 1000. `ports` is not paginated.",
    )


class ConnectModelPortToModelPortInput(BaseModel):
    source_model_name: str = Field(
        description="Model that contains the source model port, e.g. 'masterAppl'"
    )
    source_port_block_name: str = Field(
        description="Model port block of the source port: bare name or hierarchy path, e.g. 'Data Outport1' or 'masterAppl/Subsystem/Data Outport1'. Use list_model_port_blocks to discover valid names."
    )
    source_port_path: str = Field(
        description="Path of the source port inside its model port block; separate nested port groups with '/', e.g. 'data1' or 'Group1/Group2/Speed'. Use `port_path` from `leaf_ports` of list_model_ports."
    )
    target_model_name: str = Field(
        description="Model that contains the target model port, e.g. 'slaveAppl'"
    )
    target_port_block_name: str = Field(
        description="Model port block of the target port: bare name or hierarchy path, e.g. 'Data Inport1'. Use list_model_port_blocks to discover valid names."
    )
    target_port_path: str = Field(
        description="Path of the target port inside its model port block, e.g. 'data1' or 'Group1/Speed'. Use `port_path` from `leaf_ports` of list_model_ports."
    )


PortBlockDirection = Literal["inport", "outport"]


class ConnectModelPortBlockToModelPortBlockInput(BaseModel):
    source_model_name: str = Field(description="Model of the first side, e.g. 'SenderModel'")
    source_port_block_name: str = Field(
        description="Model port block of the first side: bare name or hierarchy path, e.g. 'Data Outport'. Use list_model_port_blocks to discover valid names."
    )
    source_group_path: str = Field(
        default="",
        description="Optional port group inside that block, separated by '/', e.g. 'StrucPort/SineWaveBus1'. Empty = the whole model port block. Must not point to a single port.",
    )
    source_port_block_direction: Optional[PortBlockDirection] = Field(
        default=None,
        description="Optional: 'inport' or 'outport'. Only needed when several blocks with this name exist at the same hierarchy level (e.g. the inport and outport blocks of an FMU).",
    )
    target_model_name: str = Field(description="Model of the second side, e.g. 'ReceiverModel'")
    target_port_block_name: str = Field(
        description="Model port block of the second side: bare name or hierarchy path, e.g. 'Data Inport'."
    )
    target_group_path: str = Field(
        default="",
        description="Optional port group inside that block, e.g. 'StrucPort/SineWaveBus1'. Empty = the whole model port block. Must not point to a single port.",
    )
    target_port_block_direction: Optional[PortBlockDirection] = Field(
        default=None,
        description="Optional: 'inport' or 'outport'. Only needed when several blocks with this name exist at the same hierarchy level.",
    )
