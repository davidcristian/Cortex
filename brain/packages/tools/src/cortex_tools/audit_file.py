"""JsonLinesAuditSink appends the tool audit trail to a file; TeeAuditSink writes to several."""

import logging
import os
from collections.abc import Sequence
from pathlib import Path

from cortex_core import ToolAuditSink, ToolInvocation, durable_record
from cortex_tools.audit import invocation_fields

_logger = logging.getLogger(__name__)

_GAP = "tool.audit.gap"

# Owner read and write only, because a record contains model-written arguments, which can quote
# whatever the model read earlier in the turn.
_MODE = 0o600

# What a failed append raises: the file system's refusal, or a value the line's own renderer
# cannot render either, such as a non-string key, a cycle, or text that recurses without end.
_GAP_ERRORS = (OSError, TypeError, ValueError, RecursionError)


def durable_line(invocation: ToolInvocation) -> bytes:
    """One invocation as one line of ASCII JSON, its newline included."""
    return durable_record(invocation_fields(invocation))


class JsonLinesAuditSink:
    """ToolAuditSink appending one JSON object per invocation to the file at ``path``."""

    def __init__(self, path: Path) -> None:
        """Remember the file; nothing is opened until the first record."""
        self._path = path

    async def record(self, invocation: ToolInvocation) -> None:
        """Append the invocation, or log a gap, so a trail write never fails a dispatch."""
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
    """ToolAuditSink recording each invocation to every sink it holds, in the order given."""

    def __init__(self, sinks: Sequence[ToolAuditSink]) -> None:
        """Hold the sinks, in recording order."""
        self._sinks = tuple(sinks)

    async def record(self, invocation: ToolInvocation) -> None:
        """Record ``invocation`` to each sink in turn."""
        for sink in self._sinks:
            await sink.record(invocation)
