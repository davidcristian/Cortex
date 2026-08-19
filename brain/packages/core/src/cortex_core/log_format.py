"""The formatters a process entry installs, and the one call that installs one.

Until this module existed, every brain process configured logging with a bare
``logging.basicConfig(level=...)``, which installs the stdlib's own format and therefore prints
``levelname:name:message`` and nothing else. Every ``extra`` field this repo attaches, a rejected
fold's ``capped`` and ``chars``, a stranded ``handoff``, a retried ``task_id``, a forgone recall's
``session_id``, was written onto the record and dropped on the floor, and three adapters had grown
their own hand-rolled second rendering into the message to work around it one line at a time.

**Two renderings, and the default is the plain one because of who reads these logs.** This is a
personal, local-first assistant whose operator reads ``docker compose logs brain`` in a terminal,
and that stream is *mixed*: uvicorn writes its own access lines, llama.cpp writes raw stderr, and
neither will ever be JSON. A JSON-lines default would therefore not buy a machine-readable stream
(nothing could parse the whole of it) while costing the one reader who exists the ability to read
a line at a glance. So ``plain`` appends ``key=value`` pairs after the message: legible, greppable
by the same patterns the runbooks already carry, and additive, since the part before the fields is
byte for byte what ``basicConfig`` printed before.

``packed`` is the other rendering, one JSON object per line, for a deployment that would rather
collect than read. It exists because the choice belongs to the deployment rather than to this
file, and it is selected by env like everything else here. Its fields sit under their own
``fields`` key rather than at the top level, so no attached field can ever shadow ``level``,
``logger`` or ``message``, and ``jq .fields.capped`` is a stable path.

**Naming.** The pair is one family: how a record's fields are set down for whoever reads them,
laid out plainly beside the message or packed into one carton for transport. The alternates
considered were ``plain``/``json``, rejected because it names one entry for its wire format and
the other for its lack of one (no shared metaphor, and a third rendering would have nowhere to
stand), and ``loose``/``sealed``, rejected as evocative at the cost of an operator reading an env
file at three in the morning.

**Secrets.** Both renderings withhold by the same rules, in ``log_fields.py``: a field named for a
secret never prints its value, and a URL's credential is stripped from the whole rendered line,
message and traceback included. A formatter that appends whatever a record happens to carry is the
one change in this repo that could turn a careless ``extra=`` into a leak, so the defence is part
of the formatter rather than an obligation on its callers.
"""

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
    """A deployment named a log rendering this build does not carry.

    Raised at the process entry, before anything is served, because a typo in the env is a
    configuration fault and a process that quietly fell back to a default would leave an operator
    reading the wrong shape while believing they had chosen the other one.
    """


class PlainFormatter(logging.Formatter):
    """``levelname:name:message`` exactly as before, then the record's own fields after it.

    The fields are appended in ``formatMessage`` rather than in ``format`` on purpose: that is the
    hook the stdlib calls *before* it appends a traceback, so a warning that carries both prints
    its fields on the first line where a reader and a ``grep`` will find them, rather than after
    twenty lines of stack.
    """

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
    """Install the root handler this process logs through.

    The one function in the core that changes process-wide state, and it is called only from a
    process entry, never from a library: handler configuration belongs at the entry and nowhere
    else. ``force`` is set because an entry point is stating what this process logs like rather
    than asking, and ``basicConfig`` without it is a no-op the moment anything has already
    attached a handler.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(build_formatter(style))
    logging.basicConfig(level=level, handlers=[handler], force=True)
