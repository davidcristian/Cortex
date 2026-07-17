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
"""

import asyncio
import os
import signal
import socket
from typing import cast

import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from grpc import aio
from redis.asyncio import Redis

from cortex_core import (
    ESCALATE_TOOL_NAME,
    AsyncioSleeper,
    InMemoryBodyGateway,
    ScriptedModelHost,
    SwappingModelManager,
    SystemClock,
)
from cortex_orchestrator import (
    BrainRuntimeConfig,
    InferenceConfig,
    SwapConfig,
    build_builtin_tools,
    build_swap_runtime,
    run_from_env,
    swap_closer,
)
from cortex_seam import BrainServiceStub, ClientEvent, ServerEvent, UserTurn
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


def test_the_residency_plan_carries_the_tier_ids_and_both_bounds() -> None:
    """One plan value, so the manager, the conductor, and recovery cannot disagree."""
    plan = _enabled(
        evict_models=("subagent-gpu",), swap_drain_timeout_s=5.0, swap_load_timeout_s=7.0
    ).residency_plan("cortex")
    assert (plan.cortex_model, plan.brain_model) == ("cortex", "brain")
    assert plan.evict_models == ("subagent-gpu",)
    assert (plan.drain_timeout_s, plan.load_timeout_s) == (5.0, 7.0)


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
