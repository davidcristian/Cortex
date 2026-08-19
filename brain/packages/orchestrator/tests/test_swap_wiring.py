"""The handoff's composition root: the env gate in both directions, and what it builds.

The gate is the whole safety story of this capability, so it is tested from both sides: with
``CORTEX_ESCALATION`` off (the default) nothing is built and the escalate tool is not even
advertised; with it on, the model host, the swapping manager, the handoff store, and the
escalating engine factory all exist, and the deployment must have said where the deep model
answers or boot fails loudly.

Distrust-green proofs (each mutation reddened the named test, then was restored):
- registering ``escalate_to_brain`` unconditionally reddens
  ``test_the_escalate_tool_is_not_advertised_unless_a_handoff_can_run``;
- dropping the escalation branch in ``build_swap_runtime`` (always building the runtime)
  reddens ``test_nothing_is_built_when_escalation_is_off``;
- dropping the config validator reddens ``test_escalation_without_a_model_host_fails_at_boot``.

Five more for the real backend, each applied to production code alone with the whole ``packages``
suite re-run, so the counts below are what actually reddened rather than what was aimed at. None
of them reaches outside this file, the backend name being read in exactly one place:

- building the scripted host whatever the backend names reddens 3, every case here that goes
  through ``_supervisor_runtime``;
- closing only the handoff store (dropping the model host's client from the closer) reddens the
  same 3, since two of them read ``client.is_closed`` and the third cannot get there;
- closing only the model host's client reddens 2, ``test_closing_the_runtime_...`` and
  ``test_a_store_that_will_not_close_...``, which is why both read the store's own release rather
  than only the new one;
- releasing the client outside the closer's ``finally`` (so a store that raises skips it) reddens
  exactly 1, ``test_a_store_that_will_not_close_still_releases_the_control_client``;
- dropping the endpoint clause from the config validator reddens exactly 1,
  ``test_the_real_backend_without_its_endpoint_fails_at_boot``.

Four for the deadline pairing, measured the same way. Dropping the refusal (logging the mismatch
and serving anyway) reddens 3, ``test_a_deadline_the_hosts_worst_stop_can_outlast_...``,
``test_a_refused_pairing_releases_what_the_runtime_already_holds`` and
``test_run_from_env_refuses_a_deployment_whose_pairing_does_not_hold``; making the bounds'
``clears`` answer ``True`` whatever the numbers reddens those 3 plus the boundary case in the
core's own ``test_model_host.py``, which is what separates the arithmetic from the policy over it;
refusing an unreachable host as well reddens exactly 1,
``test_a_host_that_cannot_be_asked_leaves_the_pairing_unchecked``, so the tolerance is pinned as
deliberately as the refusal; and dropping the call from the composition root reddens exactly 1, the
``run_from_env`` case, which is the only reason that case exists beside the three that drive the
check directly. That case is bounded by ``asyncio.wait_for`` because a root that never refuses goes
on to ``serve``: without the bound the mutation hung the suite instead of reddening, which is not a
proof of anything.

Two for the seam's residency reporter, measured the same way. Dropping ``residency=`` from the
``SeamPorts`` the composition root serves with reddens 2, both cases here that probe ``Health``
through the wiring, which is why the first of them holds the manager the root really built rather
than one of its own. Dropping the root's ``publish_boot_residency`` call reddens exactly 1,
``test_a_boot_that_could_not_settle_the_cortex_leaves_the_seam_saying_so``, and so does passing
it a constant ``serving=True``: that argument is the knob turning boot recovery's own observation
into the seam's first answer, and neither half of it can be dropped silently.

One more for the loop that keeps reading after that first answer. Dropping the regain from the
background pass (``residency_regain.heal_standing_residency``) reddens 12 across the workspace, and
exactly one of them is here:
``test_a_cortex_that_comes_up_after_the_boot_verdict_turns_the_seam_green`` is the only case
anywhere that drives ``TierHealer``'s own loop over the real composition root, so it is what would
catch a healer wired to a pass that no longer regains anything. It is bounded by
``asyncio.timeout`` for the reason the pairing case above is: without the bound the mutation hangs
the suite rather than reddening, which proves nothing.

One more beside them, for the record that observation is now written into. Handing boot recovery a
fresh ``StandingTiers`` instead of the manager's own (two records for one fact, which is what any
version of this that did not reach through the manager would have) reddens exactly 1,
``test_a_boot_whose_peer_tier_is_down_still_says_the_brain_is_ready``, on both of its last two
lines: the seam would say nothing about the tier and the pool would go on offering the GPU.
"""

import asyncio
import logging
import os
import signal
import socket
from collections.abc import Callable, Iterable
from dataclasses import replace
from http import HTTPStatus
from typing import cast

import httpx
import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from grpc import aio
from redis.asyncio import Redis

from cortex_core import (
    ESCALATE_TOOL_NAME,
    RESIDENCY_BOOT_FAILED,
    RESIDENCY_DEEP,
    TIERS_MISSING_DETAIL,
    AsyncioSleeper,
    Clock,
    ControlBounds,
    InMemoryBodyGateway,
    ModelHostState,
    PlacementRequest,
    PlacementTarget,
    PlainFormatter,
    ScriptedModelHost,
    Sleeper,
    SubagentPlacer,
    SwappingModelManager,
    SystemClock,
    VramBudgetPlacer,
)
from cortex_model_manager import HttpModelHost, ModelHostConfig
from cortex_orchestrator import (
    BrainRuntimeConfig,
    ControlDeadlineError,
    InferenceConfig,
    SwapConfig,
    SwapRuntime,
    build_builtin_tools,
    build_swap_runtime,
    check_control_deadline,
    recover_boot_residency,
    run_from_env,
    swap_builders,
    swap_closer,
    wiring,
)
from cortex_seam import (
    BrainServiceStub,
    ClientEvent,
    HealthReply,
    HealthRequest,
    ServerEvent,
    UserTurn,
)
from cortex_session import RedisHandoffStore, RedisSessionStore


def _stuck_host(*, running: Iterable[str]) -> ScriptedModelHost:
    """The composition root's own scripted host, with every tier it seeds stuck ``LOADING``.

    Substituted for the class the builder calls rather than for the runtime it returns, so the
    manager, boot recovery and the healer all read one machine, as they do in a deployment.
    ``set_status(model, None)`` on it is the operator starting that tier by hand.
    """
    seeded = list(running)
    return ScriptedModelHost(
        running=seeded, status_override=dict.fromkeys(seeded, ModelHostState.LOADING)
    )


def _free_loopback_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


def _enabled(**overrides: object) -> SwapConfig:
    fields: dict[str, object] = {
        "escalation": True,
        "modelhost_backend": "scripted",
        "brain_endpoint": "http://llama-brain:8081",
    }
    return SwapConfig(**(fields | overrides))  # pyright: ignore[reportArgumentType]


def _fake_handoff_store(url: str) -> RedisHandoffStore:
    del url
    return RedisHandoffStore(FakeAsyncRedis(server=FakeServer()))


class _RecordingHandoffStore(RedisHandoffStore):
    """A handoff store that says when it was released, and can refuse to be released at all."""

    def __init__(self, released: list[str], *, refuse: bool = False) -> None:
        super().__init__(FakeAsyncRedis(server=FakeServer()))
        self._released = released
        self._refuse = refuse

    async def aclose(self) -> None:
        self._released.append("handoff store")
        await super().aclose()
        if self._refuse:
            msg = "the store's connection could not be released"
            raise OSError(msg)


def _supervisor_runtime(
    monkeypatch: pytest.MonkeyPatch,
    released: list[str],
    *,
    refuse_store_close: bool = False,
    bounds: ControlBounds | None = None,
) -> tuple[SwapRuntime, httpx.AsyncClient, list[str]]:
    """The real-backend runtime, with the control client's transport replaced but nothing else.

    The client is built by the production builder's own seam, so the endpoint the adapter dials
    is whatever ``CORTEX_MODELHOST_ENDPOINT`` said, and the test holds the very object the
    runtime's closer must release. ``bounds`` is what this sidecar claims its own control calls
    can spend; without it ``/health`` carries none, which is a daemon older than that field.
    """
    asked: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        if request.url.path == "/health" and bounds is not None:
            return httpx.Response(
                HTTPStatus.OK,
                json={
                    "status": "ok",
                    "probe_timeout_s": bounds.probe_timeout_s,
                    "stop_grace_s": bounds.stop_grace_s,
                    "reap_timeout_s": bounds.reap_timeout_s,
                },
            )
        return httpx.Response(HTTPStatus.OK, json={"state": "ready", "detail": ""})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))

    def mock_client(timeout_s: float) -> httpx.AsyncClient:
        del timeout_s
        return client

    monkeypatch.setattr(swap_builders, "build_control_client", mock_client)
    runtime = build_swap_runtime(
        _enabled(modelhost_backend="supervisor", modelhost_endpoint="http://model-host:9300"),
        BrainRuntimeConfig(),
        InferenceConfig(),
        SystemClock(),
        AsyncioSleeper(),
        lambda _url: _RecordingHandoffStore(released, refuse=refuse_store_close),
    )
    assert runtime is not None
    return runtime, client, asked


def test_escalation_is_off_by_default() -> None:
    """CI and the GPU-less dev loop are byte for byte what they were before this landed."""
    config = SwapConfig()
    assert config.escalation is False
    assert config.modelhost_backend == "none"
    assert config.brain_model == "brain"


def test_escalation_without_a_model_host_fails_at_boot() -> None:
    """Nothing could evict or load a model, so the tool could only ever refuse: say so loudly."""
    with pytest.raises(ValueError, match="CORTEX_MODELHOST_BACKEND must name a model host"):
        SwapConfig(escalation=True)


def test_escalation_without_a_brain_endpoint_fails_at_boot() -> None:
    with pytest.raises(ValueError, match="CORTEX_BRAIN_ENDPOINT is required"):
        SwapConfig(escalation=True, modelhost_backend="scripted")


def test_the_real_backend_without_its_endpoint_fails_at_boot() -> None:
    """Every swap step would fail at its first call, so the deployment is refused instead."""
    with pytest.raises(ValueError, match="CORTEX_MODELHOST_ENDPOINT is required"):
        _enabled(modelhost_backend="supervisor")


def test_the_residency_plan_carries_the_tier_ids_and_both_bounds() -> None:
    """One plan value, so the manager, the conductor, and recovery cannot disagree."""
    plan = _enabled(
        evict_models=("subagent-gpu",), swap_drain_timeout_s=5.0, swap_load_timeout_s=7.0
    ).residency_plan("cortex")
    assert (plan.cortex_model, plan.brain_model) == ("cortex", "brain")
    assert plan.evict_models == ("subagent-gpu",)
    assert (plan.drain_timeout_s, plan.load_timeout_s) == (5.0, 7.0)
    # Brain-runs-alone unless the deployment says its peers fit beside the deep model.
    assert plan.coresident is False
    assert _enabled(coresident=True).residency_plan("cortex").coresident is True
    # And no fit is checked unless the deployment measured one, which is the shipped default.
    assert plan.brain_vram_mib == 0
    assert _enabled(brain_vram_mib=19125).residency_plan("cortex").brain_vram_mib == 19125
    # Nor is a handoff judged by a decode rate the deployment never measured on its own card.
    assert plan.brain_decode_tps == 0.0
    assert _enabled(brain_decode_tps=22.0).residency_plan("cortex").brain_decode_tps == 22.0
    # And the control deadline rides the plan rather than travelling beside it, so the boot check
    # and a swap re-reading the same rule after a sidecar restart cannot compare different numbers.
    assert plan.control_deadline_s == SwapConfig().modelhost_timeout_s
    assert _enabled(modelhost_timeout_s=90.0).residency_plan("cortex").control_deadline_s == 90.0


def test_co_residency_on_the_real_host_without_a_measured_fit_fails_at_boot() -> None:
    """The flag is a claim about a card, and this is the only thing that ever tests it.

    Boot rather than the swap, because a deployment that never stated the figure is misconfigured
    from the moment it starts, and a handoff is the worst place to learn it: the cortex is already
    stopped by then. What is deliberately NOT checked here is the card itself, which changes by
    the gigabyte while the machine runs and is read at the swap instead.
    """
    with pytest.raises(ValueError, match="CORTEX_SWAP_BRAIN_VRAM_MIB is required"):
        _enabled(
            modelhost_backend="supervisor",
            modelhost_endpoint="http://model-host:9300",
            coresident=True,
        )


def test_co_residency_over_the_scripted_host_needs_no_measurement() -> None:
    """That backend starts no process on any card, so a figure would assert nothing.

    It is what CI and the dev loop run the whole handoff path over, and requiring a VRAM number
    from a host that has no VRAM would be a gate that cannot fail for the deployment it is aimed
    at while blocking the one it is not.
    """
    plan = _enabled(coresident=True).residency_plan("cortex")
    assert (plan.coresident, plan.brain_vram_mib) == (True, 0)
    # The decode floor is not required by co-residency at all, on any host: it guards no
    # decision, so an unmeasured deployment is better served by the number in its log.
    assert plan.brain_decode_tps == 0.0


def test_nothing_is_built_when_escalation_is_off() -> None:
    runtime = build_swap_runtime(
        SwapConfig(),
        BrainRuntimeConfig(),
        InferenceConfig(),
        SystemClock(),
        AsyncioSleeper(),
        _fake_handoff_store,
    )
    assert runtime is None


async def test_the_enabled_runtime_is_the_one_lease_and_the_one_residency() -> None:
    """The same object must be both, or a swap could preempt a live inference round."""
    runtime = build_swap_runtime(
        _enabled(),
        BrainRuntimeConfig(),
        InferenceConfig(backend="llamacpp", endpoint="http://llama-cortex:8080"),
        SystemClock(),
        AsyncioSleeper(),
        _fake_handoff_store,
    )
    assert runtime is not None
    assert isinstance(runtime.manager, SwappingModelManager)
    assert isinstance(runtime.host, ScriptedModelHost)
    assert runtime.host.running == {"cortex"}  # the host boots with the cortex resident
    async with runtime.manager.acquire("cortex") as lease:
        assert lease.endpoint == "http://llama-cortex:8080"
    async with runtime.manager.swap_scope("brain"), runtime.manager.acquire("brain") as lease:
        assert lease.endpoint == "http://llama-brain:8081"
    await swap_closer(runtime)()


async def test_a_boot_whose_peer_tier_is_down_still_says_the_brain_is_ready() -> None:
    """A delegation tier that will not start is not the usual assistant failing to come up.

    Boot recovery converges a machine nobody has escalated on yet, which is why this is the least
    excusable place for that conflation: the report used to go amber with "did not come up at
    startup" over a cortex serving turns perfectly well. What the boot really learned goes into
    the manager's own peer record instead, so the seam stays green and names the tier, and the
    placer the pool spawns against is closed before a single delegated run pays a dead attempt.

    The retry loop is stopped before the assertions rather than after: its first pass would ask
    the manager's own host, which is the working one this test never replaced, and would clear the
    mark. Stopping it before it is ever scheduled is what keeps this case about the boot.
    """
    placer = VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0)
    runtime = build_swap_runtime(
        _enabled(evict_models=("subagent-gpu",)),
        BrainRuntimeConfig(),
        InferenceConfig(),
        SystemClock(),
        AsyncioSleeper(),
        _fake_handoff_store,
        placer,
    )
    assert runtime is not None
    broken = ScriptedModelHost(
        running=["cortex"], fail={("start", "subagent-gpu"): "no such device"}
    )
    try:
        await recover_boot_residency(replace(runtime, host=broken), SystemClock())
        await runtime.healer.aclose()
        report = runtime.manager.residency()
        assert report.serving is True
        assert report.detail == TIERS_MISSING_DETAIL.format(models="subagent-gpu")
        spawn = PlacementRequest("subagent", vram_gb=2.0, cpus=1.0, memory_gb=1.0)
        assert placer.place(spawn).target is PlacementTarget.CPU
    finally:
        await swap_closer(runtime)()


async def test_the_supervisor_backend_builds_the_real_adapter_at_the_configured_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one place ``CORTEX_MODELHOST_ENDPOINT`` reaches the adapter, asserted as the URL sent.

    The scripted host answers every ``status`` from its own bookkeeping and would send nothing,
    so the request itself is the witness that the real adapter was built and pointed somewhere.
    """
    runtime, client, asked = _supervisor_runtime(monkeypatch, [])
    try:
        assert isinstance(runtime.host, HttpModelHost)
        assert await runtime.host.status("cortex") is ModelHostState.READY
    finally:
        await swap_closer(runtime)()
    assert asked == ["http://model-host:9300/models/cortex"]
    assert client.is_closed


async def test_the_control_client_has_a_read_deadline_unlike_the_generation_clients() -> None:
    """The generation clients bound a silent gap; a control call is bounded end to end.

    A wedged sidecar would otherwise hold a swap step forever, which is the one wait in the
    sequence no plan bound covers: the drain and the load are bounded by the plan, a control call
    is bounded only by its client.
    """
    client = swap_builders.build_control_client(31.5)
    try:
        # Whole-value equality, which pins the read deadline along with the other three phases:
        # the generation clients' looser, per-read ceiling cannot satisfy it.
        assert client.timeout == httpx.Timeout(31.5)
    finally:
        await client.aclose()


async def test_closing_the_runtime_releases_the_control_client_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real host holds an HTTP client, so the shutdown hook has two things to release now."""
    released: list[str] = []
    runtime, client, _ = _supervisor_runtime(monkeypatch, released)
    assert not client.is_closed
    await swap_closer(runtime)()
    assert released == ["handoff store"]
    assert client.is_closed


async def test_a_store_that_will_not_close_still_releases_the_control_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refused store release must not leak the control client: shutdown gets one pass, not two."""
    released: list[str] = []
    runtime, client, _ = _supervisor_runtime(monkeypatch, released, refuse_store_close=True)
    with pytest.raises(OSError, match="could not be released"):
        await swap_closer(runtime)()
    assert released == ["handoff store"]
    assert client.is_closed


async def test_the_closer_is_a_clean_no_op_when_nothing_was_built() -> None:
    await swap_closer(None)()


def _with_bounds(bounds: ControlBounds | None) -> SwapRuntime:
    """The scripted runtime, holding a host that claims ``bounds`` for its own control calls."""
    runtime = build_swap_runtime(
        _enabled(),
        BrainRuntimeConfig(),
        InferenceConfig(),
        SystemClock(),
        AsyncioSleeper(),
        _fake_handoff_store,
    )
    assert runtime is not None
    return replace(runtime, host=ScriptedModelHost(running=["cortex"], control_bounds=bounds))


def _only(caplog: pytest.LogCaptureFixture) -> logging.LogRecord:
    """The single record the check emitted, so the shipped formatter can be run over it."""
    (record,) = caplog.records
    return record


async def test_the_shipped_bounds_and_the_shipped_deadline_still_clear_each_other() -> None:
    """The two containers' defaults, compared as the running pair rather than as prose.

    The sidecar's three bounds and the brain's control deadline are declared in different
    packages and set by different env, and their pairing is the reason either number is what it
    is. This is the one place both are read at once, so a default moved on one side alone stops
    being a comment somebody has to re-add up.
    """
    daemon = ModelHostConfig()
    shipped = ControlBounds(
        probe_timeout_s=daemon.probe_timeout_s,
        stop_grace_s=daemon.stop_grace_s,
        reap_timeout_s=daemon.reap_timeout_s,
    )
    assert shipped.worst_case_stop_s == 45.0
    assert shipped.clears(SwapConfig().modelhost_timeout_s) is True


async def test_a_deadline_the_hosts_worst_stop_can_outlast_refuses_to_boot(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The pairing spans two containers' env, so this is the only place it can be checked.

    Refused rather than logged, because the failure it prevents is intermittent: a stop pays the
    whole SIGTERM grace only when the tier it evicts was answering, so a mispaired stack works
    all the way up to the handoff that matters and then aborts an eviction that was succeeding.
    """
    runtime = _with_bounds(
        ControlBounds(probe_timeout_s=5.0, stop_grace_s=20.0, reap_timeout_s=35.0)
    )
    with caplog.at_level(logging.ERROR), pytest.raises(ControlDeadlineError) as excinfo:
        await check_control_deadline(runtime)
    # Every term, so the operator can see which knob to move without reading two containers' env.
    assert "worst stop is 60.0 s (probe 5.0 s, grace 20.0 s, reap 35.0 s)" in str(excinfo.value)
    assert "CORTEX_MODELHOST_TIMEOUT_S is 60.0 s" in caplog.text


async def test_a_refused_pairing_releases_what_the_runtime_already_holds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole path over the real adapter, and the shutdown hook is not armed yet when it fails.

    The bounds come off a real ``GET /health`` here rather than off a twin, so this is also what
    pins the adapter's reading to the composition root's comparison.
    """
    released: list[str] = []
    runtime, client, asked = _supervisor_runtime(
        monkeypatch,
        released,
        bounds=ControlBounds(probe_timeout_s=5.0, stop_grace_s=20.0, reap_timeout_s=35.0),
    )
    with pytest.raises(ControlDeadlineError):
        await check_control_deadline(runtime)
    assert asked == ["http://model-host:9300/health"]
    assert released == ["handoff store"]
    assert client.is_closed


async def test_a_deadline_that_clears_the_worst_stop_is_wired_and_says_so(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The shipped pair, which must pass: a check that refused this would refuse every stack."""
    runtime = _with_bounds(
        ControlBounds(probe_timeout_s=5.0, stop_grace_s=10.0, reap_timeout_s=30.0)
    )
    with caplog.at_level(logging.INFO):
        await check_control_deadline(runtime)
    assert "clears the model host's worst stop" in caplog.text
    # The two numbers ride the record rather than the message, so the pair an operator greps for
    # is read off the line the shipped formatter renders. ``caplog.text`` carries the message
    # alone, and asserting the pair against it would pass only while the values were printed twice.
    assert "deadline_s=60.0 worst_s=45.0" in PlainFormatter().format(_only(caplog))
    await swap_closer(runtime)()


async def test_a_host_that_bounds_no_stop_of_its_own_is_not_a_refusal(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The scripted backend CI and the dev loop run: it stops no process, so it bounds nothing."""
    runtime = _with_bounds(None)
    with caplog.at_level(logging.INFO):
        await check_control_deadline(runtime)
    assert "reports no control bounds" in caplog.text
    await swap_closer(runtime)()


async def test_a_host_that_cannot_be_asked_leaves_the_pairing_unchecked(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A sidecar that is down is not a misconfiguration, and boot recovery already says so.

    Its restart policy revives a daemon whose own boot default is the cortex, so the brain must
    come up beside one that is not answering yet. The mispairing this check exists for cannot
    heal itself that way, which is why only the answered case refuses.
    """
    runtime = build_swap_runtime(
        _enabled(),
        BrainRuntimeConfig(),
        InferenceConfig(),
        SystemClock(),
        AsyncioSleeper(),
        _fake_handoff_store,
    )
    assert runtime is not None
    unreachable = ScriptedModelHost(fail={("control_bounds", ""): "connection refused"})
    with caplog.at_level(logging.WARNING):
        await check_control_deadline(replace(runtime, host=unreachable))
    assert "could not be asked for its control bounds" in caplog.text
    await swap_closer(runtime)()


async def test_the_pairing_check_is_a_clean_no_op_when_nothing_was_built() -> None:
    """Escalation off builds no host, so there is no deadline anything could spend."""
    await check_control_deadline(None)


async def test_the_escalate_tool_is_not_advertised_unless_a_handoff_can_run() -> None:
    """Advertising it without the wrapper would offer a tool that could only refuse."""
    without = build_builtin_tools(None, InMemoryBodyGateway())
    assert [tool.spec.name for tool in without if tool.spec.name == ESCALATE_TOOL_NAME] == []
    with_handoff = build_builtin_tools(None, InMemoryBodyGateway(), escalation=True)
    assert ESCALATE_TOOL_NAME in [tool.spec.name for tool in with_handoff]


async def test_run_from_env_serves_with_the_handoff_wired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole capability from env: recovery runs, turns serve, and shutdown stays clean."""
    port = _free_loopback_port()
    monkeypatch.setenv("CORTEX_SEAM_HOST", "127.0.0.1")
    monkeypatch.setenv("CORTEX_SEAM_PORT", str(port))
    monkeypatch.setenv("CORTEX_ESCALATION", "1")
    monkeypatch.setenv("CORTEX_MODELHOST_BACKEND", "scripted")
    monkeypatch.setenv("CORTEX_BRAIN_ENDPOINT", "http://llama-brain:8081")
    server = FakeServer()

    def fake_from_url(url: str) -> Redis:
        del url
        return FakeAsyncRedis(server=server)

    monkeypatch.setattr(Redis, "from_url", fake_from_url)
    task = asyncio.create_task(run_from_env(store_factory=lambda _url: _session_store(server)))
    try:
        events = await _run_one_turn(f"127.0.0.1:{port}")
        # The escalating wrapper is transparent for a turn that never asks to escalate: the
        # echo backend's reply arrives exactly as it does without the handoff wired.
        assert (
            "".join(
                event.text_delta.text
                for event in events
                if event.WhichOneof("event") == "text_delta"
            )
            == "reply 1: hello"
        )
        assert any(event.WhichOneof("event") == "turn_complete" for event in events)
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()


async def test_run_from_env_refuses_a_deployment_whose_pairing_does_not_hold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The root asks before it builds anything else, so a mispaired stack never serves a turn.

    Driven through ``run_from_env`` rather than the check alone, because the check being right is
    worth nothing if the composition root never calls it. The sidecar here answers the two-term
    tuning the runbook warns about, a grace and a reap summing to a compliant-looking 55 that the
    queued probe carries to the deadline exactly.
    """
    monkeypatch.setenv("CORTEX_ESCALATION", "1")
    monkeypatch.setenv("CORTEX_MODELHOST_BACKEND", "supervisor")
    monkeypatch.setenv("CORTEX_MODELHOST_ENDPOINT", "http://model-host:9300")
    monkeypatch.setenv("CORTEX_BRAIN_ENDPOINT", "http://llama-brain:8081")
    server = FakeServer()

    def fake_from_url(url: str) -> Redis:
        del url
        return FakeAsyncRedis(server=server)

    def handle(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            HTTPStatus.OK,
            json={
                "status": "ok",
                "probe_timeout_s": 5.0,
                "stop_grace_s": 20.0,
                "reap_timeout_s": 35.0,
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))

    def mock_client(timeout_s: float) -> httpx.AsyncClient:
        del timeout_s
        return client

    monkeypatch.setattr(Redis, "from_url", fake_from_url)
    monkeypatch.setattr(swap_builders, "build_control_client", mock_client)
    # Bounded, because the failure this pins is a root that never asks: without the refusal the
    # root goes on to ``serve``, which returns for nothing this test can arrange.
    with pytest.raises(ControlDeadlineError, match=r"CORTEX_MODELHOST_TIMEOUT_S is 60\.0 s"):
        await asyncio.wait_for(
            run_from_env(store_factory=lambda _url: _session_store(server)), timeout=10
        )
    assert client.is_closed


async def test_health_tells_the_truth_about_residency_through_the_whole_wiring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reporter reaches the servicer: with the wired manager mid handoff, Health says so.

    The manager under test is the one the composition root built, captured on its way out of the
    builder rather than constructed beside it, so this is what pins the plumbing: dropping
    ``residency=`` from the ``serve`` call leaves the seam answering ready through a handoff.
    """
    port = _free_loopback_port()
    monkeypatch.setenv("CORTEX_SEAM_HOST", "127.0.0.1")
    monkeypatch.setenv("CORTEX_SEAM_PORT", str(port))
    monkeypatch.setenv("CORTEX_ESCALATION", "1")
    monkeypatch.setenv("CORTEX_MODELHOST_BACKEND", "scripted")
    monkeypatch.setenv("CORTEX_BRAIN_ENDPOINT", "http://llama-brain:8081")
    server = FakeServer()

    def fake_from_url(url: str) -> Redis:
        del url
        return FakeAsyncRedis(server=server)

    monkeypatch.setattr(Redis, "from_url", fake_from_url)
    built: list[SwapRuntime] = []
    real = build_swap_runtime

    def recording(  # noqa: PLR0913 -- mirrors the builder it stands in for
        swap: SwapConfig,
        runtime: BrainRuntimeConfig,
        inference: InferenceConfig,
        clock: Clock,
        sleeper: Sleeper,
        handoff_store_factory: Callable[[str], RedisHandoffStore] = RedisHandoffStore.from_url,
        placer: SubagentPlacer | None = None,
    ) -> SwapRuntime | None:
        # The placer is forwarded rather than dropped: the root hands the pool's own object here
        # so the residency scope can recharge it during a handoff, and a double that swallowed it
        # would hide a root that stopped passing it.
        made = real(swap, runtime, inference, clock, sleeper, handoff_store_factory, placer)
        assert made is not None  # escalation is on in this test's env
        built.append(made)
        return made

    monkeypatch.setattr(wiring, "build_swap_runtime", recording)
    task = asyncio.create_task(run_from_env(store_factory=lambda _url: _session_store(server)))
    try:
        async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            await asyncio.wait_for(channel.channel_ready(), timeout=10)
            stub = BrainServiceStub(channel)
            assert (await _health(stub)).ready is True
            swap = built[0]
            async with swap.manager.swap_scope(swap.plan.brain_model):
                mid_handoff = await asyncio.wait_for(_health(stub), timeout=5.0)
            assert mid_handoff.ready is False
            assert mid_handoff.detail == RESIDENCY_DEEP.detail
            assert (await _health(stub)).ready is True  # the swap back turns the dot green again
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()


async def test_a_boot_that_could_not_settle_the_cortex_leaves_the_seam_saying_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Boot recovery's own observation reaches the report, or the first probe is a lie.

    A manager seeds its report optimistically, because a constructor cannot know what is on the
    GPU. Recovery is what looks, and it is allowed to fail without raising, so a brain whose
    cortex never came up used to log the failure loudly and then answer ``ready=true`` from the
    same boot. The model host here reports the cortex stuck ``LOADING`` past a zero bound, which
    is the shape of the case the runbook's manual recovery exists for.

    One host for the whole runtime, deliberately, because a second one would make this case
    unfalsifiable: the background pass reads the same machine boot recovery read, so a stuck
    cortex has to stay stuck for the residency regain as well (ADR-0030 residency-regain
    addendum). The case below is the other side of that same wiring.
    """
    port = _free_loopback_port()
    monkeypatch.setenv("CORTEX_SEAM_HOST", "127.0.0.1")
    monkeypatch.setenv("CORTEX_SEAM_PORT", str(port))
    monkeypatch.setenv("CORTEX_ESCALATION", "1")
    monkeypatch.setenv("CORTEX_MODELHOST_BACKEND", "scripted")
    monkeypatch.setenv("CORTEX_BRAIN_ENDPOINT", "http://llama-brain:8081")
    monkeypatch.setenv("CORTEX_SWAP_LOAD_TIMEOUT_S", "0")
    server = FakeServer()

    def fake_from_url(url: str) -> Redis:
        del url
        return FakeAsyncRedis(server=server)

    monkeypatch.setattr(Redis, "from_url", fake_from_url)
    monkeypatch.setattr(swap_builders, "ScriptedModelHost", _stuck_host)
    task = asyncio.create_task(run_from_env(store_factory=lambda _url: _session_store(server)))
    try:
        async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            await asyncio.wait_for(channel.channel_ready(), timeout=10)
            reply = await asyncio.wait_for(_health(BrainServiceStub(channel)), timeout=5.0)
        assert reply.ready is False
        assert reply.detail == RESIDENCY_BOOT_FAILED.detail
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()


async def test_a_cortex_that_comes_up_after_the_boot_verdict_turns_the_seam_green(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The recovery that used to need a restart of the brain, driven through the whole wiring.

    Boot recovery could not settle the cortex, so the seam is honest and amber; the operator then
    starts that tier through the model host's own control API, which is step 2 of the runbook's
    manual recovery and needs no restart of anything. What used to follow was step 3, restarting
    the brain, because nothing else re-read the machine. The healer's pass is what re-reads it
    now, so the dot goes green on its own and the next turn runs.
    """
    port = _free_loopback_port()
    monkeypatch.setenv("CORTEX_SEAM_HOST", "127.0.0.1")
    monkeypatch.setenv("CORTEX_SEAM_PORT", str(port))
    monkeypatch.setenv("CORTEX_ESCALATION", "1")
    monkeypatch.setenv("CORTEX_MODELHOST_BACKEND", "scripted")
    monkeypatch.setenv("CORTEX_BRAIN_ENDPOINT", "http://llama-brain:8081")
    monkeypatch.setenv("CORTEX_SWAP_LOAD_TIMEOUT_S", "0")
    monkeypatch.setenv("CORTEX_SWAP_TIER_HEAL_S", "0.01")
    server = FakeServer()

    def fake_from_url(url: str) -> Redis:
        del url
        return FakeAsyncRedis(server=server)

    hosts: list[ScriptedModelHost] = []

    def remembered(*, running: Iterable[str]) -> ScriptedModelHost:
        hosts.append(_stuck_host(running=running))
        return hosts[-1]

    monkeypatch.setattr(Redis, "from_url", fake_from_url)
    monkeypatch.setattr(swap_builders, "ScriptedModelHost", remembered)
    task = asyncio.create_task(run_from_env(store_factory=lambda _url: _session_store(server)))
    try:
        async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            await asyncio.wait_for(channel.channel_ready(), timeout=10)
            stub = BrainServiceStub(channel)
            assert (await asyncio.wait_for(_health(stub), timeout=5.0)).ready is False
            for model in sorted(hosts[0].running):
                hosts[0].set_status(model, None)  # POST /models/cortex/start, and it came up
            async with asyncio.timeout(10):
                # Bounded polling rather than an event, deliberately: what this waits on is the
                # healer's own loop inside the process under test, which offers nothing to await.
                while not (await _health(stub)).ready:  # noqa: ASYNC110 -- no event to wait on
                    await asyncio.sleep(0.01)
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()


async def _health(stub: BrainServiceStub) -> HealthReply:
    health = stub.Health  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast("HealthReply", await health(HealthRequest()))


def _session_store(server: FakeServer) -> RedisSessionStore:
    return RedisSessionStore(FakeAsyncRedis(server=server))


async def _run_one_turn(address: str) -> list[ServerEvent]:
    async with aio.insecure_channel(address) as channel:
        await asyncio.wait_for(channel.channel_ready(), timeout=10)
        stub = BrainServiceStub(channel)
        converse = stub.Converse  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        call = cast("aio.StreamStreamCall[ClientEvent, ServerEvent]", converse())
        await call.write(ClientEvent(session_id="wired", user_turn=UserTurn(text="hello")))
        await call.done_writing()
        return [event async for event in call]
