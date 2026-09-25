import json
import logging

from cortex_core import REDACTED, durable_record, durable_value, record_fields


def test_scalars_and_short_structures_are_kept_as_values() -> None:
    assert durable_value(value=True) is True
    assert durable_value(7) == 7
    assert durable_value("plain") == "plain"
    assert durable_value("two words") == "two words"
    assert durable_value((1, 2.5, None, "x")) == [1, 2.5, None, "x"]
    assert durable_value({1, 2} - {2}) == "{1}"


def test_a_secret_named_field_is_withheld_whole_as_the_line_withholds_it() -> None:
    fields: dict[str, object] = {"api_token": {"id": "a"}, "k": 5, "nested": {"password": "pw"}}
    row = json.loads(durable_record(fields))
    assert row == {"api_token": REDACTED, "k": 5, "nested": {"password": REDACTED}}
    record = logging.LogRecord("cortex.test", logging.INFO, "p.py", 1, "m", (), None)
    record.__dict__.update(fields)
    assert row == record_fields(record)


def test_a_record_is_one_line_with_its_newline() -> None:
    line = durable_record({"b": "\u2028", "a": 1})
    assert line == b'{"a":1,"b":"\\u2028"}\n'
