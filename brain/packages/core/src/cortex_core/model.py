"""Model Manager v1: pure GPU-lease policies with no swap (no I/O, no process spawn)."""

import asyncio
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass

from cortex_core.errors import ModelUnavailableError
from cortex_core.ports_models import ServingProbe


@dataclass(frozen=True, slots=True)
class ModelLease:
    """A live claim on the GPU for one model; ``endpoint`` serves that model."""

    endpoint: str


@dataclass(frozen=True, slots=True)
class ModelServer:
    """One server of a model, its slot count, and the probe asked before each lease of it."""

    endpoint: str
    slots: int = 1
    probe: ServingProbe | None = None

    def __post_init__(self) -> None:
        if not self.endpoint or self.slots < 1:
            msg = f"ModelServer needs an endpoint and at least one slot, got {self!r}"
            raise ValueError(msg)


def _refuse_other(model: str, resident_model: str) -> None:
    """Raise for any model but the resident one."""
    if model != resident_model:
        msg = f"model {model!r} is not resident (resident: {resident_model!r}); v1 performs no swap"
        raise ModelUnavailableError(msg)


class SingleResidentModelManager:
    """ModelManager v1: one resident model, serialized access, no swap."""

    def __init__(self, resident_model: str, endpoint: str) -> None:
        self._resident_model = resident_model
        self._endpoint = endpoint
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self, model: str) -> AsyncGenerator[ModelLease, None]:
        """Queue for the GPU, then lease the resident model's endpoint."""
        _refuse_other(model, self._resident_model)
        async with self._lock:
            yield ModelLease(endpoint=self._endpoint)


class MultiServerModelManager:
    """ModelManager over several servers of one model: each lease holds one slot of one server."""

    def __init__(self, resident_model: str, servers: Sequence[ModelServer]) -> None:
        if not servers:
            msg = f"MultiServerModelManager for {resident_model!r} needs at least one server"
            raise ValueError(msg)
        self._resident_model = resident_model
        self._servers = tuple(servers)
        self._busy = [0] * len(self._servers)
        self._free_slots = asyncio.Semaphore(sum(server.slots for server in self._servers))

    def _free(self, index: int) -> int:
        """How many slots of one server no lease holds."""
        return self._servers[index].slots - self._busy[index]

    async def _claim(self, model: str) -> int:
        """Hold a slot of a serving server, asking the one with the most free slots first."""
        faults: list[str] = []
        for index in sorted(range(len(self._servers)), key=self._free, reverse=True):
            if self._free(index) < 1:
                continue
            # Held before the probe is awaited, so two callers never claim the same slot.
            self._busy[index] += 1
            probe = self._servers[index].probe
            try:
                fault = None if probe is None else await probe.fault()
            except BaseException:
                # Cancellation included: a slot kept here is never leased again.
                self._busy[index] -= 1
                raise
            if fault is None:
                return index
            self._busy[index] -= 1
            faults.append(fault)
        msg = f"no server of {model!r} with a free slot is serving: {'; '.join(faults)}"
        raise ModelUnavailableError(msg)

    @asynccontextmanager
    async def acquire(self, model: str) -> AsyncGenerator[ModelLease, None]:
        """Wait for a free slot, then lease a serving server, the first listed on a tie."""
        _refuse_other(model, self._resident_model)
        async with self._free_slots:
            index = await self._claim(model)
            try:
                yield ModelLease(endpoint=self._servers[index].endpoint)
            finally:
                self._busy[index] -= 1
