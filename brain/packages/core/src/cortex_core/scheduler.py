"""SubagentScheduler v1: a pure bounded-concurrency admission gate (asyncio, no I/O, see ADR-0010).

Owns policy, not a machine: a counting semaphore caps how many subagents run at once. The
subagent budget is CPU RAM + acceptable concurrency, not VRAM (ADR-0004), so this is a *counting*
budget (distinct from the ``ModelManager``'s exclusive single-GPU lease). ``admit`` blocks until a
slot is free and releases it on exit; over the cap, callers queue (depth-1 delegation guarantees
no spawn waits on another spawn (ADR-0010 decision 6), so this cannot deadlock). Because it does
no I/O it is a pure reference impl of the ``SubagentScheduler`` port, lives in the core, and is
fully covered without a real workload. Hard RAM-ceiling *rejection* is a later refinement.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager


class ConcurrencyScheduler:
    """SubagentScheduler v1: admit up to ``max_concurrency`` subagents at once, queue the rest."""

    def __init__(self, max_concurrency: int) -> None:
        if max_concurrency < 1:
            msg = f"max_concurrency must be >= 1, got {max_concurrency}"
            raise ValueError(msg)
        self._semaphore = asyncio.Semaphore(max_concurrency)

    @asynccontextmanager
    async def admit(self) -> AsyncGenerator[None, None]:
        """Acquire one CPU slot for the block's duration; wait when the budget is full."""
        async with self._semaphore:
            yield
