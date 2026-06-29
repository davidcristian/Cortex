import importlib

from cortex_email import main


def test_importing_the_entrypoint_starts_nothing() -> None:
    module = importlib.import_module("cortex_email.__main__")
    assert module.main is main
