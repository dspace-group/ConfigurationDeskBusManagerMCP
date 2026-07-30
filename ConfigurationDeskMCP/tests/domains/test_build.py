# -*- coding: utf-8 -*-
"""Domain: build management tools (sources/tools/build.py)."""

from sources.services import build_service as build_svc

from tests.domains.conftest import run_ok

COVERS = (
    "build_application",
    "get_build_result",
)


def test_build_application_without_download(fake_bridge):
    run_ok(build_svc.build_application(download=False, start=False, unload=False))


def test_build_application_with_download_uses_hardware_topology(fake_bridge):
    # download=True triggers the hardware-topology readiness guard, which the
    # fake bridge satisfies via a non-empty list_hardware_names.
    run_ok(build_svc.build_application(download=True, start=False, unload=True))


def test_get_build_result(fake_bridge):
    payload = run_ok(build_svc.get_build_result())
    assert payload["path"] == "D:/out/app.rta"
