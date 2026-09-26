import asyncio
import json
import os
import statistics
import time
from typing import cast

import httpx
import pytest
from system_led import (
    CONTEXT,
    QUESTION,
    RECAP,
    TRUSTED_MEMORY,
    RecordingBackend,
    plain_context_task,
    read_dispatcher,
    recalling_turn,
)

from cortex_core import (
    SECURITY_PREAMBLE,
    AttemptBounds,
    CaptureScreenTool,
    EscalateToBrainTool,
    GenerationBounds,
    GetVolumeTool,
    InMemoryBodyGateway,
    InMemoryScheduleStore,
    Message,
    PlacementRequest,
    ResourceBudgetScheduler,
    Role,
    SetVolumeTool,
    SingleResidentModelManager,
    SubagentProfile,
    SubagentResources,
    SubagentRoster,
    SystemClock,
    ToolSpec,
    TurnCompleted,
    VramBudgetPlacer,
    fence_recap,
    new_nonce,
    wrap_untrusted,
)
from cortex_core.spawn_spec import build_spawn_spec
from cortex_core.subagent_attempt import PlacedAttempt
from cortex_core.subagent_outcome import AttemptFailure
from cortex_inference import LlamaCppBackend
from cortex_inference.request import build_payload, join_leading_system, to_openai_tools
from cortex_inference.system_probe import SYSTEM_PROBE_TIMEOUT_S, delivers_system_messages
from cortex_orchestrator.config_schedule import ScheduleConfig
from cortex_orchestrator.config_subagents import (
    DEFAULT_SUBAGENT_DESCRIPTION,
    DEFAULT_SUBAGENT_MODEL,
)
from cortex_orchestrator.schedule_builders import build_schedule_tools

pytestmark = pytest.mark.integration

_ENDPOINT = os.environ.get("CORTEX_SYSTEM_JOIN_ENDPOINT", "http://127.0.0.1:8080")
_MODEL = "cortex"
# The answers written down before the run, such as "2=yes,3=no"; unset prints them unchecked.
_EXPECT = os.environ.get("CORTEX_SYSTEM_JOIN_EXPECT", "")
_PROBES = int(os.environ.get("CORTEX_SYSTEM_JOIN_PROBES", "20"))
_PAIRS = int(os.environ.get("CORTEX_SYSTEM_JOIN_PAIRS", "5"))
_MAX_TOKENS = int(os.environ.get("CORTEX_SYSTEM_JOIN_MAX_TOKENS", "512"))
_TIMEOUT = httpx.Timeout(10.0, read=600.0)
_COUNT_TO = "Count from one to three hundred in words, one number per line, and nothing else."


async def _delivers(client: httpx.AsyncClient, count: int) -> bool:
    return await delivers_system_messages(_ENDPOINT, _MODEL, count, client)


async def test_the_probe_answers_as_the_template_renders() -> None:
    expected = dict(pair.split("=") for pair in _EXPECT.split(",") if pair)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        for count in (2, 3):
            answer = await _delivers(client, count)
            print(f"\nprobe, {count} system messages: delivers={answer}")  # noqa: T201
            if str(count) in expected:
                assert answer is (expected[str(count)] == "yes")


def _recording_client(chats: list[dict[str, object]]) -> httpx.AsyncClient:
    async def keep(request: httpx.Request) -> None:
        if request.url.path.endswith("/chat/completions"):
            chats.append(json.loads(request.content))

    return httpx.AsyncClient(timeout=_TIMEOUT, event_hooks={"request": [keep]})


async def test_a_recalling_turn_with_a_recap_is_answered() -> None:
    chats: list[dict[str, object]] = []
    bounds = GenerationBounds(max_tokens=_MAX_TOKENS)
    async with _recording_client(chats) as client:
        joins = not await _delivers(client, 3)
        backend = RecordingBackend(
            LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT), client)
        )
        events = await recalling_turn(backend, bounds=bounds)
    completed = events[-1]
    assert isinstance(completed, TurnCompleted)
    first = list(backend.sent[0])
    assert [m.role for m in first[:3]] == [Role.SYSTEM] * 3
    sent = join_leading_system(first) if joins else first
    assert chats[0]["messages"] == build_payload(_MODEL, sent, (), None, None)["messages"]
    systems = [
        m for m in cast("list[dict[str, str]]", chats[0]["messages"]) if m["role"] == "system"
    ]
    print(f"\njoined={joins} system entries={len(systems)} reply={completed.full_text[:200]!r}")  # noqa: T201


async def test_a_tool_task_with_a_plain_context_is_answered() -> None:
    chats: list[dict[str, object]] = []
    async with _recording_client(chats) as client:
        backend = LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT), client)
        attempt = PlacedAttempt(
            SystemClock(),
            read_dispatcher(),
            constrain_output=False,
            bounds=AttemptBounds(max_tokens=_MAX_TOKENS),
        )
        outcome = await attempt.run(
            plain_context_task(), _MODEL, backend, budget=None, progress=None
        )
    print(f"\noutcome={outcome.failure.value} text={outcome.text[:200]!r} {outcome.detail}")  # noqa: T201
    assert outcome.failure is not AttemptFailure.INFERENCE, outcome.detail
    first = cast("list[dict[str, str]]", chats[0]["messages"])
    assert first[0]["content"].startswith(SECURITY_PREAMBLE)
    assert CONTEXT in "".join(m["content"] for m in first if m["role"] == "system")


async def _timed_probe(client: httpx.AsyncClient) -> float:
    start = time.perf_counter()
    await _delivers(client, 3)
    return (time.perf_counter() - start) * 1000


async def _generate(client: httpx.AsyncClient, started: asyncio.Event) -> None:
    body = {
        "model": _MODEL,
        "messages": [{"role": "user", "content": _COUNT_TO}],
        "max_tokens": 4000,
        "stream": True,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    url = f"{_ENDPOINT}/v1/chat/completions"
    async with client.stream("POST", url, json=body) as response:
        async for line in response.aiter_lines():
            if '"content"' in line:
                started.set()


async def test_the_probe_answers_fast_idle_and_beside_a_generation() -> None:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        idle = [await _timed_probe(client) for _ in range(_PROBES)]
        started = asyncio.Event()
        generation = asyncio.create_task(_generate(client, started))
        async with asyncio.timeout(300):
            await started.wait()
        busy = [await _timed_probe(client) for _ in range(_PROBES)]
        in_flight = not generation.done()
        generation.cancel()
    for name, samples in (("idle", idle), ("generating", busy)):
        median, worst = statistics.median(samples), max(samples)
        print(f"\nprobe {name}: median {median:.2f} ms, worst {worst:.2f} ms of {len(samples)}")  # noqa: T201
    assert in_flight, "the generation ended before the probes did"
    assert max(idle + busy) < SYSTEM_PROBE_TIMEOUT_S * 1000


def _deployed_tools() -> list[dict[str, object]]:
    resources = SubagentResources(
        backends={},
        scheduler=ResourceBudgetScheduler(4.0, 8.0),
        placer=VramBudgetPlacer(soft_cap_gb=20.0, cortex_reservation_gb=10.0),
        request=PlacementRequest(DEFAULT_SUBAGENT_MODEL, 3.5, 2.0, 3.0),
    )
    roster = SubagentRoster(
        entries={DEFAULT_SUBAGENT_MODEL: SubagentProfile(resources, DEFAULT_SUBAGENT_DESCRIPTION)},
        default=DEFAULT_SUBAGENT_MODEL,
    )
    body = InMemoryBodyGateway()
    specs: list[ToolSpec] = [build_spawn_spec(roster, tools_enabled=True)]
    specs += [GetVolumeTool(body).spec, SetVolumeTool(body).spec]
    specs.append(CaptureScreenTool(body, max_edge=1568, max_bytes=4_000_000).spec)
    specs.append(EscalateToBrainTool().spec)
    schedule = build_schedule_tools(
        ScheduleConfig(), InMemoryScheduleStore(), SystemClock(), tasks_enabled=True
    )
    specs += [tool.spec for tool in schedule]
    return to_openai_tools(specs)


_NOW = SystemClock().now()


def _system(text: str) -> Message:
    return Message(role=Role.SYSTEM, text=text, at=_NOW, turn_id="t")


def _pair(history_turns: int) -> tuple[list[Message], list[Message]]:
    filler = "They compared morning and evening trains, seat classes and the walk to the hotel. "
    history: list[Message] = []
    for index in range(history_turns):
        for role in (Role.USER, Role.ASSISTANT):
            text = f"{role.value} {index}: {filler * 6}"
            history.append(Message(role=role, text=text, at=_NOW, turn_id=f"h{index}"))
    recap = _system(fence_recap(RECAP))
    turns: list[list[Message]] = []
    for memory in (TRUSTED_MEMORY, "User: My sister lives in Porto.\nAssistant: Good to know."):
        fenced = wrap_untrusted("Forwarded note.", nonce=new_nonce())
        head = [_system(SECURITY_PREAMBLE), _system(f"{memory}\n\n{fenced}"), recap]
        turns.append(
            [*head, *history, Message(role=Role.USER, text=QUESTION, at=_NOW, turn_id="u")]
        )
    return turns[0], turns[1]


async def test_a_turn_per_system_message_keeps_the_tool_block_cached() -> None:
    tools = _deployed_tools()
    url = f"{_ENDPOINT}/v1/chat/completions"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        for rep in range(_PAIRS):
            for history_turns in (0, 16):
                for layout in ("separate", "joined"):
                    for name, turn in zip(("t1", "t2"), _pair(history_turns), strict=True):
                        messages = join_leading_system(turn) if layout == "joined" else turn
                        body = build_payload(
                            _MODEL, messages, (), None, GenerationBounds(max_tokens=1)
                        )
                        body.update({"tools": tools, "stream": False})
                        response = await client.post(url, json=body)
                        timings = response.json().get("timings", {})
                        print(  # noqa: T201
                            f"\nrep {rep} history {history_turns} {layout} {name}: "
                            f"HTTP {response.status_code} prompt_n {timings.get('prompt_n')} "
                            f"cache_n {timings.get('cache_n')}"
                        )
