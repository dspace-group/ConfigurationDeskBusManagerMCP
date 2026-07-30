# -*- coding: utf-8 -*-
"""Pydantic input models for project management tools."""

from typing import Optional

from pydantic import BaseModel, Field


class CreateProjectInput(BaseModel):
    name: str = Field(description="Name of the new project, e.g. 'MyTestProject'")
    project_root: Optional[str] = Field(
        default=None, description="Optional project root directory path, e.g. 'C:/Projects'"
    )
    replace: bool = Field(default=True, description="Replace if project already exists, e.g. true")


class OpenProjectInput(BaseModel):
    name: str = Field(description="Name of the project to open, e.g. 'MyTestProject'")


class CloseProjectInput(BaseModel):
    save: bool = Field(default=True, description="Save before closing, e.g. true")


class RemoveProjectInput(BaseModel):
    name: str = Field(description="Name of the project to remove, e.g. 'OldProject'")
    delete_files: bool = Field(
        default=False, description="Also delete project files from disk, e.g. false"
    )


class ListProjectsInput(BaseModel):
    pass


class SetProjectRootInput(BaseModel):
    path: str = Field(description="Project root directory path, e.g. 'C:/dSPACE/Projects'")


class GetProjectPathInput(BaseModel):
    pass


class BackupProjectInput(BaseModel):
    path: str = Field(description="Backup destination folder path, e.g. 'C:/Backups'")


class OpenProjectFromBackupInput(BaseModel):
    backup_path: str = Field(
        description="Path to the backup zip archive file, e.g. 'C:/Backups/MyProject.zip'"
    )
    name: str = Field(description="Name for the restored project, e.g. 'MyProject'")
    overwrite: bool = Field(
        default=False, description="Overwrite if a project with the same name exists, e.g. false"
    )
