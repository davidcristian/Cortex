"""The `python -m cortex_orchestrator` entrypoint is import-safe (guard defers all work)."""

import importlib

from cortex_orchestrator import SeamServerConfig, serve


def test_importing_the_entrypoint_starts_nothing() -> None:
    module = importlib.import_module("cortex_orchestrator.__main__")
    # Importing must only wire names together; serving happens solely under `-m`.
    assert module.serve is serve
    assert module.SeamServerConfig is SeamServerConfig
