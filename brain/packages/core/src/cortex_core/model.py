"""Model Manager v1: pure single-resident GPU-lease policy (no I/O, no process spawn)."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from cortex_core.errors import ModelUnavailableError


@dataclass(frozen=True, slots=True)
class ModelLease:
    """A live claim on the GPU for one model; ``endpoint`` serves that model."""

    endpoint: str


class SingleResidentModelManager:
    """ModelManager v1: one resident model, serialized access, no swap."""

    def __init__(self, resident_model: str, endpoint: str) -> None:
        self._resident_model = resident_model
        self._endpoint = endpoint
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self, model: str) -> AsyncGenerator[ModelLease, None]:
        """Queue for the GPU, then lease the resident model's endpoint."""
        if model != self._resident_model:
            msg = (
                f"model {model!r} is not resident (resident: {self._resident_model!r}); "
                "v1 performs no swap"
            )
            raise ModelUnavailableError(msg)
        async with self._lock:
            yield ModelLease(endpoint=self._endpoint)
