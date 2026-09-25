"""JsonLinesRecallSink appends the recall trail to a file; TeeRecallSink writes to several."""

import logging
import os
from collections.abc import Sequence
from pathlib import Path

from cortex_core import RecallAudit, RecallAuditSink, durable_record
from cortex_memory.audit import recall_fields

_logger = logging.getLogger(__name__)

_GAP = "memory.recall.gap"

# Owner read and write only, because a record names which memories a session recalled.
_MODE = 0o600


class JsonLinesRecallSink:
    """RecallAuditSink appending one JSON object per recall to the file at ``path``."""

    def __init__(self, path: Path) -> None:
        """Remember the file; nothing is opened until the first record."""
        self._path = path

    async def record(self, audit: RecallAudit) -> None:
        """Append the recall, or log a gap, so a trail write never fails a turn."""
        try:
            data = durable_record(recall_fields(audit))
            descriptor = os.open(self._path, os.O_RDWR | os.O_APPEND | os.O_CREAT, _MODE)
            try:
                _append(descriptor, data)
            finally:
                os.close(descriptor)
        except OSError as error:
            _logger.warning(
                _GAP,
                extra={
                    "path": str(self._path),
                    "turn_id": audit.turn_id,
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


class TeeRecallSink:
    """RecallAuditSink recording each recall to every sink it holds, in the order given."""

    def __init__(self, sinks: Sequence[RecallAuditSink]) -> None:
        """Hold the sinks, in recording order."""
        self._sinks = tuple(sinks)

    async def record(self, audit: RecallAudit) -> None:
        """Record ``audit`` to each sink in turn."""
        for sink in self._sinks:
            await sink.record(audit)
