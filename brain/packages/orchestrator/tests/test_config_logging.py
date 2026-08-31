"""The logging configuration `python -m cortex_orchestrator` installs before it serves anything.

The entry guard itself is unreachable in a test, so the checks live here instead. They assert that
the brain's rendering comes from the environment, that the level does not, and that a format name
this build does not carry stops the process rather than changing the rendering silently.
"""

import logging

import pytest

from cortex_core import PACKED_FORMAT, PLAIN_FORMAT, UnknownLogFormatError
from cortex_orchestrator.config_logging import LoggingConfig, configure_from_env


def test_a_deployment_that_names_nothing_gets_the_rendering_a_person_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CORTEX_LOG_FORMAT", raising=False)
    assert LoggingConfig().format == PLAIN_FORMAT


def test_the_rendering_comes_from_the_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_LOG_FORMAT", PACKED_FORMAT)
    assert LoggingConfig().format == PACKED_FORMAT


def test_the_brain_configures_info_and_the_env_rendering(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The level is fixed at INFO, since the tool audit trail and the recall trail both log at it.

    The assertion goes through a real emitted record rather than a recorded call, because what
    matters is how the line reads once it has left the process.
    """
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    root.handlers[:] = []
    monkeypatch.delenv("CORTEX_LOG_FORMAT", raising=False)
    try:
        configure_from_env()
        assert root.level == logging.INFO
        logging.getLogger("cortex.tools.audit").info("tool.invocation", extra={"tool": "read"})
    finally:
        root.handlers[:] = handlers
        root.setLevel(level)
    assert capsys.readouterr().err.strip() == "INFO:cortex.tools.audit:tool.invocation tool=read"


def test_a_rendering_this_build_does_not_carry_stops_the_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unrecognized format name raises at the entry point, rather than letting a whole session
    be served in a rendering nobody asked for."""
    monkeypatch.setenv("CORTEX_LOG_FORMAT", "logfmt")
    with pytest.raises(UnknownLogFormatError):
        configure_from_env()
