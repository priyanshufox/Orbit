"""Smoke test: every module from ADR 0001 exists and imports."""

import importlib

MODULES = ["accounts", "rooms", "game", "scoring", "graph", "content", "privacy"]


def test_modules_import() -> None:
    for name in MODULES:
        importlib.import_module(f"orbit.modules.{name}")
    importlib.import_module("orbit.modules.scoring.domain")
    importlib.import_module("orbit.core")
