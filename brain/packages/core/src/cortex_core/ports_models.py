"""Model-lifecycle ports (typing.Protocol): who owns a model process, and who owns residency."""

from contextlib import AbstractAsyncContextManager
from typing import Protocol

from cortex_core.model_host import ControlBounds, DeviceMemory, ModelHostState
from cortex_core.residency_state import ResidencyReport


class ModelHost(Protocol):
    """Starts, stops, and reports one logical model's server process (ADR-0030 decision 3)."""

    async def start(self, model: str) -> None: ...

    async def stop(self, model: str) -> None: ...

    async def status(self, model: str) -> ModelHostState: ...

    async def device_memory(self) -> DeviceMemory | None: ...

    async def control_bounds(self) -> ControlBounds | None: ...


class ResidencyController(Protocol):
    """Changes which model is resident on the GPU, for the duration of a scope (ADR-0030 d5)."""

    def swap_scope(self, model: str) -> AbstractAsyncContextManager[None]: ...

    def handoff_claim(self) -> AbstractAsyncContextManager[None]: ...


class ResidencyReporter(Protocol):
    """Reads what the GPU is serving right now, for the seam to answer with (ADR-0030 d6)."""

    def residency(self) -> ResidencyReport: ...
