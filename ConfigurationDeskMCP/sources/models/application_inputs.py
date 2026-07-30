# -*- coding: utf-8 -*-
"""Pydantic input models for application lifecycle tools."""

from pydantic import BaseModel, Field


class StartConfigurationDeskInput(BaseModel):
    visible: bool = Field(
        default=True, description="Make the application window visible, e.g. true"
    )


class StopConfigurationDeskInput(BaseModel):
    save: bool = Field(default=True, description="Save the project before closing, e.g. true")


class SaveProjectInput(BaseModel):
    pass


class UndoInput(BaseModel):
    pass


class RedoInput(BaseModel):
    pass
