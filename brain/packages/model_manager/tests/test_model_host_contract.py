"""One behaviour suite over BOTH ``ModelHost`` implementations: the core fake and the real adapter.

The real half is not stubbed HTTP: the adapter talks to a real ``ModelSupervisor`` through a real
Starlette app over ``httpx.ASGITransport``, so a check exercises the adapter's encoding, the API's
routing and refusals, and the supervisor's state machine in one pass. Only the two things a gated
test may not do are faked, the OS spawn and the health socket.

Distrust-green proofs. Each mutation was applied to production code alone and the whole
``packages/model_manager`` suite re-run, so the counts below are what actually reddened, not what
the mutation was aimed at:

- probing ``/health`` **before** reading the child's exit code in ``ModelSupervisor.status``
  reddens 3 cases: ``[supervisor-check_a_process_that_died_unasked_reports_failed]``,
  ``[supervisor-check_a_failed_model_is_restarted_without_being_stopped_first]``, and
  ``test_supervisor.py::test_status_reads_the_exit_code_without_asking_the_probe_at_all``. No
  scripted case reddens, which is the point: that ordering is the real adapter's whole defence
  against a dead start whose port is still answered by the model it was meant to replace;
- reporting an absent child as LOADING instead of STOPPED reddens 10 cases, 4 of them here, all on
  the supervisor side (``check_a_model_nobody_started_reports_stopped``,
  ``check_stop_ends_the_model_and_is_idempotent``,
  ``check_stopping_a_model_that_already_died_settles_it`` and
  ``check_a_swap_leaves_only_the_model_it_swapped_in``), the rest in the supervisor and api suites
  over the same production code;
- keeping (rather than replacing) a child that exited when ``start`` is re-issued reddens exactly
  1 case, ``[supervisor-check_a_failed_model_is_restarted_without_being_stopped_first]``, which is
  why that check exists separately from the stop-then-start one;
- returning ``ModelHostState.READY`` from the adapter instead of the reported word reddens 11
  cases: 7 here on the supervisor side and 4 in ``test_adapter.py``;
- dropping ``probe_timeout_s`` from the daemon's health body reddens 2, the supervisor leg of
  ``check_a_host_reports_the_control_bounds_it_was_wired_with`` and ``test_api.py``'s health case.
  No scripted case reddens, which is again the point: the twin echoes the bounds it was handed, and
  what the supervisor leg pins is that a real daemon publishes the three it was really given;
- dropping ``boot_id`` from that body reddens 2 in exactly the same shape, the supervisor leg of
  ``check_a_host_names_which_boot_of_it_is_answering`` and that same health case;
- collapsing a tier's 404 back into the broad ``ModelHostError`` reddens 2, the supervisor leg of
  ``check_an_id_this_host_does_not_carry_is_refused_by_every_verb`` and one row of
  ``test_adapter.py``'s status table. No scripted case reddens, for the usual reason: the twin is
  **told** which ids it does not host, while the real leg has to derive the same answer from a
  roster it built and a status code it read;
- letting the twin serve every id it is handed reddens 5, both scripted legs of the two unhosted
  checks and the three core cases that arrange the condition over it, which is the mirror image
  and the reason a fake that could not refuse would leave the distinction untestable in the core.
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
# An id neither fixture's host carries: the supervisor's roster is built from ``CONTRACT_MODELS``
# and never sees it, and the twin is told. It is named for the deployment that produces the
# condition, escalation turned on with no artifact declared for the deep tier.
_UNROSTERED = "tier-with-no-artifact"


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
    """The daemon's device seam, standing in for a GPU the gated suite may not touch.

    The real ``nvidia-smi`` call is exercised by ``test_device_memory.py`` over a stand-in process
    and by the live suite against a real card; what this contributes is the world-condition the
    shared checks arrange, so the adapter's own encoding of both answers is driven end to end
    through a real Starlette app.
    """

    def __init__(self) -> None:
        self._reading: DeviceMemory | None = None

    def set(self, reading: DeviceMemory | None) -> None:
        self._reading = reading

    async def read(self) -> DeviceMemory | None:
        return self._reading


def _scripted_subject() -> HostUnderTest:
    """The core's scriptable twin: the world's conditions are its status overrides."""
    host = ScriptedModelHost(control_bounds=_BOUNDS, boot_id=_SCRIPTED_BOOT, unhosted=[_UNROSTERED])

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
        unhosted=_UNROSTERED,
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
        unhosted=_UNROSTERED,
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
