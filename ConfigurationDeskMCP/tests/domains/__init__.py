# -*- coding: utf-8 -*-
"""Per-domain tool coverage tests.

Each ``test_<domain>.py`` module mirrors one tool domain under
``sources/tools`` and exercises every tool that domain exposes through the real
service layer with a faked COM bridge. Every module declares the tools it
covers via a module-level ``COVERS`` tuple; ``test_tool_coverage.py`` asserts
the union of all ``COVERS`` equals the set of registered MCP tools.
"""
