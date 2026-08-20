"""What a record carries beyond the standard attributes, and how those fields are written down."""

import json
import logging
import re
from collections.abc import Mapping

# What stands in for a value this module will not print. Visible on purpose, per the docstring.
REDACTED = "<redacted>"

# What stands in for the rest of a value the bound below cut, naming how many characters went.
# Sibling of REDACTED in shape, since both are the formatter speaking rather than the record.
CUT = "<cut {chars} chars>"

VALUE_CHARS = 2048

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

# Substrings that make a field name too dangerous to print, matched case-insensitively so
# ``apiKey`` and ``API_KEY`` are the same name. Every concrete secret this deployment holds is
# named for what it is: the seam token, the mail bridge's password, a model host's credential.
SECRET_NAMES = (
    "apikey",
    "api_key",
    "authorization",
    "cookie",
    "credential",
    "passwd",
    "password",
    "secret",
    "token",
)

_USERINFO = re.compile(r"(?<=://)[^/\s@]*@")

# A value that can be printed as it stands: one token, no whitespace to run it into the next
# field and no quote of its own to confuse the one this module would otherwise add.
_BARE = re.compile(r'[^\s"]+')


def is_secret_name(key: str) -> bool:
    """Whether a field name is one whose value no log line may carry."""
    lowered = key.lower()
    return any(marker in lowered for marker in SECRET_NAMES)


def redact_urls(text: str) -> str:
    """Return ``text`` with the credential in every URL replaced, wherever in the line it sits."""
    return _USERINFO.sub(f"{REDACTED}@", text)


def record_fields(record: logging.LogRecord) -> dict[str, object]:
    """The fields a caller attached to ``record``, with every secret-named value withheld."""
    return {
        key: REDACTED if is_secret_name(key) else value
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
    """One field's value, written so the pair it sits in can still be told from the next one."""
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
