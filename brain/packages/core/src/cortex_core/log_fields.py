"""The fields a caller attaches to a log record, and how each one is rendered."""

import json
import logging
import re
from collections.abc import Mapping

from cortex_core.log_secrets import REDACTED, is_secret_name, withhold_secrets

CUT = "<cut {chars} chars>"

# The most characters one rendered value may take on a line. A container log driver ends a
# message at 16 KiB, so this is that limit divided by eight, which leaves room for seven cut
# fields on one line; the widest sink today puts five fields past this bound.
VALUE_CHARS = 2048

# The attributes ``logging`` puts on every record itself, plus the two a ``Formatter`` adds.
# Written out rather than read off a sample record, so a Python release that adds one fails a
# test here instead of printing a new stdlib field as if a caller had attached it.
RESERVED_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)

SESSION_FIELD = "session_id"
TURN_FIELD = "turn_id"
TASK_FIELD = "task_id"
ITEM_FIELD = "item_id"
CALL_FIELD = "call_id"

# The userinfo half of a URL: everything between ``://`` and an ``@``. The match ends on that
# ``@``, so nothing may shorten a rendering before this has run over it.
_USERINFO = re.compile(r"(?<=://)[^/\s@]*@")

_BARE = re.compile(r'[^\s"]+')


def redact_urls(text: str) -> str:
    """Return ``text`` with the credential in every URL replaced, wherever in the line it sits."""
    return _USERINFO.sub(f"{REDACTED}@", text)


def record_fields(record: logging.LogRecord) -> dict[str, object]:
    """The fields a caller attached to ``record``, with every secret-named value withheld."""
    return {
        key: REDACTED if is_secret_name(key) else withhold_secrets(value)
        for key, value in record.__dict__.items()
        if key not in RESERVED_ATTRS
    }


def _bound_value(rendering: str) -> str:
    """``rendering`` with its credentials withheld, then cut to ``VALUE_CHARS`` with a marker."""
    text = redact_urls(rendering)
    if len(text) <= VALUE_CHARS:
        return text
    return text[:VALUE_CHARS] + CUT.format(chars=len(text) - VALUE_CHARS)


def render_value(value: object) -> str:
    """One field's value, written so its ``key=value`` pair can be told from the next one."""
    if isinstance(value, str):
        text = value
    elif value is None or isinstance(value, int | float):
        text = str(value)
    else:
        return _bound_value(
            json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
            )
        )
    safe = redact_urls(text)
    if _BARE.fullmatch(safe) and len(safe) <= VALUE_CHARS:
        return safe
    return _bound_value(json.dumps(safe, ensure_ascii=False))


def render_fields(fields: Mapping[str, object]) -> str:
    """The fields as ``key=value`` pairs in name order, on one line."""
    return " ".join(f"{key}={render_value(fields[key])}" for key in sorted(fields))
