import json
import logging
import sys
from collections.abc import Iterator
from typing import cast

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
    withhold_secrets,
)

_LEAK = "hunter2"
_STORE_URL = f"redis://cortex:{_LEAK}@redis:6379"


def _record(message: str = "hello", **fields: object) -> logging.LogRecord:
    """One INFO record with ``fields`` attached the way ``extra=`` attaches them."""
    record = logging.LogRecord("cortex.test", logging.INFO, "p.py", 7, message, (), None)
    record.__dict__.update(fields)
    return record


def _raised() -> logging.LogRecord:
    """A WARNING record with the store's URL in its message, in a field, and in a traceback."""
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
    """The root logger with its handlers detached, restored afterwards."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    root.handlers[:] = []
    try:
        yield root
    finally:
        root.handlers[:] = handlers
        root.setLevel(level)


def test_the_reserved_set_is_exactly_what_the_stdlib_owns() -> None:
    assert RESERVED_ATTRS - set(_record().__dict__) == {"message", "asctime"}
    assert set(_record().__dict__) - RESERVED_ATTRS == set()


def test_a_record_with_no_fields_prints_exactly_what_it_always_did() -> None:
    assert PlainFormatter().format(_record()) == "INFO:cortex.test:hello"


def test_a_records_fields_are_appended_in_name_order() -> None:
    line = PlainFormatter().format(_record(pool=3, capped=True, chars=9))
    assert line == "INFO:cortex.test:hello capped=True chars=9 pool=3"


def test_a_boolean_prints_the_way_the_runbooks_read_it() -> None:
    assert "capped=True" in PlainFormatter().format(_record(capped=True))
    assert "capped=False" in PlainFormatter().format(_record(capped=False))


def test_a_value_that_would_run_into_the_next_field_is_quoted() -> None:
    assert render_value("permission denied") == '"permission denied"'
    assert render_value('say "no"') == '"say \\"no\\""'
    assert render_value("") == '""'
    assert render_value("untrusted") == "untrusted"


def test_a_structure_prints_as_compact_json_and_a_scalar_as_itself() -> None:
    assert render_value([{"id": "m1", "score": 0.9}]) == '[{"id":"m1","score":0.9}]'
    assert render_value(None) == "None"
    assert render_value(7) == "7"


def test_a_value_longer_than_the_bound_is_cut_and_the_line_says_how_much_went() -> None:
    rendered = render_value("x" * (VALUE_CHARS + 500))
    assert rendered == '"' + "x" * (VALUE_CHARS - 1) + "<cut 502 chars>"
    assert rendered == '"' + "x" * (VALUE_CHARS - 1) + CUT.format(chars=502)


def test_a_structure_is_cut_on_its_rendered_json_and_stops_parsing() -> None:
    rendered = render_value({"instruction": "summarise the inbox " * 500})
    assert rendered.startswith('{"instruction":"summarise the inbox ')
    assert rendered.endswith(CUT.format(chars=7970))  # of the 10,018 the structure renders to
    with pytest.raises(json.JSONDecodeError):
        json.loads(rendered)


def test_a_rendering_exactly_at_the_bound_prints_whole() -> None:
    edge = "x" * VALUE_CHARS
    assert render_value(edge) == edge
    assert render_value(edge + "x") == '"' + "x" * (VALUE_CHARS - 1) + CUT.format(chars=3)


def test_the_bound_is_spent_on_the_rendered_text_rather_than_on_the_value() -> None:
    value = '"' * (VALUE_CHARS - 100)
    rendered = render_value(value)
    assert len(value) < VALUE_CHARS
    assert len(rendered) == VALUE_CHARS + len(CUT.format(chars=1850))
    assert rendered.endswith(CUT.format(chars=1850))


def test_a_field_that_holds_the_marker_itself_is_still_told_from_a_cut_one() -> None:
    said = CUT.format(chars=7)
    assert render_value(said) == f'"{said}"'
    assert render_value("x" * (VALUE_CHARS + 7)) == '"' + "x" * (VALUE_CHARS - 1) + CUT.format(
        chars=9
    )


def test_a_cut_bare_value_is_quoted_rather_than_run_into_the_pair_beside_it() -> None:
    line = render_fields({"endpoint": "http://" + "a" * VALUE_CHARS, "next": 1})
    assert line.startswith('endpoint="http://aaa')
    assert line.endswith(f"{CUT.format(chars=9)} next=1")
    assert render_value("http://model-host:9300/health") == "http://model-host:9300/health"


def test_an_enormous_field_leaves_a_line_the_log_driver_still_keeps_whole() -> None:
    one_docker_message = 16383
    line = PlainFormatter().format(_record(reply="y" * 100_000, session="s1"))
    assert len(line) < one_docker_message
    assert line.count(CUT.format(chars=97954)) == 1


def test_the_packed_rendering_carries_a_value_the_plain_one_would_cut() -> None:
    payload = json.loads(PackedFormatter().format(_record(reply="y" * 100_000)))
    assert payload["fields"]["reply"] == "y" * 100_000


def test_a_value_no_json_encoder_knows_falls_back_to_its_text() -> None:
    assert render_value(object()).startswith('"<object object at')


def test_no_fields_render_to_no_text() -> None:
    assert render_fields({}) == ""


def test_a_field_named_for_a_secret_is_withheld_rather_than_printed() -> None:
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
    assert "model=cortex" in line


def test_the_denylist_errs_toward_withholding() -> None:
    assert "max_tokens=<redacted>" in PlainFormatter().format(_record(max_tokens=512))
    assert render_fields(record_fields(_record(chars=512))) == "chars=512"


def test_a_secret_named_key_inside_a_field_is_withheld_on_both_renderings() -> None:
    arguments = {
        "password": _LEAK,
        "nested": [{"API_TOKEN": "abc"}, ("keep", {"cookie": "c1"})],
        "path": "/etc/hosts",
    }
    record = _record("tool.invocation", arguments=arguments)
    line = PlainFormatter().format(record)
    packed = json.loads(PackedFormatter().format(record))
    for leaked in (_LEAK, "abc", "c1"):
        assert leaked not in line
    assert packed["fields"]["arguments"] == {
        "nested": [{"API_TOKEN": REDACTED}, ["keep", {"cookie": REDACTED}]],
        "password": REDACTED,
        "path": "/etc/hosts",
    }
    assert line.endswith(render_value(packed["fields"]["arguments"]).replace(" ", ""))
    assert arguments["password"] == _LEAK


def test_the_walk_returns_a_value_holding_no_secret_as_it_was() -> None:
    plain = {"items": [1, (2, 3)], 7: {"x": None}}
    assert withhold_secrets(plain) is plain
    assert withhold_secrets(("a", {"token": 1})) == ("a", {"token": REDACTED})
    assert withhold_secrets([{"token": 1}]) == [{"token": REDACTED}]
    assert withhold_secrets({1: "token", None: "password"}) == {1: "token", None: "password"}
    assert withhold_secrets(_LEAK) == _LEAK
    shared = {"token": 1}
    assert withhold_secrets([shared, {"again": shared}]) == [
        {"token": REDACTED},
        {"again": {"token": REDACTED}},
    ]


def test_a_structure_too_deep_to_walk_is_withheld_whole() -> None:
    deep: object = {"password": _LEAK}
    for _ in range(sys.getrecursionlimit() * 20):
        deep = [deep]
    line = PlainFormatter().format(_record("tool.invocation", arguments={"value": deep}))
    assert line == f"INFO:cortex.test:tool.invocation arguments={REDACTED}"


def test_a_cycle_still_fails_in_the_encoder() -> None:
    looped: dict[str, object] = {"password": _LEAK}
    looped["self"] = looped
    walked = withhold_secrets(looped)
    assert walked is not looped
    assert cast("dict[str, object]", walked)["password"] == REDACTED
    with pytest.raises(ValueError, match="Circular reference"):
        render_value(walked)


def test_a_withheld_value_is_gone_before_the_bound_cuts_the_structure() -> None:
    first = {"password": _LEAK * 400, "z": "x" * VALUE_CHARS}
    rendered = render_value(record_fields(_record(arguments=first))["arguments"])
    assert rendered.startswith(f'{{"password":"{REDACTED}","z":"xxx')
    assert rendered.endswith(CUT.format(chars=len('{"password":"<redacted>","z":"') + 2))
    last = {"a": "x" * VALUE_CHARS, "password": _LEAK * 400}
    rendered = render_value(record_fields(_record(arguments=last))["arguments"])
    assert _LEAK[:3] not in rendered
    assert rendered.endswith(CUT.format(chars=len('{"a":"') + len('","password":"<redacted>"}')))


def test_a_credential_inside_a_url_never_survives_the_line() -> None:
    assert redact_urls(_STORE_URL) == f"redis://{REDACTED}@redis:6379"
    assert redact_urls("imap://u:pw@127.0.0.1:1143") == f"imap://{REDACTED}@127.0.0.1:1143"
    assert redact_urls("mail to me@example.com") == "mail to me@example.com"
    assert redact_urls("http://model-host:9300/health") == "http://model-host:9300/health"


def test_a_credential_the_bound_cuts_across_is_still_withheld() -> None:
    url = f"postgres://cortex:{_LEAK}@db:5432/cortex"
    padding = "x" * (VALUE_CHARS - len('{"a":"') - url.index("@"))
    line = PlainFormatter().format(_record("tool.invocation", arguments={"a": padding + url}))
    assert _LEAK not in line
    assert f"postgres://{REDACTED}@" in line
    assert line.endswith(CUT.format(chars=13))


def test_a_value_that_grows_under_withholding_is_still_bounded() -> None:
    value = "http://a@h" + "x" * (VALUE_CHARS - 10)
    assert len(value) == VALUE_CHARS
    rendered = render_value(value)
    assert rendered.startswith(f'"http://{REDACTED}@hxxx')
    assert len(rendered) == VALUE_CHARS + len(CUT.format(chars=11))
    assert rendered.endswith(CUT.format(chars=11))


def test_a_secret_named_field_is_withheld_before_the_bound_can_reach_it() -> None:
    line = PlainFormatter().format(_record(api_key="k" * 100_000))
    assert line == f"INFO:cortex.test:hello api_key={REDACTED}"
    assert len(REDACTED) < VALUE_CHARS


def test_the_url_defence_reaches_the_message_the_field_and_the_traceback() -> None:
    line = PlainFormatter().format(_raised())
    head, _, trace = line.partition("\n")
    assert _LEAK not in line
    assert head.count(REDACTED) == 2
    assert REDACTED in trace


def test_fields_print_before_a_traceback_rather_than_after_it() -> None:
    head, _, trace = PlainFormatter().format(_raised()).partition("\n")
    assert "attempt=2" in head
    assert "attempt=2" not in trace
    assert "ConnectionError" in trace


def test_the_packed_rendering_is_one_json_object_per_line() -> None:
    payload = json.loads(PackedFormatter().format(_record(pool=3, capped=True)))
    assert payload == {
        "level": "INFO",
        "logger": "cortex.test",
        "message": "hello",
        "fields": {"pool": 3, "capped": True},
    }


def test_the_packed_rendering_omits_the_fields_key_when_there_are_none() -> None:
    assert "fields" not in json.loads(PackedFormatter().format(_record()))


def test_the_packed_rendering_carries_a_traceback_and_withholds_the_same_secrets() -> None:
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
    with pytest.raises(UnknownLogFormatError) as err:
        build_formatter("jsonl")
    assert "jsonl" in str(err.value)
    assert PACKED_FORMAT in str(err.value)


def test_the_configured_handler_puts_a_records_fields_on_the_stream(
    bare_root: logging.Logger, capsys: pytest.CaptureFixture[str]
) -> None:
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
    assert len(bare_root.handlers) == 1


def test_an_unknown_rendering_installs_nothing_at_all(bare_root: logging.Logger) -> None:
    before = bare_root.handlers[:]
    with pytest.raises(UnknownLogFormatError):
        configure_logging(logging.INFO, style="nope")
    assert bare_root.handlers == before
