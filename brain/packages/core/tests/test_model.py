import asyncio
from collections.abc import Callable

import pytest

from cortex_core import (
    ModelLease,
    ModelManager,
    ModelServer,
    ModelUnavailableError,
    MultiServerModelManager,
    ScriptedServingProbe,
    SingleResidentModelManager,
)

_ENDPOINT = "http://llama-cortex:8080"
_SECOND = "http://llama-cortex:8084"


def _single() -> ModelManager:
    return SingleResidentModelManager("cortex", _ENDPOINT)


def _one_server_one_slot() -> ModelManager:
    return MultiServerModelManager("cortex", [ModelServer(_ENDPOINT)])


_ONE_AT_A_TIME = pytest.mark.parametrize("build", [_single, _one_server_one_slot])


async def _overlap(manager: ModelManager, callers: int) -> tuple[int, list[str]]:
    """Run ``callers`` leases at once: the most held together, and each endpoint leased."""
    held = 0
    peak = 0
    endpoints: list[str] = []

    async def worker() -> None:
        nonlocal held, peak
        async with manager.acquire("cortex") as lease:
            held += 1
            peak = max(peak, held)
            endpoints.append(lease.endpoint)
            await asyncio.sleep(0)
            held -= 1

    await asyncio.gather(*(worker() for _ in range(callers)))
    return peak, endpoints


@_ONE_AT_A_TIME
async def test_acquire_resident_leases_the_endpoint(build: Callable[[], ModelManager]) -> None:
    async with build().acquire("cortex") as lease:
        assert lease == ModelLease(endpoint=_ENDPOINT)


@_ONE_AT_A_TIME
async def test_acquire_non_resident_raises_without_swap(
    build: Callable[[], ModelManager],
) -> None:
    with pytest.raises(ModelUnavailableError, match=r"brain.*not resident"):
        async with build().acquire("brain"):
            pass  # pragma: no cover - acquire raises before the body runs


@_ONE_AT_A_TIME
async def test_acquire_serializes_concurrent_callers(build: Callable[[], ModelManager]) -> None:
    peak, endpoints = await _overlap(build(), 3)
    assert peak == 1
    assert endpoints == [_ENDPOINT] * 3


async def test_two_servers_of_one_slot_run_two_callers_on_different_servers() -> None:
    manager = MultiServerModelManager("cortex", [ModelServer(_ENDPOINT), ModelServer(_SECOND)])
    peak, endpoints = await _overlap(manager, 2)
    assert peak == 2
    assert sorted(endpoints) == [_ENDPOINT, _SECOND]


async def test_a_third_caller_waits_for_a_slot_on_two_servers_of_one_slot() -> None:
    manager = MultiServerModelManager("cortex", [ModelServer(_ENDPOINT), ModelServer(_SECOND)])
    peak, endpoints = await _overlap(manager, 3)
    assert peak == 2
    assert len(endpoints) == 3


async def test_one_server_of_two_slots_runs_two_callers_on_that_server() -> None:
    manager = MultiServerModelManager("cortex", [ModelServer(_ENDPOINT, slots=2)])
    peak, endpoints = await _overlap(manager, 3)
    assert peak == 2
    assert endpoints == [_ENDPOINT] * 3


async def test_a_lease_goes_to_the_server_with_the_most_free_slots() -> None:
    manager = MultiServerModelManager(
        "cortex", [ModelServer(_ENDPOINT, slots=2), ModelServer(_SECOND, slots=2)]
    )
    async with (
        asyncio.timeout(5.0),
        manager.acquire("cortex") as first,
        manager.acquire("cortex") as second,
    ):
        assert (first.endpoint, second.endpoint) == (_ENDPOINT, _SECOND)
        async with manager.acquire("cortex") as third:
            assert third.endpoint == _ENDPOINT


async def test_a_lease_that_ends_in_an_error_frees_its_slot() -> None:
    manager = MultiServerModelManager("cortex", [ModelServer(_ENDPOINT), ModelServer(_SECOND)])
    broke = RuntimeError("the stream broke")
    with pytest.raises(RuntimeError, match="the stream broke"):
        async with manager.acquire("cortex"):
            raise broke
    async with manager.acquire("cortex") as lease:
        assert lease.endpoint == _ENDPOINT


class _YieldingProbe:
    part = "a server that answers after a pause"

    async def fault(self) -> str | None:
        await asyncio.sleep(0)
        return None


def _probed(
    first: str | None, second: str | None
) -> tuple[MultiServerModelManager, list[ScriptedServingProbe]]:
    probes = [ScriptedServingProbe(answer=first), ScriptedServingProbe(answer=second)]
    servers = [ModelServer(_ENDPOINT, probe=probes[0]), ModelServer(_SECOND, probe=probes[1])]
    return MultiServerModelManager("cortex", servers), probes


@pytest.mark.parametrize("fault", ["the first server is stopped", "the first server is loading"])
async def test_a_lone_caller_is_leased_the_server_that_serves(fault: str) -> None:
    manager, _ = _probed(fault, None)
    for _ in range(2):
        async with manager.acquire("cortex") as lease:
            assert lease.endpoint == _SECOND


async def test_no_lease_is_given_when_no_server_serves_and_every_fault_is_named() -> None:
    manager, _ = _probed("the first is stopped", "the second is loading")
    with pytest.raises(
        ModelUnavailableError,
        match=r"no server of 'cortex' .* is serving: the first is stopped; the second is loading",
    ):
        async with manager.acquire("cortex"):
            pass  # pragma: no cover - acquire raises before the body runs


async def test_a_server_is_asked_again_on_every_lease() -> None:
    manager, probes = _probed("the first is loading", "the second is stopped")
    with pytest.raises(ModelUnavailableError):
        async with manager.acquire("cortex"):
            pass  # pragma: no cover - acquire raises before the body runs
    probes[0].answer = None
    async with manager.acquire("cortex") as first:
        assert first.endpoint == _ENDPOINT
        probes[1].answer = None
        async with manager.acquire("cortex") as second:
            assert second.endpoint == _SECOND
    assert [probe.calls for probe in probes] == [2, 2]


async def test_a_second_caller_is_refused_while_the_one_serving_server_is_leased() -> None:
    manager, _ = _probed("the first is stopped", None)
    async with manager.acquire("cortex") as lease:
        assert lease.endpoint == _SECOND
        with pytest.raises(ModelUnavailableError, match=r"is serving: the first is stopped$"):
            async with manager.acquire("cortex"):
                pass  # pragma: no cover - acquire raises before the body runs


async def test_two_callers_asking_at_once_are_leased_different_servers() -> None:
    servers = [
        ModelServer(_ENDPOINT, probe=_YieldingProbe()),
        ModelServer(_SECOND, probe=_YieldingProbe()),
    ]
    peak, endpoints = await _overlap(MultiServerModelManager("cortex", servers), 2)
    assert peak == 2
    assert sorted(endpoints) == [_ENDPOINT, _SECOND]


class _BreakingProbe:
    part = "a server whose probe raises once"

    def __init__(self) -> None:
        self.broken = True

    async def fault(self) -> str | None:
        if self.broken:
            self.broken = False
            msg = "the probe broke"
            raise RuntimeError(msg)
        return None


async def test_a_probe_that_raises_leaves_its_server_one_free_slot() -> None:
    servers = [ModelServer(_ENDPOINT, probe=_BreakingProbe()), ModelServer(_SECOND)]
    manager = MultiServerModelManager("cortex", servers)
    with pytest.raises(RuntimeError, match="the probe broke"):
        async with manager.acquire("cortex"):
            pass  # pragma: no cover - acquire raises before the body runs
    peak, endpoints = await _overlap(manager, 2)
    assert peak == 2
    assert sorted(endpoints) == [_ENDPOINT, _SECOND]


async def test_a_lease_cancelled_while_its_probe_is_asked_leaves_its_slot() -> None:
    probe = ScriptedServingProbe()
    probe.silent = True
    manager = MultiServerModelManager("cortex", [ModelServer(_ENDPOINT, probe=probe)])

    async def lease() -> None:
        async with manager.acquire("cortex"):
            pass  # pragma: no cover - the probe never answers

    waiting = asyncio.create_task(lease())
    await asyncio.sleep(0)
    assert probe.calls == 1
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting
    probe.silent = False
    async with manager.acquire("cortex") as held:
        assert held.endpoint == _ENDPOINT


def test_a_manager_over_no_server_is_rejected() -> None:
    with pytest.raises(ValueError, match="needs at least one server"):
        MultiServerModelManager("cortex", [])


@pytest.mark.parametrize(("endpoint", "slots"), [("", 1), (_ENDPOINT, 0)])
def test_a_server_needs_an_endpoint_and_a_slot(endpoint: str, slots: int) -> None:
    with pytest.raises(ValueError, match="needs an endpoint and at least one slot"):
        ModelServer(endpoint, slots)
