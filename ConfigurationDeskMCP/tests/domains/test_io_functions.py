# -*- coding: utf-8 -*-
"""Domain: I/O functions library tools (sources/tools/io_functions.py)."""

from types import SimpleNamespace

from configurationdesk_com_bridge.domains import io_functions_com
from sources.services import io_functions_service as io_svc

from tests.domains.conftest import run_ok, run_raw

COVERS = (
    "add_io_function_block",
    "list_io_function_block_types",
    "connect_function_block_port_to_model_port",
)


def test_list_io_function_block_types(fake_bridge):
    payload = run_ok(io_svc.list_io_function_block_types())
    assert "Voltage Out" in payload["types"]


def test_add_io_function_block(fake_bridge):
    payload = run_ok(io_svc.add_io_function_block("Voltage Out", "VoltageOut_FB"))
    assert payload["name"] == "VoltageOut_FB"


def test_connect_function_block_port_to_model_port(fake_bridge):
    run_ok(
        io_svc.connect_function_block_port_to_model_port(
            "VoltageOut_FB", "Out1", "demosmd_io", "In1"
        )
    )


def test_connect_function_block_port_to_named_model_port(fake_bridge):
    payload = run_ok(
        io_svc.connect_function_block_port_to_model_port(
            "VoltageOut", "Voltage", "Simple_FIR_Filter", "FIR", "Output"
        )
    )
    assert payload["model_port_name"] == "Output"


# ── COM-layer behavior (io_functions_com) ──────────────────────────────────


class _Node:
    def __init__(self, name, children=()):
        self.Name = name
        self._children = list(children)
        self.Links = SimpleNamespace(Count=0)

    def __iter__(self):
        return iter(self._children)

    def Item(self, key):
        if isinstance(key, int):
            return self._children[key]
        for child in self._children:
            if child.Name == key:
                return child
        raise KeyError(key)


def _fir_connection():
    """Fake connection mirroring an FMU with two model port blocks named 'FIR'."""
    voltage_port = _Node("Voltage")
    voltage_out = _Node("VoltageOut", [_Node("Voltage Out", [voltage_port])])
    io_root = _Node("root", [_Node("Voltage Out", [voltage_out])])
    fir_input = _Node("Input")
    fir_output = _Node("Output")
    model = _Node(
        "Simple_FIR_Filter",
        [_Node("FIR", [fir_input]), _Node("FIR", [fir_output])],
    )
    connected = []

    def connect(a, b):
        connected.append((a, b))
        a.Links = SimpleNamespace(Count=1)

    conn = SimpleNamespace(
        active=SimpleNamespace(
            Components=_Node("components", [_Node("IOFunctionLib", [io_root])]),
            ConnectObjects=connect,
        ),
        model_topology=_Node("mt", [model]),
    )
    return conn, connected, voltage_port, fir_output


def test_com_connect_selects_named_port_among_duplicate_blocks():
    conn, connected, voltage_port, fir_output = _fir_connection()

    result = io_functions_com.connect_function_block_port_to_model_port(
        conn, "VoltageOut", "Voltage", "Simple_FIR_Filter", "FIR", "Output"
    )

    assert result.get("error") is None, result
    assert connected == [(voltage_port, fir_output)]
    assert result["model_port_name"] == "Output"
    assert result["verified"] is True


def test_com_connect_rejects_ambiguous_block_without_port_name():
    conn, connected, _voltage_port, _fir_output = _fir_connection()

    result = io_functions_com.connect_function_block_port_to_model_port(
        conn, "VoltageOut", "Voltage", "Simple_FIR_Filter", "FIR"
    )

    assert result["reason"] == "ambiguous_model_port_block"
    assert result["available_model_ports"] == ["Input", "Output"]
    assert connected == []


def test_com_connect_reports_unknown_model_port():
    conn, connected, _voltage_port, _fir_output = _fir_connection()

    result = io_functions_com.connect_function_block_port_to_model_port(
        conn, "VoltageOut", "Voltage", "Simple_FIR_Filter", "FIR", "Missing"
    )

    assert result["reason"] == "model_port_not_found"
    assert connected == []


def _wavetable_connection():
    """Fake connection mirroring demosmd_io: 'Wavetable' at root and inside 'Subsystem'."""
    port_names = ("Wavetable Period", "Amplitude")
    fb_port = _Node("Amplitude")
    fb = _Node("Wavetable Source", [_Node("Wavetable", [fb_port])])
    io_root = _Node("root", [_Node("Wavetable", [fb])])
    root_block = _Node("Wavetable", [_Node(name) for name in port_names])
    nested_block = _Node("Wavetable", [_Node(name) for name in port_names])
    model = _Node(
        "demosmd_io",
        [
            _Node("Mass displacement", [_Node("Voltage")]),
            root_block,
            _Node("Subsystem", [nested_block]),
        ],
    )
    connected = []

    def connect(a, b):
        connected.append((a, b))
        a.Links = SimpleNamespace(Count=1)

    conn = SimpleNamespace(
        active=SimpleNamespace(
            Components=_Node("components", [_Node("IOFunctionLib", [io_root])]),
            ConnectObjects=connect,
        ),
        model_topology=_Node("mt", [model]),
    )
    return conn, connected, fb_port, root_block, nested_block


def test_com_connect_rejects_block_name_shared_across_hierarchy_levels():
    conn, connected, *_ = _wavetable_connection()

    result = io_functions_com.connect_function_block_port_to_model_port(
        conn, "Wavetable Source", "Amplitude", "demosmd_io", "Wavetable", "Amplitude"
    )

    assert result["reason"] == "ambiguous_model_port_block_hierarchy"
    assert result["candidates"] == ["demosmd_io/Wavetable", "demosmd_io/Subsystem/Wavetable"]
    assert connected == []


def test_com_connect_resolves_nested_block_by_path():
    conn, connected, fb_port, _root_block, nested_block = _wavetable_connection()

    result = io_functions_com.connect_function_block_port_to_model_port(
        conn, "Wavetable Source", "Amplitude", "demosmd_io", "Subsystem/Wavetable", "Amplitude"
    )

    assert result.get("error") is None, result
    assert connected == [(fb_port, nested_block.Item("Amplitude"))]
    assert result["model_port_block_path"] == "demosmd_io/Subsystem/Wavetable"


def test_com_connect_resolves_root_block_by_model_prefixed_path():
    conn, connected, fb_port, root_block, _nested_block = _wavetable_connection()

    result = io_functions_com.connect_function_block_port_to_model_port(
        conn, "Wavetable Source", "Amplitude", "demosmd_io", "demosmd_io/Wavetable", "Amplitude"
    )

    assert result.get("error") is None, result
    assert connected == [(fb_port, root_block.Item("Amplitude"))]
    assert result["model_port_block_path"] == "demosmd_io/Wavetable"


def test_connect_service_asks_user_on_hierarchy_ambiguity(fake_bridge, monkeypatch):
    candidates = ["demosmd_io/Wavetable", "demosmd_io/Subsystem/Wavetable"]

    async def ambiguous_dispatch(*_args, **_kwargs):
        return {
            "error": True,
            "reason": "ambiguous_model_port_block_hierarchy",
            "candidates": candidates,
            "detail": "Model 'demosmd_io' has model port blocks named 'Wavetable' at 2 levels.",
        }

    monkeypatch.setattr(io_svc, "dispatch", ambiguous_dispatch)

    payload = run_raw(
        io_svc.connect_function_block_port_to_model_port(
            "Wavetable Source", "Amplitude", "demosmd_io", "Wavetable", "Amplitude"
        )
    )

    assert payload["success"] is False
    assert payload["error_code"] == "AMBIGUOUS_TARGET"
    assert payload["retryable"] is False
    assert "Ask the user" in payload["next_action"]
    for candidate in candidates:
        assert candidate in payload["next_action"]
