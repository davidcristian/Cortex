import memory_contract
import pytest

from cortex_core import InMemoryMemoryStore, MemoryStoreError


@pytest.mark.parametrize("check", memory_contract.ALL_CHECKS, ids=lambda check: check.__name__)
async def test_in_memory_store_satisfies_the_contract(check: memory_contract.Check) -> None:
    store = InMemoryMemoryStore()

    async def break_backend() -> None:
        """The fake's twin of closing a pool: every later verb raises what the port owes."""
        store.fail_with(MemoryStoreError("the memory store is unreachable"))

    await check(memory_contract.MemoryStoreUnderTest(store=store, break_backend=break_backend))
