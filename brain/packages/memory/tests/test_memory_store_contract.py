"""The MemoryStore contract over the in-memory fake, in CI, from the same file the live run uses.

Ports before adapters: the real adapter must pass the same contract test as the fake (AGENTS.md).
That held for memory only in halves until now, `memory_contract.ALL_CHECKS` being driven solely by
the integration run against real pgvector while the fake was checked by hand in `cortex_core`'s own
tests. So a check added to the shared file reached CI only if someone remembered to write it twice,
and the candidate-count checks (ADR-0038 candidate-count addendum) are exactly the kind that must
bite on both sides: a count is trivial to fake as a length over rows, and that mistake is invisible
to a suite nobody runs without a database.

This is the TaskStore/ScheduleStore arrangement (`test_task_store_contract.py`), minus their second
implementation: the pgvector adapter needs a server, so its arm of the same suite stays in
`test_pgvector_live.py`, and only the fake is exercisable without one.
"""

from collections.abc import Awaitable, Callable

import memory_contract
import pytest

from cortex_core import InMemoryMemoryStore, MemoryStore


@pytest.mark.parametrize("check", memory_contract.ALL_CHECKS, ids=lambda check: check.__name__)
async def test_in_memory_store_satisfies_the_contract(
    check: Callable[[MemoryStore], Awaitable[None]],
) -> None:
    await check(InMemoryMemoryStore())
