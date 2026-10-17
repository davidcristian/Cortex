# The autouse fixture below is called by pytest and never referenced, so pyright reads it
# as unused.
# pyright: reportUnusedFunction=false

import importlib
import logging
import os

import pytest
from mcp.server.fastmcp import FastMCP

from cortex_email import main


@pytest.fixture(autouse=True)
def _clean_email_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [name for name in os.environ if name.startswith("CORTEX_EMAIL_")]:
        monkeypatch.delenv(name)


def _refused(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> str:
    def refuse_to_serve(_self: FastMCP, transport: str) -> None:
        pytest.fail(f"a refused setting must not serve over {transport}")

    monkeypatch.setattr(FastMCP, "run", refuse_to_serve)
    with caplog.at_level(logging.ERROR, logger="cortex_email.server"):
        assert main() == 1
    [record] = caplog.records
    assert record.exc_info is None
    return record.getMessage()


def test_importing_the_entrypoint_starts_nothing() -> None:
    module = importlib.import_module("cortex_email.__main__")
    assert module.main is main


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("CORTEX_EMAIL_IMAP_PORT", "11q43"),
        ("CORTEX_EMAIL_IMAP_SECURITY", "qx7plain"),
        ("CORTEX_EMAIL_SMTP_TLS_INSECURE", "perhaps"),
        ("CORTEX_EMAIL_SEND_ENABLED", "maybe"),
    ],
)
def test_a_refused_setting_is_one_line_naming_its_variable_and_never_its_value(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, variable: str, value: str
) -> None:
    monkeypatch.setenv(variable, value)
    line = _refused(monkeypatch, caplog)
    assert line.startswith(f"setting refused: {variable}: ")
    assert value not in line


def test_a_send_without_a_user_is_refused_without_showing_the_password(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("CORTEX_EMAIL_SEND_ENABLED", "true")
    monkeypatch.setenv("CORTEX_EMAIL_SMTP_PASSWORD", "qx7secret")
    assert _refused(monkeypatch, caplog) == (
        "setting refused: CORTEX_EMAIL_SMTP_USER and CORTEX_EMAIL_SMTP_PASSWORD are required "
        "when CORTEX_EMAIL_SEND_ENABLED=true"
    )
