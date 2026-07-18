"""Spawning and signalling one child process: the daemon's OS seam (port + asyncio adapter).

The supervisor's lifecycle logic is gated at 100% over a fake of these two protocols; the real
``asyncio`` calls live here, in the thinnest wrapper that can hold them (AGENTS.md gate 3). Two
deliberate choices, both measured rather than assumed:

- **The child inherits the daemon's stdout and stderr.** No pipe is created, so nothing can wedge
  when llama.cpp's loading log outruns a buffer nobody drains, and ``docker logs model-host``
  shows the daemon and every child interleaved, which is what an operator wants during a swap.
  The cost is that a failed child's reason is in the container log rather than in the control
  API's ``detail``, which carries the exit code instead.
- **No new session or process group.** The child stays in the daemon's, so a container the
  runtime tears down takes the child with it and no ``llama-server`` can outlive the container
  holding the GPU reservation. The daemon still stops its children on shutdown, for the graceful
  path; this is the backstop for the ungraceful one.

Reaping needs no explicit collector: asyncio's child watcher reaps on its own, so ``returncode``
becomes non-``None`` for a child that died unasked without anybody awaiting it, which is exactly
what the supervisor's status reads before it trusts a health probe.
"""

import asyncio
import logging
from collections.abc import Callable, Sequence
from typing import Protocol

_logger = logging.getLogger(__name__)


class ChildProcess(Protocol):
    """One spawned process, as the supervisor sees it: an id, an exit code, and two signals."""

    @property
    def pid(self) -> int: ...

    @property
    def returncode(self) -> int | None: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...

    async def wait(self) -> int: ...


class ChildProcesses(Protocol):
    """Starts one child from a complete argv. The only OS write the daemon performs."""

    async def spawn(self, argv: Sequence[str]) -> ChildProcess: ...


class AsyncioChild:
    """An ``asyncio.subprocess.Process`` behind ``ChildProcess``, absorbing the one race.

    ``terminate``/``kill`` raise ``ProcessLookupError`` when the child has already exited, which
    is not an error for either caller here: the supervisor's whole point is to end a process, and
    a process that ended on its own between the status read and the signal has done that. The
    exit code is still readable afterwards, so nothing is lost by treating it as success.
    """

    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self._process = process

    @property
    def pid(self) -> int:
        return self._process.pid

    @property
    def returncode(self) -> int | None:
        return self._process.returncode

    def terminate(self) -> None:
        self._signal(self._process.terminate, "SIGTERM")

    def kill(self) -> None:
        self._signal(self._process.kill, "SIGKILL")

    async def wait(self) -> int:
        return await self._process.wait()

    def _signal(self, send: Callable[[], None], name: str) -> None:
        try:
            send()
        except ProcessLookupError:
            _logger.info(
                "the child had already exited when the signal was sent: pid=%d signal=%s",
                self._process.pid,
                name,
                extra={"pid": self._process.pid, "signal": name},
            )


class AsyncioChildProcesses:
    """The real spawner: ``asyncio.create_subprocess_exec`` with inherited output streams."""

    async def spawn(self, argv: Sequence[str]) -> ChildProcess:
        process = await asyncio.create_subprocess_exec(*argv)
        return AsyncioChild(process)
