import importlib

from cortex_orchestrator import run_from_env
from cortex_orchestrator.config_logging import configure_from_env


def test_importing_the_entrypoint_starts_nothing() -> None:
    module = importlib.import_module("cortex_orchestrator.__main__")
    assert module.run_from_env is run_from_env
    assert module.configure_from_env is configure_from_env
