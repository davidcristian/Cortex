"""The control API's wire shape: four routes, two refusal codes, and the lifespan's two duties.

Driven over ``httpx.ASGITransport`` against the real app, so a test asserts the JSON an operator
(and the adapter) actually reads. The lifespan is driven directly, because ASGITransport speaks
only the http scope and would silently skip the boot start and the shutdown stop.

Distrust-green proofs, measured across ``packages/model_manager`` one mutation at a time:

- mapping ``UnknownModelError`` to 503 (dropping the 404 branch) reddens 3 cases, the whole
  parameterization of ``test_an_unknown_id_is_a_404_on_every_route`` and nothing else;
- dropping ``stop_all`` from the lifespan's ``finally`` reddens exactly 1,
  ``test_the_lifespan_starts_the_boot_model_and_stops_everything_on_the_way_down``;
- swallowing a failed boot start without logging it reddens exactly 1,
  ``test_a_boot_start_that_fails_is_logged_and_the_api_still_serves``;
- answering ``/health`` with the shipped default bounds instead of the supervisor's own reddens
  exactly 1, ``test_health_reports_the_daemon_the_roster_and_the_bounds_it_was_wired_with``.
"""

import logging
from http import HTTPStatus
from typing import Any, cast

import httpx
import pytest
from model_host_contract import CORTEX, DEEP
from process_fakes import FakeChildProcesses, FakeProbe
from test_model_host_contract import contract_roster

from cortex_core import DeviceMemory, ModelHostState
from cortex_model_manager import (
    DeviceMemoryProbe,
    ModelSupervisor,
    build_app,
    model_host_lifespan,
    nothing_to_close,
)

_TINY = 0.05
# Deliberately different from the grace, so an app that reported the two bounds in the wrong order
# would be caught rather than pass on a coincidence.
_TINY_REAP = 0.07


def _wired(
    processes: FakeChildProcesses | None = None,
    device: DeviceMemoryProbe | None = None,
) -> tuple[httpx.AsyncClient, ModelSupervisor, FakeProbe]:
    children = processes or FakeChildProcesses()
    probe = FakeProbe()
    supervisor = ModelSupervisor(
        contract_roster(), children, probe, stop_grace_s=_TINY, reap_timeout_s=_TINY_REAP
    )
    app = build_app(supervisor, boot_model=CORTEX, device=device)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://model-host")
    return client, supervisor, probe


def _body(response: httpx.Response) -> dict[str, Any]:
    return cast("dict[str, Any]", response.json())


async def test_health_reports_the_daemon_the_roster_and_the_bounds_it_was_wired_with() -> None:
    """The compose healthcheck's route, and the first thing an operator asks the sidecar.

    The two bounds are on it because the pairing rule (their sum plus the probe timeout below the
    brain's control-call deadline) is enforced nowhere, so what a running daemon actually got has
    to be answerable without reading its container's env. They are read off the supervisor rather
    than restated here, so a supervisor built with other numbers reports the other numbers.
    """
    client, _, _ = _wired()
    try:
        response = await client.get("/health")
    finally:
        await client.aclose()
    assert response.status_code == HTTPStatus.OK
    assert _body(response) == {
        "status": "ok",
        "models": [CORTEX, DEEP],
        "stop_grace_s": _TINY,
        "reap_timeout_s": _TINY_REAP,
        # A daemon wired with no device probe says so rather than omitting the fields, because
        # the brain reads their absence as "cannot see a card" and refuses a checked handoff on
        # it; a missing key and a null must not be two different answers.
        "device_free_mib": None,
        "device_total_mib": None,
    }


async def test_health_reports_what_the_card_has_free_for_the_brains_fit_check() -> None:
    """The reading the brain's swap compares against, on the one route that takes no model lock.

    Deliberately here and not on ``/models/{id}``: a ``status`` queues behind that model's lock,
    so a question asked between an eviction and a load could wait out a whole stop grace. This
    route holds nothing, which is why the fit check can afford to ask it inside a swap step.
    """

    class _Card:
        async def read(self) -> DeviceMemory | None:
            return DeviceMemory(free_mib=22484, total_mib=24463)

    client, _, _ = _wired(device=_Card())
    try:
        body = _body(await client.get("/health"))
    finally:
        await client.aclose()
    assert (body["device_free_mib"], body["device_total_mib"]) == (22484, 24463)


async def test_start_then_status_then_stop_answer_the_state_each_left_behind() -> None:
    client, _, probe = _wired()
    probe.set(contract_roster()[DEEP].health_url, serving=True)
    try:
        started = _body(await client.post(f"/models/{DEEP}/start"))
        seen = _body(await client.get(f"/models/{DEEP}"))
        stopped = _body(await client.post(f"/models/{DEEP}/stop"))
    finally:
        await client.aclose()
    assert started["state"] == ModelHostState.READY.value
    assert seen == started
    assert stopped["state"] == ModelHostState.STOPPED.value
    assert stopped["detail"] == "no process is running"


@pytest.mark.parametrize("path", ["/models/ghost", "/models/ghost/start", "/models/ghost/stop"])
async def test_an_unknown_id_is_a_404_on_every_route(path: str) -> None:
    """An id outside the roster is refused as absent, never as a sick host.

    The two must be distinguishable: "you configured no such tier" and "the sidecar is broken"
    send an operator to different halves of the runbook.
    """
    client, _, _ = _wired()
    method = client.get if path.endswith("ghost") else client.post
    try:
        response = await method(path)
    finally:
        await client.aclose()
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "unknown model 'ghost'" in _body(response)["error"]


async def test_a_supervisor_failure_is_a_503_carrying_its_reason() -> None:
    """A child that survives SIGKILL is the one failure a stop can report, and it reports it."""
    client, supervisor, _ = _wired(FakeChildProcesses(exits_on=None))
    try:
        await supervisor.start(CORTEX)
        response = await client.post(f"/models/{CORTEX}/stop")
    finally:
        await client.aclose()
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert "survived SIGKILL" in _body(response)["error"]


async def test_the_lifespan_starts_the_boot_model_and_stops_everything_on_the_way_down() -> None:
    """ADR-0030's boot default: a stack that never escalates comes up with the cortex serving."""
    processes = FakeChildProcesses()
    probe = FakeProbe()
    supervisor = ModelSupervisor(
        contract_roster(), processes, probe, stop_grace_s=_TINY, reap_timeout_s=_TINY
    )
    closed: list[str] = []

    async def close() -> None:
        closed.append("probe client")

    lifespan = model_host_lifespan(supervisor, CORTEX, close)
    async with lifespan(build_app(supervisor, boot_model=CORTEX)):
        assert len(processes.spawned) == 1
        assert processes.spawned[0].port == contract_roster()[CORTEX].port
        assert (await supervisor.status(CORTEX)).state is ModelHostState.LOADING
    assert processes.spawned[0].signals == ["terminate"]
    assert (await supervisor.status(CORTEX)).state is ModelHostState.STOPPED
    assert closed == ["probe client"]


async def test_a_boot_start_that_fails_is_logged_and_the_api_still_serves(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A crash loop under compose's restart policy would hide the cause; an answering API cannot."""
    processes = FakeChildProcesses()
    supervisor = ModelSupervisor(contract_roster(), processes, FakeProbe())
    app = build_app(supervisor, boot_model="ghost")
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://model-host")
    lifespan = model_host_lifespan(supervisor, "ghost", nothing_to_close)
    try:
        with caplog.at_level(logging.ERROR):
            async with lifespan(app):
                response = await client.get("/health")
    finally:
        await client.aclose()
    assert response.status_code == HTTPStatus.OK
    assert processes.spawned == []
    # Names the tier it failed on: the boot default is configurable, so "a model" is not an answer.
    assert "the boot-default model could not be started; serving without it: model=ghost" in (
        caplog.text
    )
