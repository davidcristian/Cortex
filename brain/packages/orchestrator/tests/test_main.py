"""The `python -m cortex_orchestrator` entrypoint is import-safe (guard defers all work)."""

import importlib

from cortex_orchestrator import run_from_env
from cortex_orchestrator.config_logging import configure_from_env


def test_importing_the_entrypoint_starts_nothing() -> None:
    module = importlib.import_module("cortex_orchestrator.__main__")
    # Importing must only wire names together; serving happens solely under `-m`.
    assert module.run_from_env is run_from_env
    # And the guard configures logging through the one place that decides how, so a line's own
    # fields reach the container log rather than being attached to a record nothing renders.
    assert module.configure_from_env is configure_from_env
