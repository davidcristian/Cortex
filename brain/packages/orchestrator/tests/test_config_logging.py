import logging

import pytest

from cortex_core import PACKED_FORMAT, PLAIN_FORMAT
from cortex_orchestrator.config_logging import LoggingConfig, configure_from_env
from cortex_orchestrator.entry import main


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


def test_a_rendering_this_build_does_not_offer_is_refused_in_the_default_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def serve() -> None:
        pytest.fail("a refused rendering must not serve")

    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    root.handlers[:] = []
    monkeypatch.setenv("CORTEX_LOG_FORMAT", "logfmt")
    try:
        assert main(serve) == 1
    finally:
        root.handlers[:] = handlers
        root.setLevel(level)
    assert capsys.readouterr().err.splitlines() == [
        'ERROR:cortex_orchestrator.entry:setting refused reason="CORTEX_LOG_FORMAT: unknown log '
        "format '<value>'; this build renders ['packed', 'plain']\""
    ]
