"""The control API's wire shape: four routes, two refusal codes, and the lifespan's two duties.

Driven over ``httpx.ASGITransport`` against the real app, so a test asserts the JSON an operator
(and the adapter) actually reads. The lifespan is driven directly, because ASGITransport speaks
only the http scope and would silently skip the boot start and the shutdown stop.

These checks were proved able to fail. Each mutation below was measured across
``packages/model_manager``, one at a time, and every count is over that suite:

- mapping ``UnknownModelError`` to 503 (dropping the 404 branch) fails 3 cases, the whole
  parameterization of ``test_an_unknown_id_is_a_404_on_every_route`` and nothing else;
- dropping ``stop_all`` from the lifespan's ``finally`` fails exactly 1,
  ``test_the_lifespan_starts_the_boot_model_and_stops_everything_on_the_way_down``;
- swallowing a failed boot start without logging it fails exactly 1,
  ``test_a_boot_start_that_fails_is_logged_and_the_api_still_serves``;
- answering ``/health`` with the shipped default bounds instead of the supervisor's own fails
  exactly 1, ``test_health_reports_the_daemon_the_roster_and_the_bounds_it_was_wired_with``;
- dropping ``probe_timeout_s`` from the health body fails 2, that same case and the shared
  contract's supervisor leg, and no scripted case: it is the term the brain cannot infer from the
  other two, and the term a two-term reading of the pairing rule already once left out;
- dropping ``boot_id`` from that body fails 2 in the same shape, that case and the contract's
  supervisor leg, and again no scripted case: the twin echoes the id it was handed, while what
  the supervisor leg pins is that a real daemon publishes the one it actually minted.

Three more for the refusal's own line, once the supervisor stopped printing what it raises, each
applied to production code alone with the whole brain workspace re-run:

- logging every refusal at ``WARNING`` again fails exactly 1, the 503 case, which is the whole
  of what the level following the status code is for;
- logging every refusal at ``ERROR`` fails 3, the 404 parameterization, so the rule is pinned
  from both sides rather than only from the loud one;
- dropping the refusal's ``error`` field fails exactly 1, the 503 case: that field is where the
  sentence went when the raise stopped printing it, so nothing else would notice it gone.
"""

import logging
from http import HTTPStatus
from typing import Any, cast

import httpx
import pytest
from model_host_contract import CORTEX, DEEP
from process_fakes import FakeChildProcesses, FakeProbe
from test_model_host_contract import contract_roster

from cortex_core import DeviceMemory, ModelHostState, PlainFormatter, record_fields
from cortex_model_manager import (
    DeviceMemoryProbe,
    ModelSupervisor,
    build_app,
    model_host_lifespan,
    nothing_to_close,
)

_TINY = 0.05
# Deliberately different from the grace, so an app that reported the three bounds in the wrong
# order would be caught rather than pass on a coincidence.
_TINY_REAP = 0.07
_TINY_PROBE = 0.03


def _wired(
    processes: FakeChildProcesses | None = None,
    device: DeviceMemoryProbe | None = None,
) -> tuple[httpx.AsyncClient, ModelSupervisor, FakeProbe]:
    children = processes or FakeChildProcesses()
    probe = FakeProbe()
    supervisor = ModelSupervisor(
        contract_roster(),
        children,
        probe,
        stop_grace_s=_TINY,
        reap_timeout_s=_TINY_REAP,
        probe_timeout_s=_TINY_PROBE,
    )
    app = build_app(supervisor, boot_model=CORTEX, device=device)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://model-host")
    return client, supervisor, probe


def _body(response: httpx.Response) -> dict[str, Any]:
    return cast("dict[str, Any]", response.json())


async def test_health_reports_the_daemon_the_roster_and_the_bounds_it_was_wired_with() -> None:
    """The compose healthcheck's route, and the first thing an operator asks the sidecar.

    All three bounds are on it because the pairing rule (their sum below the brain's control-call
    deadline) spans two containers' env, so what a running daemon actually got has to be
    answerable without reading that env: an operator asks by hand, and the brain asks at wiring
    time. They are read off the supervisor rather than restated here, so a supervisor built with
    other numbers reports the other numbers.
    """
    client, supervisor, _ = _wired()
    try:
        response = await client.get("/health")
    finally:
        await client.aclose()
    assert response.status_code == HTTPStatus.OK
    assert _body(response) == {
        "status": "ok",
        "models": [CORTEX, DEEP],
        # Read off the supervisor for the same reason the bounds are: a route that minted its own
        # would name a boot nothing in the process shares, and the brain compares this against
        # what it was told last rather than against anything it can derive.
        "boot_id": supervisor.boot_id,
        "probe_timeout_s": _TINY_PROBE,
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
async def test_an_unknown_id_is_a_404_on_every_route(
    path: str, caplog: pytest.LogCaptureFixture
) -> None:
    """An id outside the roster is refused as absent, never as a failing host.

    The two must be distinguishable: "you configured no such tier" and "the sidecar is broken"
    send an operator to different halves of the runbook. The log level is the same distinction
    said again to whoever is reading the container rather than the response: this is a caller
    asking after a tier that was never configured, so it is a line and no more.
    """
    client, _, _ = _wired()
    method = client.get if path.endswith("ghost") else client.post
    try:
        with caplog.at_level(logging.WARNING):
            response = await method(path)
    finally:
        await client.aclose()
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "unknown model 'ghost'" in _body(response)["error"]
    assert [(record.levelno, record.message) for record in caplog.records] == [
        (logging.WARNING, "a model-host request failed")
    ]


async def test_a_supervisor_failure_is_a_503_logged_once_and_loudly(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A child that survives SIGKILL is the one failure a stop can report, and it reports it once.

    The supervisor raises the sentence and does not also log it, so the two records here are two
    events, the escalation to SIGKILL and the refusal that came of it, rather than the refusal
    printed twice with its numbers in the prose and in the fields beside them.

    The refusal is at ERROR, which is what a level following the status code gives. Nothing
    else records this: a swap's eviction meets the same 503 through the brain's own port, which
    turns it into a user-facing note without logging its text, so a line at the level a missing
    model id gets would be the only trace of a card nobody can load anything onto.
    """
    client, supervisor, _ = _wired(FakeChildProcesses(exits_on=None))
    try:
        await supervisor.start(CORTEX)
        with caplog.at_level(logging.WARNING):
            response = await client.post(f"/models/{CORTEX}/stop")
    finally:
        await client.aclose()
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert "survived SIGKILL" in _body(response)["error"]
    assert [(record.levelno, record.message) for record in caplog.records] == [
        (logging.WARNING, "a model process ignored SIGTERM; killing it"),
        (logging.ERROR, "a model-host request failed"),
    ]
    # The whole sentence rides the field, so printing it a second time adds nothing: dropping
    # that second line loses no part of the failure.
    assert "survived SIGKILL" in str(record_fields(caplog.records[1])["error"])


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
    # Read off the rendered line rather than `caplog.text`, which carries no field: the tier rides
    # this record as one, and the traceback the formatter appends stays below the fields.
    (record,) = caplog.records
    assert (
        PlainFormatter()
        .format(record)
        .startswith(
            "ERROR:cortex_model_manager.api:"
            "the boot-default model could not be started; serving without it model=ghost\n"
        )
    )
