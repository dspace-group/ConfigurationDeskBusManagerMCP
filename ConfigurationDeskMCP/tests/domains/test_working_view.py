# -*- coding: utf-8 -*-
"""Domain: working view and conflict tools (sources/tools/working_view.py)."""

from sources.services import working_view_service as wv_svc

from tests.domains.conftest import run_ok, run_raw

COVERS = (
    "create_working_view",
    "list_working_views",
    "remove_working_view",
    "clear_all_working_views",
    "export_working_view",
    "check_conflicts",
)


def test_create_working_view(fake_bridge):
    run_ok(wv_svc.create_working_view("MyView"))


def test_list_working_views(fake_bridge):
    run_ok(wv_svc.list_working_views())


def test_remove_working_view(fake_bridge):
    payload = run_ok(wv_svc.remove_working_view("MyView"))
    assert payload["verified"] is True


def test_remove_working_view_requires_com_verification(fake_bridge, monkeypatch):
    async def unverified_removal(*_args, **_kwargs):
        return {"removed": True, "verified": False}

    monkeypatch.setattr(wv_svc, "dispatch", unverified_removal)

    payload = run_raw(wv_svc.remove_working_view("MyView"))

    assert payload["success"] is False
    assert payload["retryable"] is False
    assert "not confirmed" in payload["error"]


def test_clear_all_working_views(fake_bridge):
    run_ok(wv_svc.clear_all_working_views())


def test_export_working_view(fake_bridge):
    payload = run_ok(wv_svc.export_working_view("MyView", "D:/views/MyView.xml"))
    assert payload["path"] == "D:/views/MyView.xml"


def test_check_conflicts(fake_bridge):
    payload = run_ok(wv_svc.check_conflicts())
    assert payload["count"] == 0
