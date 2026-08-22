"""The composition root's vision decisions, driven through ``run_from_env`` itself (ADR-0029).

Every other vision test calls ``build_builtin_tools`` directly, which proves the builder and
nothing about the root. The decisions live in the root: whether to build a probe at all, what
the probe's answer does, which numbers reach the tool, and which tier is offered the capability.
None of that was executed by any test when this suite was written: the ternary's true arm never
ran, so ``vision=capture`` could be replaced by ``vision=None`` with the whole suite green, and
coverage stayed at 100% because coverage.py does not measure the arms of a boolean short-circuit.

What the root decides changed on 2026-08-06 (ADR-0029 live-probe addendum) and this suite moved
with it. The answer is no longer taken once and frozen into a built-in set: the root registers
the tool whenever a body can take a picture, and hands the cortex's dispatcher a
``VisionProbe`` the registry re-asks on every advertisement and every call. So the cases read
the **advertised** set out of the dispatcher the root actually built, which is the set the model
is offered, rather than the list of objects that were constructed.

Distrust-green proofs (each mutation applied to production code alone, ``packages/orchestrator``
plus ``packages/core`` re-run, 2026-08-06):
- dropping ``vision=sight`` where the root builds the cortex's dispatcher reddens exactly 2 here,
  ``test_the_probes_answer_decides_whether_the_screen_is_offered`` and
  ``test_a_capture_the_model_can_no_longer_read_reads_no_pixels``: the tool would be advertised
  and run whatever the server said, which is the shipped defect this work removes;
- returning bounds for ``off`` in ``build_vision`` reddens exactly 2,
  ``test_the_owners_off_switch_needs_no_server_to_be_believed`` and ``test_vision.py``'s
  ``test_off_registers_no_capture_tool_at_all``;
- handing the cortex's built-in set to the deep phase reddens exactly 1,
  ``test_the_deep_tier_is_never_offered_the_screen``, and so does giving the deep set
  ``vision=capture``.

The builder's own arguments are asserted for the same reason as before: a root that passed a
constant mode, or the endpoint where the mode goes, would leave a suite that only checks the
outcome green.
"""

import asyncio
import os
import signal
import socket
from collections.abc import Awaitable, Callable, Sequence
from typing import cast

import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from grpc import aio
from redis.asyncio import Redis

from cortex_body_client import GrpcBodyGateway
from cortex_core import (
    CAPTURE_SCREEN_TOOL_NAME,
    GET_VOLUME_TOOL_NAME,
    BodyGateway,
    BrainPhase,
    BuiltinTool,
    CaptureAsk,
    InMemoryBodyGateway,
    ScriptedVisionProbe,
    ToolCall,
    ToolDispatcher,
    TurnCapabilities,
)
from cortex_orchestrator import build_builtin_tools, engines, run_from_env, wiring
from cortex_orchestrator.builders import build_cortex_tools
from cortex_orchestrator.config import InferenceConfig
from cortex_orchestrator.config_body import BodyConfig
from cortex_orchestrator.vision import build_vision
from cortex_seam import BrainServiceStub, ClientEvent, ServerEvent, UserTurn
from cortex_session import RedisSessionStore


def _free_loopback_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


class _Root:
    """What one ``run_from_env`` composition decided, recorded from inside the root.

    ``builtin_sets`` is every set the root assembled, in the order it assembled them (the cortex's
    first, the deep tier's second), and ``builds`` is every ``build_vision`` call with the mode
    and endpoint the root passed it. ``dispatchers`` is every dispatcher the root built, the
    cortex's first, which is where the advertised set actually comes from now. All of it is
    written by production code; the harness only keeps it.
    """

    def __init__(self) -> None:
        self.builtin_sets: list[list[BuiltinTool]] = []
        self.builds: list[tuple[str, str]] = []
        self.dispatchers: list[ToolDispatcher] = []
        self.deep_capabilities: list[TurnCapabilities] = []
        self.scripted: ScriptedVisionProbe | None = None
        self.body = InMemoryBodyGateway()

    def names(self, which: int) -> list[str]:
        return [tool.spec.name for tool in self.builtin_sets[which]]

    async def offered(self) -> set[str]:
        """What the cortex's own dispatcher advertises, which is what the model is offered."""
        return {spec.name for spec in await self.dispatchers[0].describe_tools()}

    async def deep_tools(self) -> set[str]:
        (deep,) = self.deep_capabilities
        assert deep.tools is not None
        return {spec.name for spec in await deep.tools.describe_tools()}

    async def captures(self) -> Sequence[CaptureAsk]:
        return self.body.captures


def _record(monkeypatch: pytest.MonkeyPatch, root: _Root, vision_answers: tuple[bool, ...]) -> None:
    """Wrap the four root collaborators whose arguments and products this suite reads back.

    Each wrapper calls the real thing and keeps what it returned, so every assertion below is
    about shipped code; the only substitution is the scripted probe, and only when a test asked
    for one.
    """
    real_builtins = build_builtin_tools
    real_vision = build_vision
    real_tools = build_cortex_tools
    real_phase = BrainPhase

    def recording_builtins(*args: object, **kwargs: object) -> list[BuiltinTool]:
        built = real_builtins(*args, **kwargs)  # pyright: ignore[reportCallIssue, reportArgumentType]
        root.builtin_sets.append(built)
        return built

    def recording_vision(
        config: InferenceConfig, body_config: BodyConfig, body: object
    ) -> tuple[object, object, Callable[[], Awaitable[None]]]:
        root.builds.append((config.vision, config.endpoint))
        bounds, probe, close = real_vision(config, body_config, cast("BodyGateway | None", body))
        if vision_answers and probe is not None:
            root.scripted = ScriptedVisionProbe(vision_answers)
            probe = root.scripted
        return bounds, probe, close

    def recording_tools(*args: object, **kwargs: object) -> ToolDispatcher | None:
        built = real_tools(*args, **kwargs)  # pyright: ignore[reportCallIssue, reportArgumentType]
        if built is not None:
            root.dispatchers.append(built)
        return built

    def recording_phase(*args: object) -> object:
        # The capabilities bundle by position, not from the end: the spill watch's declared floor
        # now rides after it (ADR-0030 spill-watch addendum).
        root.deep_capabilities.append(cast("TurnCapabilities", args[4]))
        return real_phase(*args)  # pyright: ignore[reportCallIssue, reportArgumentType]

    # Two of the four are patched where the per-stream factory reads them (`engines.py`): the
    # root assembles the two built-in sets and probes for vision, and the factory is what turns
    # a set into a dispatcher and hands the deep tier's bundle to its phase.
    monkeypatch.setattr(wiring, "build_builtin_tools", recording_builtins)
    monkeypatch.setattr(wiring, "build_vision", recording_vision)
    monkeypatch.setattr(engines, "build_cortex_tools", recording_tools)
    monkeypatch.setattr(engines, "BrainPhase", recording_phase)


async def _compose(
    monkeypatch: pytest.MonkeyPatch,
    *,
    env: dict[str, str],
    vision_answers: tuple[bool, ...] = (),
) -> _Root:
    """Run the real composition root against a fake body, one turn, then shut it down.

    A turn is run rather than only waiting for composition, because the engine factory (and with
    it the deep phase) is built per stream: without a stream nothing would construct it.
    ``vision_answers`` substitutes a scripted probe for the real one when a test needs ``auto`` to
    answer without a server, one entry per question asked and the last repeating; left empty,
    whatever ``build_vision`` really returns is used, so ``off`` and a body-less deployment are
    resolved by shipped code.
    """
    root = _Root()
    port = _free_loopback_port()
    monkeypatch.setenv("CORTEX_SEAM_HOST", "127.0.0.1")
    monkeypatch.setenv("CORTEX_SEAM_PORT", str(port))
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    server = FakeServer()

    def fake_from_url(url: str) -> Redis:
        del url
        return FakeAsyncRedis(server=server)

    monkeypatch.setattr(Redis, "from_url", fake_from_url)

    async def fake_connect(
        endpoint: str,
        *,
        token: str = "",
        capture_timeout_s: float = 10.0,
        call_timeout_s: float = 5.0,
    ) -> tuple[object, Callable[[], Awaitable[None]]]:
        del endpoint, token, capture_timeout_s, call_timeout_s

        async def closer() -> None:
            return None

        return root.body, closer

    monkeypatch.setattr(GrpcBodyGateway, "connect", fake_connect)

    _record(monkeypatch, root, vision_answers)

    task = asyncio.create_task(
        run_from_env(store_factory=lambda _url: RedisSessionStore(FakeAsyncRedis(server=server)))
    )
    try:
        async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            await asyncio.wait_for(channel.channel_ready(), timeout=10)
            stub = BrainServiceStub(channel)
            converse = stub.Converse  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            call = cast("aio.StreamStreamCall[ClientEvent, ServerEvent]", converse())
            await call.write(ClientEvent(session_id="vision", user_turn=UserTurn(text="hi")))
            await call.done_writing()
            assert [event async for event in call], "the turn produced no events at all"
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()
    return root


_BODY = {"CORTEX_BODY_BACKEND": "grpc", "CORTEX_BODY_ENDPOINT": "host.docker.internal:50151"}
_ESCALATION = {
    "CORTEX_ESCALATION": "1",
    "CORTEX_MODELHOST_BACKEND": "scripted",
    "CORTEX_BRAIN_ENDPOINT": "http://llama-brain:8081",
}


async def test_the_probes_answer_decides_whether_the_screen_is_offered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Discovered, not declared: the same env, the same body, and only the probe's verdict differs.

    Read off what the cortex's dispatcher advertises rather than off the built-in list, because
    that is where the decision moved: the tool object exists under ``auto`` either way now, and a
    root that built the probe and then never handed it to the dispatcher would leave a
    built-in-list assertion green while the model was offered eyes it does not have.

    The builder's arguments are read back too, because the root passing the wrong pair (a
    constant mode, or the endpoint as the mode) would leave a suite that only checks the outcome
    green.
    """
    seeing = await _compose(
        monkeypatch,
        env={**_BODY, "CORTEX_VISION": "auto", "CORTEX_INFERENCE_ENDPOINT": "http://cortex:8080"},
        vision_answers=(True,),
    )
    assert seeing.builds == [("auto", "http://cortex:8080")]
    assert CAPTURE_SCREEN_TOOL_NAME in await seeing.offered()

    blind = await _compose(
        monkeypatch,
        env={**_BODY, "CORTEX_VISION": "auto", "CORTEX_INFERENCE_ENDPOINT": "http://cortex:8080"},
        vision_answers=(False,),
    )
    assert blind.builds == [("auto", "http://cortex:8080")]
    offered = await blind.offered()
    assert CAPTURE_SCREEN_TOOL_NAME not in offered
    assert GET_VOLUME_TOOL_NAME in offered, "the body's other tools are unaffected"


async def test_a_capture_the_model_can_no_longer_read_reads_no_pixels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reproduced failure, refused at the root: advertised honestly, then the server changed.

    Scripted True for the advertisement and False from then on, which is exactly what a model
    host recreated without its projector does to a running brain. The assertion that matters is
    on the **body**: nothing was blitted, so no notification fired and no turn was tainted for a
    picture that would have come back as an HTTP 500.
    """
    root = await _compose(
        monkeypatch,
        env={**_BODY, "CORTEX_VISION": "auto", "CORTEX_INFERENCE_ENDPOINT": "http://cortex:8080"},
        vision_answers=(True,),
    )
    assert CAPTURE_SCREEN_TOOL_NAME in await root.offered(), "honest when it was advertised"
    assert root.scripted is not None
    # The model host is recreated without its projector, under a brain that never restarts.
    root.scripted.rescript([False])

    result = await root.dispatchers[0].dispatch(
        ToolCall(id="c1", name=CAPTURE_SCREEN_TOOL_NAME, arguments={"target": "display"})
    )

    assert result.is_error is True
    assert "the screen was not read" in result.content
    assert await root.captures() == (), "the body was never asked for a picture"


async def test_the_owners_off_switch_needs_no_server_to_be_believed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``off`` is resolved by the real ``build_vision``, so no tool lands and nothing is probed."""
    root = await _compose(monkeypatch, env={**_BODY, "CORTEX_VISION": "off"})
    assert root.builds == [("off", "")]
    assert CAPTURE_SCREEN_TOOL_NAME not in root.names(0)
    assert CAPTURE_SCREEN_TOOL_NAME not in await root.offered()


async def test_without_a_body_nothing_is_built_to_probe_with(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No body, no capture, so there is no reason to ask a model server anything.

    ``CORTEX_VISION=on`` would answer True without touching the network, which is why the guard
    is asserted on the tool never being *registered* under a mode that would otherwise register
    it unconditionally.
    """
    root = await _compose(monkeypatch, env={"CORTEX_VISION": "on"})
    assert root.builds == [("on", "")]
    assert CAPTURE_SCREEN_TOOL_NAME not in root.names(0)


async def test_the_capture_bounds_the_tool_asks_for_come_from_body_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The knobs, asserted at the far end: what the body was actually asked for.

    A composition root that built the tool with its defaults instead of the configured numbers
    leaves every other test green, so the bound is measured by invoking the tool the root built
    and reading the request that reached the fake body.
    """
    root = await _compose(
        monkeypatch,
        env={
            **_BODY,
            "CORTEX_VISION": "on",
            "CORTEX_BODY_CAPTURE_MAX_EDGE": "1280",
            "CORTEX_BODY_MAX_IMAGE_BYTES": "4000000",
        },
    )
    capture = next(
        tool for tool in root.builtin_sets[0] if tool.spec.name == CAPTURE_SCREEN_TOOL_NAME
    )
    await capture.invoke(
        ToolCall(id="c1", name=CAPTURE_SCREEN_TOOL_NAME, arguments={"target": "display"})
    )
    assert [(ask.max_edge, ask.max_bytes) for ask in await root.captures()] == [(1280, 4_000_000)]


async def test_the_deep_tier_is_never_offered_the_screen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The tier that swaps in is text-only by construction, so it must not be offered eyes.

    The probe asked the cortex's endpoint and the deep model serves at another one, so a set
    registered from that answer would advertise `capture_screen` to a model with no projector:
    the full privacy cost of a screen read (pixels blitted, receipt fired, turn tainted and
    opaque) for a picture nothing can read. Read off the capabilities the root handed the real
    ``BrainPhase``, not off the sets it built, because building the right set and passing the
    wrong one is the mistake with no other symptom.
    """
    root = await _compose(
        monkeypatch,
        env={**_BODY, **_ESCALATION, "CORTEX_VISION": "on"},
    )
    assert CAPTURE_SCREEN_TOOL_NAME in root.names(0), "the cortex keeps its eyes"
    deep = await root.deep_tools()
    assert CAPTURE_SCREEN_TOOL_NAME not in deep
    assert GET_VOLUME_TOOL_NAME in deep, "the deep tier keeps every other built-in"
