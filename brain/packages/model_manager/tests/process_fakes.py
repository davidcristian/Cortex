"""Fakes for the daemon's two seams: processes that never existed, and a probe a test decides.

The supervisor's whole lifecycle is exercised over these, so the gated suite spawns nothing and
opens no socket. Everything a real child can do to a swap is expressible: exit on SIGTERM, exit
only on SIGKILL, ignore both, die unasked at any moment, and refuse to be spawned at all.
"""

import asyncio
from collections.abc import Sequence

from cortex_model_manager import ChildProcess


class FakeChild:
    """A child process a test drives. ``exits_on`` names the signal it actually honours.

    ``"terminate"`` is the well-behaved case (llama-server exits 0 in a fraction of a second on
    the dev GPU), ``"kill"`` is a wedged child that only SIGKILL ends, and ``None`` is the one
    that survives even that, which is the only case a stop can genuinely fail on.
    """

    def __init__(
        self, argv: Sequence[str], pid: int, *, exits_on: str | None = "terminate"
    ) -> None:
        self.argv = tuple(argv)
        self.signals: list[str] = []
        self.exits_on = exits_on
        self._pid = pid
        self._code: int | None = None
        self._exited = asyncio.Event()

    @property
    def pid(self) -> int:
        return self._pid

    @property
    def returncode(self) -> int | None:
        return self._code

    @property
    def port(self) -> int:
        """The port this child was started for, read off its own argv as an operator would."""
        return int(self.argv[self.argv.index("--port") + 1])

    def terminate(self) -> None:
        self.signals.append("terminate")
        if self.exits_on == "terminate":
            self.exit(0)

    def kill(self) -> None:
        self.signals.append("kill")
        if self.exits_on == "kill":
            self.exit(-9)

    def exit(self, code: int) -> None:
        """Die: what a crash, a bind failure, or an operator's own kill does to a real child."""
        self._code = code
        self._exited.set()

    async def wait(self) -> int:
        await self._exited.wait()
        assert self._code is not None
        return self._code


class FakeChildProcesses:
    """Spawns ``FakeChild``ren, optionally refusing, optionally suspending inside the spawn.

    ``gate`` is what makes the per-model lock testable: a spawn that suspends holds the lock, so a
    second concurrent start genuinely queues behind it instead of merely being called second.
    """

    def __init__(self, *, exits_on: str | None = "terminate") -> None:
        self.spawned: list[FakeChild] = []
        self.error: OSError | None = None
        self.gate: asyncio.Event | None = None
        self._exits_on = exits_on
        self._pid = 4000

    async def spawn(self, argv: Sequence[str]) -> ChildProcess:
        if self.gate is not None:
            await self.gate.wait()
        if self.error is not None:
            raise self.error
        self._pid += 1
        child = FakeChild(argv, self._pid, exits_on=self._exits_on)
        self.spawned.append(child)
        return child

    def last_for(self, port: int) -> FakeChild:
        """The most recent child started for a port, so a test can kill exactly one tier."""
        for child in reversed(self.spawned):
            if child.port == port:
                return child
        msg = f"nothing was ever spawned for port {port}"
        raise KeyError(msg)


class FakeProbe:
    """Whether each child's ``/health`` answers, per URL, as a test decides.

    The default is **not serving**, which is the honest state of a freshly spawned llama-server:
    measured, the socket refuses for a moment and then answers 503 for the whole load.
    """

    def __init__(self) -> None:
        self.answers: dict[str, bool] = {}
        self.probed: list[str] = []

    def set(self, url: str, *, serving: bool) -> None:
        self.answers[url] = serving

    async def serving(self, url: str) -> bool:
        self.probed.append(url)
        return self.answers.get(url, False)
