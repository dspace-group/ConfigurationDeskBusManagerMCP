# -*- coding: utf-8 -*-
"""Pydantic input models for working view and conflict tools."""

from pydantic import BaseModel, Field


class CreateWorkingViewInput(BaseModel):
    name: str = Field(description="Name for the working view, e.g. 'SignalChain_CAN'")


class ListWorkingViewsInput(BaseModel):
    pass


class RemoveWorkingViewInput(BaseModel):
    name: str = Field(description="Name of the working view to remove, e.g. 'SignalChain_CAN'")


class ClearAllWorkingViewsInput(BaseModel):
    pass


class ExportWorkingViewInput(BaseModel):
    name: str = Field(description="Name of the working view, e.g. 'SignalChain_CAN'")
    path: str = Field(
        description="Output file path for the export, e.g. 'C:/Export/signal_chain.xml'"
    )


class CheckConflictsInput(BaseModel):
    pass
