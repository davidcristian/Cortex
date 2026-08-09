"""One behaviour suite over BOTH ``ModelHost`` implementations: the core fake and the real adapter.
"""

from collections.abc import AsyncIterator, Awaitable, Callable

import httpx
import model_host_contract
import pytest
from model_host_contract import CONTRACT_MODELS, HostUnderTest
from process_fakes import FakeChildProcesses, FakeProbe

from cortex_core import ControlBounds, DeviceMemory, ModelHostState, ScriptedModelHost
from cortex_model_manager import (
    HttpModelHost,
    ModelSpec,
    ModelSupervisor,
    TierArgs,
    build_app,
    build_roster,
    nothing_to_close,
    tier_spec,
)

_BIN = "/app/llama-server"
_ENDPOINT = "http://model-host:9300"
# Three distinct sub-second bounds, so a host that reported them in the wrong order, or that
# published the shipped defaults instead of what it was built with, cannot pass on a coincidence.
_BOUNDS = ControlBounds(probe_timeout_s=0.5, stop_grace_s=1.0, reap_timeout_s=1.5)
# The twin is told which boot it is; the supervisor mints its own, so that leg reads it back off
# the daemon rather than declaring it, which is the difference the contract is driven over both to
# expose (a fixture that supplied both sides of the comparison would assert nothing).
_SCRIPTED_BOOT = "scripted-daemon"


def contract_roster() -> dict[str, ModelSpec]:
    """A roster naming exactly the contract's two ids, on the ADR's cortex and deep-tier ports."""
    return build_roster(
        tier_spec(
            _BIN,
            TierArgs(
                model=model,
                model_path=f"/models/{model}.gguf",
                port=port,
                ngl=99,
                ctx_size=4096,
                parallel=1,
            ),
        )
        for model, port in zip(CONTRACT_MODELS, (8080, 8081), strict=True)
    )


class _FakeCard:
    """The daemon's device seam, standing in for a GPU the gated suite may not touch."""

    def __init__(self) -> None:
        self._reading: DeviceMemory | None = None

    def set(self, reading: DeviceMemory | None) -> None:
        self._reading = reading

    async def read(self) -> DeviceMemory | None:
        return self._reading


def _scripted_subject() -> HostUnderTest:
    """The core's scriptable twin: the world's conditions are its status overrides."""
    host = ScriptedModelHost(control_bounds=_BOUNDS, boot_id=_SCRIPTED_BOOT)

    def serving(model: str, *, serving: bool) -> None:
        host.set_status(model, None if serving else ModelHostState.LOADING)

    def die(model: str) -> None:
        host.set_status(model, ModelHostState.FAILED)

    def card(reading: DeviceMemory | None) -> None:
        host.device = reading

    return HostUnderTest(
        host=host,
        serving=serving,
        die=die,
        card=card,
        aclose=nothing_to_close,
        bounds=_BOUNDS,
        boot_id=_SCRIPTED_BOOT,
    )


def _supervisor_subject() -> HostUnderTest:
    """The real adapter over the real daemon: fake children, fake probe, everything else real."""
    roster = contract_roster()
    processes = FakeChildProcesses()
    probe = FakeProbe()
    supervisor = ModelSupervisor(
        roster,
        processes,
        probe,
        stop_grace_s=_BOUNDS.stop_grace_s,
        reap_timeout_s=_BOUNDS.reap_timeout_s,
        probe_timeout_s=_BOUNDS.probe_timeout_s,
    )
    # ASGITransport speaks only the http scope, so the app's lifespan (and therefore its boot
    # start and its shutdown stop) never runs here; test_api.py drives that half directly.
    device = _FakeCard()
    app = build_app(supervisor, boot_model=model_host_contract.CORTEX, device=device)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app))

    def serving(model: str, *, serving: bool) -> None:
        probe.set(roster[model].health_url, serving=serving)

    def die(model: str) -> None:
        processes.last_for(roster[model].port).exit(1)

    return HostUnderTest(
        host=HttpModelHost(_ENDPOINT, client),
        serving=serving,
        die=die,
        card=device.set,
        aclose=client.aclose,
        bounds=_BOUNDS,
        boot_id=supervisor.boot_id,
    )


@pytest.fixture(params=["scripted", "supervisor"])
async def subject(request: pytest.FixtureRequest) -> AsyncIterator[HostUnderTest]:
    """A fresh implementation of each kind; every shared check runs against both."""
    made = _scripted_subject() if request.param == "scripted" else _supervisor_subject()
    try:
        yield made
    finally:
        await made.aclose()


@pytest.mark.parametrize("check", model_host_contract.ALL_CHECKS)
async def test_model_host_contract(
    subject: HostUnderTest, check: Callable[[HostUnderTest], Awaitable[None]]
) -> None:
    await check(subject)
