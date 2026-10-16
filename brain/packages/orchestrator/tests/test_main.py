import importlib

from cortex_orchestrator.entry import main


def test_importing_the_entrypoint_starts_nothing() -> None:
    module = importlib.import_module("cortex_orchestrator.__main__")
    assert module.main is main
