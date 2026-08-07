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

Two for the seam's residency reporter, measured the same way. Dropping ``residency=`` from the
``SeamPorts`` the composition root serves with reddens 2, both cases here that probe ``Health``
through the wiring, which is why the first of them holds the manager the root really built rather
than one of its own. Dropping the root's ``publish_boot_residency`` call reddens exactly 1,
``test_a_boot_that_could_not_settle_the_cortex_leaves_the_seam_saying_so``, and so does passing
it a constant ``serving=True``: that argument is the knob turning boot recovery's own observation
into the seam's first answer, and neither half of it can be dropped silently.
"""

import asyncio
import os
import signal
import socket
from collections.abc import Callable
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
    AsyncioSleeper,
    Clock,
    InMemoryBodyGateway,
    ModelHostState,
    ScriptedModelHost,
    Sleeper,
    SubagentPlacer,
    SwappingModelManager,
    SystemClock,
)
from cortex_model_manager import HttpModelHost
from cortex_orchestrator import (
    BrainRuntimeConfig,
    InferenceConfig,
    SwapConfig,
    SwapRuntime,
    build_builtin_tools,
    build_swap_runtime,
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
) -> tuple[SwapRuntime, httpx.AsyncClient, list[str]]:
    """The real-backend runtime, with the control client's transport replaced but nothing else.

    The client is built by the production builder's own seam, so the endpoint the adapter dials
    is whatever ``CORTEX_MODELHOST_ENDPOINT`` said, and the test holds the very object the
    runtime's closer must release.
    """
    asked: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
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
    """The generation clients pass ``read=None`` on purpose; a control call may not hang at all.

    A wedged sidecar would otherwise hold a swap step forever, which is the one wait in the
    sequence no plan bound covers: the drain and the load are bounded by the plan, a control call
    is bounded only by its client.
    """
    client = swap_builders.build_control_client(31.5)
    try:
        # Whole-value equality, which pins the read deadline along with the other three phases:
        # `read=None` (what builders.py passes on purpose) cannot satisfy it.
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
    real = build_swap_runtime

    def stuck(  # noqa: PLR0913 -- mirrors the builder it stands in for
        swap: SwapConfig,
        runtime: BrainRuntimeConfig,
        inference: InferenceConfig,
        clock: Clock,
        sleeper: Sleeper,
        handoff_store_factory: Callable[[str], RedisHandoffStore] = RedisHandoffStore.from_url,
        placer: SubagentPlacer | None = None,
    ) -> SwapRuntime | None:
        made = real(swap, runtime, inference, clock, sleeper, handoff_store_factory, placer)
        assert made is not None  # escalation is on in this test's env
        never_ready = ScriptedModelHost(
            status_override={made.plan.cortex_model: ModelHostState.LOADING}
        )
        return replace(made, host=never_ready, plan=replace(made.plan, load_timeout_s=0.0))

    monkeypatch.setattr(wiring, "build_swap_runtime", stuck)
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
