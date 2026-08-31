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
    CUT,
    DEFAULT_LOG_FORMAT,
    LOG_FORMATS,
    PACKED_FORMAT,
    PLAIN_FORMAT,
    REDACTED,
    RESERVED_ATTRS,
    VALUE_CHARS,
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
    """A Python release that adds a record attribute fails this test rather than having the
    formatter print it as a field.

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
    """A structure renders as compact JSON and a scalar as itself. The recall trail's hits are a
    list of objects, and a Python repr of one parses nowhere."""
    assert render_value([{"id": "m1", "score": 0.9}]) == '[{"id":"m1","score":0.9}]'
    assert render_value(None) == "None"
    assert render_value(7) == "7"


def test_a_value_longer_than_the_bound_is_cut_and_the_line_says_how_much_went() -> None:
    """The scalar branch of the bound: what prints is the bound, then the formatter's own marker.

    A count of the characters that did not print, rather than a bare ellipsis, because the reader
    who needs it is the one deciding whether to go and find the whole value somewhere else. The
    count is of the rendering, quotes included, since the rendering is what the bound is spent on.
    """
    rendered = render_value("x" * (VALUE_CHARS + 500))
    assert rendered == '"' + "x" * (VALUE_CHARS - 1) + "<cut 502 chars>"
    assert rendered == '"' + "x" * (VALUE_CHARS - 1) + CUT.format(chars=502)


def test_a_structure_is_cut_on_its_rendered_json_and_stops_parsing() -> None:
    """The other branch, and the deliberate cost: a cut structure fails loudly at whatever reads it.

    The shape is the live one. Every dispatch audits its `arguments` verbatim, and a
    `spawn_subagents` call's arguments are written by the model, so this is the field that can
    arrive at any size at all.
    """
    rendered = render_value({"instruction": "summarise the inbox " * 500})
    assert rendered.startswith('{"instruction":"summarise the inbox ')
    assert rendered.endswith(CUT.format(chars=7970))  # of the 10,018 the object renders to
    with pytest.raises(json.JSONDecodeError):
        json.loads(rendered)  # the cut left it unterminated, and that is the point


def test_a_rendering_exactly_at_the_bound_prints_whole() -> None:
    """The bound is inclusive, so the edge is the last value that reaches a line as it stands."""
    edge = "x" * VALUE_CHARS
    assert render_value(edge) == edge
    assert render_value(edge + "x") == '"' + "x" * (VALUE_CHARS - 1) + CUT.format(chars=3)


def test_the_bound_is_spent_on_the_rendered_text_rather_than_on_the_value() -> None:
    """Escaping is what a line pays for, so a value under the bound can still render past it.

    A string of quotes renders at twice its length plus the pair this module adds, which is why
    the cut is the last thing done to a rendering rather than the first thing done to a value.
    """
    value = '"' * (VALUE_CHARS - 100)
    rendered = render_value(value)
    assert len(value) < VALUE_CHARS
    assert len(rendered) == VALUE_CHARS + len(CUT.format(chars=1850))
    assert rendered.endswith(CUT.format(chars=1850))


def test_a_field_that_spells_the_marker_itself_is_still_told_from_a_cut_one() -> None:
    """The marker is unambiguous by where it sits: a value's own text lives inside a closing quote.

    Every cut rendering stops mid-syntax, having lost its closing quote or bracket, so a marker
    outside a closing delimiter is the formatter speaking. A field whose own text spells the
    marker carries the marker's whitespace, which is what forces it into a quote that closes.
    """
    said = CUT.format(chars=7)
    assert render_value(said) == f'"{said}"'
    assert render_value("x" * (VALUE_CHARS + 7)) == '"' + "x" * (VALUE_CHARS - 1) + CUT.format(
        chars=9
    )


def test_a_cut_bare_value_is_quoted_rather_than_run_into_the_pair_beside_it() -> None:
    """A bare rendering is bare because it prints whole, and a cut one no longer does.

    `_BARE` exists so an unquoted value carries no whitespace and cannot be read into its
    neighbour. The marker carries two spaces, so appending it to a bare rendering would put a
    field boundary inside a field: `endpoint=http://aaa<cut 9 chars> next=1` reads as three
    tokens, the first of them a plausible whole endpoint, and the failure is silent. A rendering
    that will be cut is therefore quoted, which is the same thing a cut structure already does:
    it stops mid-syntax, so a reader meets a fault rather than a value they cannot see is short.
    """
    line = render_fields({"endpoint": "http://" + "a" * VALUE_CHARS, "next": 1})
    assert line.startswith('endpoint="http://aaa')
    assert line.endswith(f"{CUT.format(chars=9)} next=1")
    assert render_value("http://model-host:9300/health") == "http://model-host:9300/health"


def test_an_enormous_field_leaves_a_line_the_log_driver_still_keeps_whole() -> None:
    """Why the bound is the number it is (ADR-0038 bounded-value addendum).

    A container's log driver ends a message at 16 KiB, and past that `--tail` counts pieces
    rather than lines while `docker compose logs -t` stamps every piece, the stamps landing mid
    line because a piece boundary carries no newline of its own. Measured on the shipped image
    and re-measured against the `json-file` driver: a rendered line of 16,383 characters plus its
    newline is the last one that stays a single entry.
    """
    one_docker_message = 16383
    line = PlainFormatter().format(_record(reply="y" * 100_000, session="s1"))
    assert len(line) < one_docker_message
    assert line.count(CUT.format(chars=97954)) == 1


def test_the_packed_rendering_carries_a_value_the_plain_one_would_cut() -> None:
    """The asymmetry is real and deliberate: only the plain rendering passes through `render_value`.

    `PackedFormatter` hands the fields to `json.dumps` as they were attached, because the whole
    value of a rendering meant to be collected is that the object parses, and a bound inside it
    either corrupts the object or lies about its shape. The exposure is recorded rather than
    fixed here; this test is what makes closing it a decision rather than an accident.
    """
    payload = json.loads(PackedFormatter().format(_record(reply="y" * 100_000)))
    assert payload["fields"]["reply"] == "y" * 100_000


def test_a_value_no_json_encoder_knows_falls_back_to_its_text() -> None:
    """An `extra` may carry anything, and a formatter that raised would lose the whole record."""
    assert render_value(object()).startswith('"<object object at')


def test_no_fields_render_to_no_text() -> None:
    """The empty rendering the formatter's own guard relies on being empty."""
    assert render_fields({}) == ""


def test_a_field_named_for_a_secret_is_withheld_rather_than_printed() -> None:
    """A field named for a secret prints ``<redacted>`` rather than its value, which is the risk
    a formatter that prints what nobody enumerated carries (AGENTS.md gate 5).

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
    """A credential inside a URL is withheld, which is the shape of leak a key-name rule cannot
    see."""
    assert redact_urls(_STORE_URL) == f"redis://{REDACTED}@redis:6379"
    assert redact_urls("imap://u:pw@127.0.0.1:1143") == f"imap://{REDACTED}@127.0.0.1:1143"
    assert redact_urls("mail to me@example.com") == "mail to me@example.com"  # no scheme, no match
    assert redact_urls("http://model-host:9300/health") == "http://model-host:9300/health"


def test_a_credential_the_bound_cuts_across_is_still_withheld() -> None:
    """The interaction of the two defences the module carries, and the one that had a hole.

    `_USERINFO` is anchored on the `@` that ends a URL's userinfo, and the bound cuts a rendering
    before the whole-line pass ever runs. So a cut landing between a URL's `://` and its `@` used
    to leave the pattern nothing to match and print the credential in full. The padding here puts
    that `@` at exactly the first character the cut removes, which is the sharpest form of it.

    The carrier is the live one rather than a hypothetical: `LoggingAuditSink` attaches every tool
    call's `arguments` verbatim, and one shipped tool takes its arguments from the model.
    """
    url = f"postgres://cortex:{_LEAK}@db:5432/cortex"
    padding = "x" * (VALUE_CHARS - len('{"a":"') - url.index("@"))
    line = PlainFormatter().format(_record("tool.invocation", arguments={"a": padding + url}))
    assert _LEAK not in line
    assert f"postgres://{REDACTED}@" in line
    assert line.endswith(CUT.format(chars=13))  # and the case really is a cut one


def test_a_value_that_grows_under_withholding_is_still_bounded() -> None:
    """Withholding can lengthen a rendering, and the bound is spent on what actually prints.

    `<redacted>` is longer than the userinfo it stands in for whenever that userinfo is short, so
    a value sitting exactly at the bound crosses it on the way to the line. The length that
    decides whether a rendering may print as it stands is therefore the withheld one.
    """
    value = "http://a@h" + "x" * (VALUE_CHARS - 10)
    assert len(value) == VALUE_CHARS
    rendered = render_value(value)
    assert rendered.startswith(f'"http://{REDACTED}@hxxx')
    assert len(rendered) == VALUE_CHARS + len(CUT.format(chars=11))
    assert rendered.endswith(CUT.format(chars=11))


def test_a_secret_named_field_is_withheld_before_the_bound_can_reach_it() -> None:
    """A field named for a secret is withheld before the bound can reach it, so these two
    defences do not interact.

    A field named for a secret loses its value before anything renders it, and what stands in its
    place is one short constant, so no cut can ever land inside it. The arrangement that would
    break this is a bound spent on the way to the substitution rather than after it, which is
    what the cut did to the URL defence beside it.
    """
    line = PlainFormatter().format(_record(api_key="k" * 100_000))
    assert line == f"INFO:cortex.test:hello api_key={REDACTED}"
    assert len(REDACTED) < VALUE_CHARS  # what makes the sentence above true rather than lucky


def test_the_url_defence_reaches_the_message_the_field_and_the_traceback() -> None:
    """A connection URL arrives in all three, so the defence is over the whole rendered line."""
    line = PlainFormatter().format(_raised())
    head, _, trace = line.partition("\n")
    assert _LEAK not in line
    assert head.count(REDACTED) == 2  # once in the message, once in the field beside it
    assert REDACTED in trace


def test_fields_print_before_a_traceback_rather_than_after_it() -> None:
    """Fields are appended to the first line, because a field printed below a stack trace is
    hard to grep and easy to miss."""
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
