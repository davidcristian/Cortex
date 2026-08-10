"""The MemoryStore contract over the in-memory fake, in CI, from the same file the live run uses."""

from collections.abc import Awaitable, Callable

import memory_contract
import pytest

from cortex_core import InMemoryMemoryStore, MemoryStore


@pytest.mark.parametrize("check", memory_contract.ALL_CHECKS, ids=lambda check: check.__name__)
async def test_in_memory_store_satisfies_the_contract(
    check: Callable[[MemoryStore], Awaitable[None]],
) -> None:
    await check(InMemoryMemoryStore())
