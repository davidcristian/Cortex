"""Behavior of the formatter every brain process entry installs.

The defect it exists to end: `logging.basicConfig(level=...)` installs the stdlib's own format,
which prints `levelname:name:message` and drops every `extra` field this repo attaches. So the
tests here are about what reaches a line rather than about what was attached, and the two that
matter most are the ones nothing else in the tree can assert: that a field named for a secret
never prints its value, and that a credential inside a URL never survives the line it rides on.
"""

import json
import logging
import sys
from collections.abc import Iterator

import pytest

from cortex_core import (
    DEFAULT_LOG_FORMAT,
    LOG_FORMATS,
    PACKED_FORMAT,
    PLAIN_FORMAT,
    REDACTED,
    RESERVED_ATTRS,
    PackedFormatter,
    PlainFormatter,
    UnknownLogFormatError,
    build_formatter,
    configure_logging,
    record_fields,
    redact_urls,
    render_fields,
    render_value,
)

# One fake credential, spent in all three places a line can carry one.
_LEAK = "hunter2"
_STORE_URL = f"redis://cortex:{_LEAK}@redis:6379"


def _record(message: str = "hello", **fields: object) -> logging.LogRecord:
    """One INFO record carrying ``fields`` the way `extra=` would have attached them."""
    record = logging.LogRecord("cortex.test", logging.INFO, "p.py", 7, message, (), None)
    record.__dict__.update(fields)
    return record


def _raised() -> logging.LogRecord:
    """A WARNING record carrying the store's URL in its message, in a field, and in a traceback."""
    logger = logging.getLogger("cortex.test")
    try:
        refused = f"{_STORE_URL} refused the connection"
        raise ConnectionError(refused)  # noqa: TRY301 - a real traceback is the subject here
    except ConnectionError:
        return logger.makeRecord(
            "cortex.test",
            logging.WARNING,
            "p.py",
            7,
            f"the session store is unreachable: {_STORE_URL}",
            (),
            sys.exc_info(),
            extra={"attempt": 2, "endpoint": _STORE_URL},
        )


@pytest.fixture
def bare_root() -> Iterator[logging.Logger]:
    """The root logger with its handlers detached, restored afterwards.

    `configure_logging` forces its handler on, which closes whatever was attached. Pytest's own
    capture handler is attached during a test, so it is taken out of harm's way here rather than
    closed and handed back broken.
    """
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    root.handlers[:] = []
    try:
        yield root
    finally:
        root.handlers[:] = handlers
        root.setLevel(level)


def test_the_reserved_set_is_exactly_what_the_stdlib_owns() -> None:
    """A Python release that adds a record attribute must redden here, not print it as a field.

    Asserted as a difference in both directions: an attribute the stdlib grew would show up on
    the right and fail, and a name written down here that no record carries would show up on the
    left. The only two legitimately absent from a fresh record are the pair a `Formatter` adds
    itself while it runs.
    """
    assert RESERVED_ATTRS - set(_record().__dict__) == {"message", "asctime"}
    assert set(_record().__dict__) - RESERVED_ATTRS == set()


def test_a_record_with_no_fields_prints_exactly_what_it_always_did() -> None:
    """The formatter is additive: a line with nothing attached must not gain a stray separator."""
    assert PlainFormatter().format(_record()) == "INFO:cortex.test:hello"


def test_a_records_fields_are_appended_in_name_order() -> None:
    """Name order rather than attachment order, so two lines of a kind compare column by column."""
    line = PlainFormatter().format(_record(pool=3, capped=True, chars=9))
    assert line == "INFO:cortex.test:hello capped=True chars=9 pool=3"


def test_a_boolean_prints_the_way_the_runbooks_read_it() -> None:
    """`capped=True` is the exact spelling a runbook sends an operator to grep for.

    JSON would write that boolean `true`, a different string, and would silently invalidate every
    documented reading of the rank fallback's line.
    """
    assert "capped=True" in PlainFormatter().format(_record(capped=True))
    assert "capped=False" in PlainFormatter().format(_record(capped=False))


def test_a_value_that_would_run_into_the_next_field_is_quoted() -> None:
    """Whitespace and a quote of its own are the two things that break the `key=value` shape."""
    assert render_value("permission denied") == '"permission denied"'
    assert render_value('say "no"') == '"say \\"no\\""'
    assert render_value("") == '""'
    assert render_value("untrusted") == "untrusted"


def test_a_structure_prints_as_compact_json_and_a_scalar_as_itself() -> None:
    """The recall trail's hits are a list of objects, and a Python repr of one parses nowhere."""
    assert render_value([{"id": "m1", "score": 0.9}]) == '[{"id":"m1","score":0.9}]'
    assert render_value(None) == "None"
    assert render_value(7) == "7"


def test_a_value_no_json_encoder_knows_falls_back_to_its_text() -> None:
    """An `extra` may carry anything, and a formatter that raised would lose the whole record."""
    assert render_value(object()).startswith('"<object object at')


def test_no_fields_render_to_no_text() -> None:
    """The empty rendering the formatter's own guard relies on being empty."""
    assert render_fields({}) == ""


def test_a_field_named_for_a_secret_is_withheld_rather_than_printed() -> None:
    """The whole risk of a formatter that prints what nobody enumerated (AGENTS.md gate 5).

    Four spellings of the concrete secrets this deployment holds: the seam token, the mail
    bridge's password, a model host credential, an authorization header. No value may appear on
    the line, and every key must, so a reader can tell a withheld field from a missing one.
    """
    line = PlainFormatter().format(
        _record(
            token="s3cr3t-seam",  # noqa: S106 - a fake secret is the subject of the test
            IMAP_PASSWORD=_LEAK,
            api_key="ak-live-1",
            authorization="Bearer abc",
            model="cortex",
        )
    )
    for leaked in ("s3cr3t-seam", _LEAK, "ak-live-1", "Bearer abc"):
        assert leaked not in line
    assert line.count(REDACTED) == 4
    assert "token=<redacted>" in line
    assert "model=cortex" in line  # and an ordinary field is untouched


def test_the_denylist_errs_toward_withholding() -> None:
    """`max_tokens` is withheld too, and that is the trade this direction of error buys.

    A count a reader can recover from the message costs less than one bearer token reaching a
    terminal, so the match is a substring of the name and not the whole of it.
    """
    assert "max_tokens=<redacted>" in PlainFormatter().format(_record(max_tokens=512))
    assert render_fields(record_fields(_record(chars=512))) == "chars=512"


def test_a_credential_inside_a_url_never_survives_the_line() -> None:
    """The other shape of the leak, and the one a key-name rule cannot see."""
    assert redact_urls(_STORE_URL) == f"redis://{REDACTED}@redis:6379"
    assert redact_urls("imap://u:pw@127.0.0.1:1143") == f"imap://{REDACTED}@127.0.0.1:1143"
    assert redact_urls("mail to me@example.com") == "mail to me@example.com"  # no scheme, no match
    assert redact_urls("http://model-host:9300/health") == "http://model-host:9300/health"


def test_the_url_defence_reaches_the_message_the_field_and_the_traceback() -> None:
    """A connection URL arrives in all three, so the defence is over the whole rendered line."""
    line = PlainFormatter().format(_raised())
    head, _, trace = line.partition("\n")
    assert _LEAK not in line
    assert head.count(REDACTED) == 2  # once in the message, once in the field beside it
    assert REDACTED in trace


def test_fields_print_before_a_traceback_rather_than_after_it() -> None:
    """A field twenty lines under a stack is a field nobody greps and nobody reads."""
    head, _, trace = PlainFormatter().format(_raised()).partition("\n")
    assert "attempt=2" in head
    assert "attempt=2" not in trace
    assert "ConnectionError" in trace


def test_the_packed_rendering_is_one_json_object_per_line() -> None:
    """For a deployment that collects rather than reads; the fields keep their own key."""
    payload = json.loads(PackedFormatter().format(_record(pool=3, capped=True)))
    assert payload == {
        "level": "INFO",
        "logger": "cortex.test",
        "message": "hello",
        "fields": {"pool": 3, "capped": True},
    }


def test_the_packed_rendering_omits_the_fields_key_when_there_are_none() -> None:
    """An empty object on every line would be noise in the one rendering meant to be parsed."""
    assert "fields" not in json.loads(PackedFormatter().format(_record()))


def test_the_packed_rendering_carries_a_traceback_and_withholds_the_same_secrets() -> None:
    """Both renderings withhold by the same rules; a second rendering is a second chance to leak."""
    line = PackedFormatter().format(_raised())
    payload = json.loads(line)
    assert "ConnectionError" in str(payload["exception"])
    assert _LEAK not in line
    assert payload["fields"]["attempt"] == 2


def test_a_secret_named_field_is_withheld_in_the_packed_rendering_too() -> None:
    token = "abc123"  # noqa: S105 - a fake secret is the subject of the test
    payload = json.loads(PackedFormatter().format(_record(session_token=token)))
    assert payload["fields"] == {"session_token": REDACTED}


def test_each_rendering_is_reachable_by_the_name_a_deployment_writes() -> None:
    assert isinstance(build_formatter(PLAIN_FORMAT), PlainFormatter)
    assert isinstance(build_formatter(PACKED_FORMAT), PackedFormatter)
    assert DEFAULT_LOG_FORMAT == PLAIN_FORMAT
    assert set(LOG_FORMATS) == {PLAIN_FORMAT, PACKED_FORMAT}


def test_a_rendering_this_build_does_not_carry_is_a_typed_refusal() -> None:
    """A typo in the env is a configuration fault, and the refusal names the alternatives."""
    with pytest.raises(UnknownLogFormatError) as err:
        build_formatter("jsonl")
    assert "jsonl" in str(err.value)
    assert PACKED_FORMAT in str(err.value)


def test_the_configured_handler_puts_a_records_fields_on_the_stream(
    bare_root: logging.Logger, capsys: pytest.CaptureFixture[str]
) -> None:
    """The end of the defect: a real logger call, through a real handler, printing a real field."""
    configure_logging(logging.INFO)
    logging.getLogger("cortex.test").info("swap done", extra={"model": "brain"})
    assert capsys.readouterr().err.strip() == "INFO:cortex.test:swap done model=brain"
    assert bare_root.level == logging.INFO


def test_the_configured_handler_honours_the_rendering_the_deployment_named(
    bare_root: logging.Logger, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging("INFO", style=PACKED_FORMAT)
    logging.getLogger("cortex.test").info("swap done", extra={"model": "brain"})
    payload = json.loads(capsys.readouterr().err.strip())
    assert payload["fields"] == {"model": "brain"}
    assert len(bare_root.handlers) == 1  # forced on, so exactly one handler renders this process


def test_an_unknown_rendering_installs_nothing_at_all(bare_root: logging.Logger) -> None:
    """The refusal comes before the handler, so a failed entry leaves no half-configured root."""
    before = bare_root.handlers[:]
    with pytest.raises(UnknownLogFormatError):
        configure_logging(logging.INFO, style="nope")
    assert bare_root.handlers == before
