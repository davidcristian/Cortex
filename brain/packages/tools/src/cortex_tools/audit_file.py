"""JsonLinesAuditSink appends the tool audit trail to a file; TeeAuditSink records to several sinks.
"""

import json
import logging
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from cortex_core import ToolAuditSink, ToolInvocation, redact_urls, render_value
from cortex_tools.audit import invocation_fields

_logger = logging.getLogger(__name__)

# The message a gap line is found by: a record this sink could not append.
_GAP = "tool.audit.gap"

# Owner read and write only, because a record carries model-written arguments, which can quote
# whatever the model read earlier in the turn.
_MODE = 0o600

# What a failed append raises: the file system's refusal, or a value the line's own renderer
# cannot render either (a non-string key, a cycle, nesting past the interpreter's depth).
_GAP_ERRORS = (OSError, TypeError, ValueError, RecursionError)


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
    """One field as the file keeps it: the value if the line prints it whole, else the line's text.
    """
    if isinstance(value, bool | int):
        return value
    rendered = render_value(value)
    redacted = _redacted(value)
    try:
        whole = _compact(redacted)
    except ValueError:  # NaN or an infinity, which the line prints and JSON cannot hold
        return rendered
    return redacted if rendered in (redacted, whole) else rendered


def durable_line(invocation: ToolInvocation) -> bytes:
    """One invocation as one line of ASCII JSON, its newline included.

    ASCII output escapes every control character, line separator and lone surrogate, so no value
    can end the record early or fail to encode.
    """
    fields = {name: durable_value(value) for name, value in invocation_fields(invocation).items()}
    text = json.dumps(
        fields, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return f"{text}\n".encode("ascii")


class JsonLinesAuditSink:
    """ToolAuditSink appending one JSON object per invocation to the file at ``path``."""

    def __init__(self, path: Path) -> None:
        """Remember the file; nothing is opened until the first record."""
        self._path = path

    async def record(self, invocation: ToolInvocation) -> None:
        """Append the invocation, or log a gap and return, so a trail write never fails a dispatch.
        """
        try:
            data = durable_line(invocation)
            descriptor = os.open(self._path, os.O_RDWR | os.O_APPEND | os.O_CREAT, _MODE)
            try:
                _append(descriptor, data)
            finally:
                os.close(descriptor)
        except _GAP_ERRORS as error:
            _logger.warning(
                _GAP,
                extra={
                    "path": str(self._path),
                    "tool": invocation.name,
                    "error": f"{type(error).__name__}: {error}",
                },
            )


def _append(descriptor: int, data: bytes) -> None:
    """Write ``data`` whole at the end of the file, opening a fresh line if the last one is torn."""
    size = os.fstat(descriptor).st_size
    if size and os.pread(descriptor, 1, size - 1) != b"\n":
        data = b"\n" + data
    view = memoryview(data)
    while view:
        view = view[os.write(descriptor, view) :]


class TeeAuditSink:
    """ToolAuditSink recording each invocation to every sink it holds, in the order given.

    The composition root puts the logging sink first, so the line an operator already reads is
    written before any other sink is tried.
    """

    def __init__(self, sinks: Sequence[ToolAuditSink]) -> None:
        """Hold the sinks, in recording order."""
        self._sinks = tuple(sinks)

    async def record(self, invocation: ToolInvocation) -> None:
        """Record ``invocation`` to each sink in turn."""
        for sink in self._sinks:
            await sink.record(invocation)
