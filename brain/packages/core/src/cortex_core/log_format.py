"""The formatters a process entry installs, and the one call that installs one."""

import json
import logging
from collections.abc import Callable, Mapping

from cortex_core.log_fields import record_fields, redact_urls, render_fields

# The two renderings, named in the module docstring's own terms.
PLAIN_FORMAT = "plain"
PACKED_FORMAT = "packed"

# What a deployment gets when it names nothing: the rendering a person reads.
DEFAULT_LOG_FORMAT = PLAIN_FORMAT


class UnknownLogFormatError(ValueError):
    """A deployment named a log rendering this build does not carry."""


class PlainFormatter(logging.Formatter):
    """``levelname:name:message`` exactly as before, then the record's own fields after it."""

    def __init__(self) -> None:
        """Build on the stdlib's own basic format, so the line's first half cannot drift."""
        super().__init__(logging.BASIC_FORMAT)

    def formatMessage(self, record: logging.LogRecord) -> str:  # noqa: N802 - stdlib hook name
        """The formatted message, with the record's fields appended when it carries any."""
        base = super().formatMessage(record)
        fields = record_fields(record)
        if not fields:
            return base
        return f"{base} {render_fields(fields)}"

    def format(self, record: logging.LogRecord) -> str:
        """The whole line, with any URL credential in it withheld (message and traceback alike)."""
        return redact_urls(super().format(record))


class PackedFormatter(logging.Formatter):
    """One JSON object per line: the level, the logger, the message, and the fields under a key."""

    def format(self, record: logging.LogRecord) -> str:
        """The record as one JSON line, with any URL credential in it withheld."""
        payload: dict[str, object] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        fields = record_fields(record)
        if fields:
            payload["fields"] = fields
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return redact_urls(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))


LOG_FORMATS: Mapping[str, Callable[[], logging.Formatter]] = {
    PLAIN_FORMAT: PlainFormatter,
    PACKED_FORMAT: PackedFormatter,
}


def build_formatter(style: str) -> logging.Formatter:
    """The formatter named ``style``, or a typed refusal naming every rendering that exists."""
    build = LOG_FORMATS.get(style)
    if build is None:
        msg = f"unknown log format {style!r}; this build renders {sorted(LOG_FORMATS)}"
        raise UnknownLogFormatError(msg)
    return build()


def configure_logging(level: int | str, *, style: str = DEFAULT_LOG_FORMAT) -> None:
    """Install the root handler this process logs through."""
    handler = logging.StreamHandler()
    handler.setFormatter(build_formatter(style))
    logging.basicConfig(level=level, handlers=[handler], force=True)
