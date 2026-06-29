"""The `python -m cortex_email` entrypoint is import-safe (guard defers all work)."""

import importlib

from cortex_email import main


def test_importing_the_entrypoint_starts_nothing() -> None:
    module = importlib.import_module("cortex_email.__main__")
    # Importing must only wire names together; serving happens solely under `-m`.
    assert module.main is main
