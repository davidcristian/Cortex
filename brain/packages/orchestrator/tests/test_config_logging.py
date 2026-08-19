"""What `python -m cortex_orchestrator` installs before it serves anything.

The entry guard itself is unreachable in a test, which is why the decision lives here instead of
in it: what is asserted is that the brain's own rendering comes from env, that the level does not,
and that a name this build does not carry stops the process rather than quietly changing it.
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
    """INFO is not a knob here: the tool audit trail and the recall trail both log at it.

    Asserted through a real record rather than through a recorded call, because the whole point of
    the change is what a line looks like once it leaves the process.
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
    """Loudly, at the entry, rather than serving a whole session in a shape nobody asked for."""
    monkeypatch.setenv("CORTEX_LOG_FORMAT", "logfmt")
    with pytest.raises(UnknownLogFormatError):
        configure_from_env()
