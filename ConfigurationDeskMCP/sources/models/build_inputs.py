# -*- coding: utf-8 -*-
"""Pydantic input models for build management tools."""

from pydantic import BaseModel, Field


class BuildApplicationInput(BaseModel):
    download: bool = Field(default=True, description="Download to hardware after build, e.g. true")
    start: bool = Field(default=True, description="Start application after download, e.g. true")
    unload: bool = Field(
        default=True, description="Unload existing application before download, e.g. true"
    )


class GetBuildResultInput(BaseModel):
    pass
