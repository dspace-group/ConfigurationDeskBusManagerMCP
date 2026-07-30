# -*- coding: utf-8 -*-
"""Pydantic input models for application management tools."""

from pydantic import BaseModel, Field


class AddApplicationInput(BaseModel):
    name: str = Field(description="Name for the new application, e.g. 'Application1'")


class ActivateApplicationInput(BaseModel):
    name: str = Field(description="Name of the application to activate, e.g. 'Application1'")


class RemoveApplicationInput(BaseModel):
    name: str = Field(description="Name of the application to remove, e.g. 'Application1'")


class ListApplicationsInput(BaseModel):
    pass
