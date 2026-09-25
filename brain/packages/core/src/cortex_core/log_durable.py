"""How a trail file keeps a log line's fields: no more than the line prints, one ASCII line each."""

import json
from collections.abc import Mapping, Sequence
from typing import cast

from cortex_core.log_fields import redact_urls, render_value
from cortex_core.log_secrets import REDACTED, is_secret_name, withhold_secrets


def _redacted(value: object) -> object:
    """``value`` with the credential withheld from every URL in every string, keys included."""
    if isinstance(value, str):
        return redact_urls(value)
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, Mapping):
        mapping = cast("Mapping[object, object]", value)
        return {redact_urls(str(key)): _redacted(item) for key, item in mapping.items()}
    if isinstance(value, list | tuple):
        return [_redacted(item) for item in cast("Sequence[object]", value)]
    return redact_urls(str(value))


def _compact(value: object) -> str:
    """``value`` as the line's formatter writes a structure, refusing a non-finite number."""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def durable_value(value: object) -> object:
    """One field as the file keeps it: the value if the line prints it whole, else its text."""
    if isinstance(value, bool | int):
        return value
    value = withhold_secrets(value)
    rendered = render_value(value)
    redacted = _redacted(value)
    try:
        whole = _compact(redacted)
    except ValueError:
        return rendered
    return redacted if rendered in (redacted, whole) else rendered


def durable_record(fields: Mapping[str, object]) -> bytes:
    """A log line's fields as one line of ASCII JSON, its newline included."""
    kept = {
        name: REDACTED if is_secret_name(name) else durable_value(value)
        for name, value in fields.items()
    }
    text = json.dumps(
        kept, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return f"{text}\n".encode("ascii")
