# -*- coding: utf-8 -*-
"""Pydantic input models for model topology tools."""

from typing import Optional

from pydantic import BaseModel, Field


class AddModelInput(BaseModel):
    path: str = Field(
        description="Path to the model file (.slx, .mdl, .sic, or .bsc), e.g. 'C:/Models/Restbus_Model_64-bit.sic'"
    )
    analyze: bool = Field(
        default=True,
        description="Analyze model after adding. Set false for .sic/.bsc files, e.g. true",
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
    pass


class ListModelsInput(BaseModel):
    pass


class AddModelToSignalChainInput(BaseModel):
    model_name: str = Field(
        description="Name of the model whose ALL ports should be added to the signal chain (e.g. 'SineWaves'). No port_name is used — all ports are exposed at once."
    )


class AddModelPortToSignalChainInput(BaseModel):
    model_name: str = Field(
        description="Name of the model that contains the target port (e.g. 'SineWaves')."
    )
    port_name: str = Field(
        description="Name of the ONE specific port block to add to the signal chain (e.g. 'Sine_t'). Use list_model_ports to discover valid names."
    )


class ListModelPortsInput(BaseModel):
    model_name: str = Field(
        description="Name of the model whose port names should be listed, e.g. 'SineWaves'"
    )
