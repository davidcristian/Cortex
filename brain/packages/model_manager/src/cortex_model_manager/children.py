"""Spawning and signalling one child process: the daemon's OS seam (port + asyncio adapter)."""

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
    """An ``asyncio.subprocess.Process`` behind ``ChildProcess``, absorbing the one race."""

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
                "the child had already exited when the signal was sent",
                extra={"pid": self._process.pid, "signal": name},
            )


class AsyncioChildProcesses:
    """The real spawner: ``asyncio.create_subprocess_exec`` with inherited output streams."""

    async def spawn(self, argv: Sequence[str]) -> ChildProcess:
        process = await asyncio.create_subprocess_exec(*argv)
        return AsyncioChild(process)
