# -*- coding: utf-8 -*-
"""Pydantic input models for I/O Functions Library tools."""

from pydantic import BaseModel, Field


class AddIoFunctionBlockInput(BaseModel):
    function_type_name: str = Field(
        description=(
            "Name of the I/O function type from the I/O Functions Library, "
            "e.g. 'Voltage Out', 'Voltage In', 'PWM Out', 'Digital In'. "
            "Use list_io_function_block_types to discover valid values."
        )
    )
    block_name: str = Field(
        description=(
            "Instance name for the new function block in the signal chain, "
            "e.g. 'Voltage1', 'PWM_Throttle'."
        )
    )


class ListIoFunctionBlockTypesInput(BaseModel):
    pass


class ConnectFunctionBlockPortToModelPortInput(BaseModel):
    function_block_name: str = Field(
        description=(
            "Instance name of the function block in the signal chain whose "
            "port should be connected, e.g. 'Voltage Out', 'Voltage1'. "
            "Must already exist (see `add_io_function_block`)."
        )
    )
    function_block_port_name: str = Field(
        description=("Name of the port on the function block, e.g. 'Voltage'.")
    )
    model_name: str = Field(
        description=(
            "Name of the model that owns the target model port block, "
            "e.g. 'SineWaves'. The model must already be added with "
            "`add_model`."
        )
    )
    model_port_name: str = Field(
        description=(
            "Name of the model port block on the model, e.g. 'Sine_t'. "
            "Use `list_model_ports` to discover valid values."
        )
    )
