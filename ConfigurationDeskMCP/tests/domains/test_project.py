# -*- coding: utf-8 -*-
"""Domain: project management tools (sources/tools/project.py)."""

from sources.services import project_service as project_svc

from tests.domains.conftest import run_ok

COVERS = (
    "create_project",
    "open_project",
    "close_project",
    "remove_project",
    "list_projects",
    "set_project_root",
    "get_project_path",
    "backup_project",
    "open_project_from_backup",
)


def test_create_project(fake_bridge):
    run_ok(project_svc.create_project("DemoProject", "D:/Projects", True))


def test_open_project(fake_bridge):
    run_ok(project_svc.open_project("DemoProject"))


def test_close_project(fake_bridge):
    run_ok(project_svc.close_project(save=True))


def test_remove_project(fake_bridge):
    run_ok(project_svc.remove_project("DemoProject", delete_files=False))


def test_list_projects(fake_bridge):
    run_ok(project_svc.list_projects())


def test_set_project_root(fake_bridge):
    run_ok(project_svc.set_project_root("D:/Projects"))


def test_get_project_path(fake_bridge):
    run_ok(project_svc.get_project_path())


def test_backup_project(fake_bridge):
    payload = run_ok(project_svc.backup_project("D:/Projects/backup.zip"))
    assert payload["path"] == "D:/Projects/backup.zip"


def test_open_project_from_backup(fake_bridge):
    run_ok(project_svc.open_project_from_backup("D:/Projects/backup.zip", "DemoProject", True))
