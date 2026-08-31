"""Behavior tests for the ModelManager v1 policy: leasing, single-resident, serialization.

These pin the ModelManager contract, so the process-lifecycle adapter that replaces this
manager has to pass the same checks against the same port (ADR-0007).
"""

import asyncio

import pytest

from cortex_core import (
    ModelLease,
    ModelManager,
    ModelUnavailableError,
    SingleResidentModelManager,
)

_ENDPOINT = "http://llama-cortex:8080"


def test_manager_satisfies_the_port() -> None:
    """The concrete v1 manager is a structural ModelManager (pins the port signature)."""
    manager: ModelManager = SingleResidentModelManager("cortex", _ENDPOINT)
    assert isinstance(manager, SingleResidentModelManager)


async def test_acquire_resident_leases_the_endpoint() -> None:
    manager = SingleResidentModelManager("cortex", _ENDPOINT)
    async with manager.acquire("cortex") as lease:
        assert lease == ModelLease(endpoint=_ENDPOINT)
        assert lease.endpoint == _ENDPOINT


async def test_acquire_non_resident_raises_without_swap() -> None:
    manager = SingleResidentModelManager("cortex", _ENDPOINT)
    with pytest.raises(ModelUnavailableError, match=r"brain.*not resident"):
        async with manager.acquire("brain"):
            pass  # pragma: no cover - acquire raises before the body runs


async def test_acquire_serializes_concurrent_callers() -> None:
    """The lock keeps two turns from holding the GPU at once (no interleaving)."""
    manager = SingleResidentModelManager("cortex", _ENDPOINT)
    order: list[str] = []

    async def worker(tag: str) -> None:
        async with manager.acquire("cortex"):
            order.append(f"enter-{tag}")
            # Yield control: under a lock-less manager the other task runs here, which
            # produces an interleaved order.
            await asyncio.sleep(0)
            order.append(f"exit-{tag}")

    await asyncio.gather(worker("a"), worker("b"))

    assert order in (
        ["enter-a", "exit-a", "enter-b", "exit-b"],
        ["enter-b", "exit-b", "enter-a", "exit-a"],
    )
