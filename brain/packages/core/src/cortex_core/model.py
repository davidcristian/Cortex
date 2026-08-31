"""Model Manager v1: pure single-resident GPU-lease policy (no I/O, no process spawn).

It owns policy rather than a GPU: one model is resident, and callers are serialized so only one
turn touches the GPU at a time. The resident ``llama-server`` is brought up out-of-band
(``docker-compose.gpu.yml``, ADR-0005); this object hands out its endpoint under a lease and
raises for any other model, since v1 performs no swap. Because it does no I/O it is a
pure reference implementation of the ``ModelManager`` port, lives in the core, and is fully
covered without a GPU (ADR-0007 decision 3).
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from cortex_core.errors import ModelUnavailableError


@dataclass(frozen=True, slots=True)
class ModelLease:
    """A live claim on the GPU for one model; ``endpoint`` serves that model.

    Valid only inside the ``async with model_manager.acquire(...)`` block that yields it;
    leaving the block releases the GPU to the next waiter. ``endpoint`` is the base URL of
    that model's ``llama-server`` (ADR-0005).
    """

    endpoint: str


class SingleResidentModelManager:
    """ModelManager v1: one resident model, serialized access, no swap (ADR-0007 d3).

    ``endpoint`` is the base URL of the resident model's ``llama-server``, handed in at
    the composition root (never discovered here, since this stays pure).
    """

    def __init__(self, resident_model: str, endpoint: str) -> None:
        self._resident_model = resident_model
        self._endpoint = endpoint
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self, model: str) -> AsyncGenerator[ModelLease, None]:
        """Queue for the GPU, then lease the resident model's endpoint.

        Raises ``ModelUnavailableError`` for any model other than the resident one, since v1
        performs no swap. The lock serializes callers; its waiter queue is the
        queue API, so a second turn blocks until the first releases the lease.
        """
        if model != self._resident_model:
            msg = (
                f"model {model!r} is not resident (resident: {self._resident_model!r}); "
                "v1 performs no swap"
            )
            raise ModelUnavailableError(msg)
        async with self._lock:
            yield ModelLease(endpoint=self._endpoint)
