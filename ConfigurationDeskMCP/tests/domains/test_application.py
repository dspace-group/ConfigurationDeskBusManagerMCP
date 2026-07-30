# -*- coding: utf-8 -*-
"""Domain: application lifecycle tools (sources/tools/application.py)."""

from sources.services import application_service as app_svc

from tests.domains.conftest import run_ok

COVERS = (
    "start_configurationdesk",
    "stop_configurationdesk",
    "get_application_status",
    "save_project",
    "undo",
    "redo",
    "diagnose_connection",
)


def test_start_configurationdesk(fake_bridge):
    run_ok(app_svc.start(visible=False))


def test_stop_configurationdesk(fake_bridge):
    run_ok(app_svc.stop(save=True))


def test_get_application_status(fake_bridge):
    status = run_ok(app_svc.get_status())
    assert status["project"] == "DemoProject"


def test_save_project(fake_bridge):
    run_ok(app_svc.save_project())


def test_undo(fake_bridge):
    run_ok(app_svc.undo())


def test_redo(fake_bridge):
    run_ok(app_svc.redo())


def test_diagnose_connection(fake_bridge):
    payload = run_ok(app_svc.diagnose_connection())
    assert "diagnostics" in payload
