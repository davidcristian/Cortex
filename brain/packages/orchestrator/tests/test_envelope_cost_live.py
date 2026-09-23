import json
import os
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from cortex_core import (
    DEFAULT_SUBAGENT_MAX_TOKENS,
    DEFAULT_SUBAGENT_RUN_TIMEOUT_S,
    AttemptBounds,
    DecodeCadence,
    DecodeStop,
    GenerationBounds,
    InferenceBackend,
    InferenceEvent,
    InMemoryTaskStore,
    JsonSchema,
    Message,
    PlacementRequest,
    PlacementTarget,
    ReasoningChunk,
    ResourceBudgetScheduler,
    Role,
    SingleResidentModelManager,
    SubagentProfile,
    SubagentResources,
    SubagentRoster,
    SubagentRunner,
    SubagentTask,
    SystemClock,
    TextChunk,
    ToolSpec,
    VramBudgetPlacer,
)
from cortex_core.subagent_reply import REPLY_ENVELOPE, REPLY_INSTRUCTION
from cortex_inference import LlamaCppBackend, reads_a_trace_budget
from cortex_inference.request import TRACE_BUDGET_KEY

_ENDPOINT = os.environ.get("CORTEX_SUBAGENTS_ENDPOINT")
_MODEL = os.environ.get("CORTEX_SUBAGENTS_MODEL", "subagent")
_OUT = Path(os.environ.get("CORTEX_ENVELOPE_OUT", "."))
_LIMIT = int(os.environ.get("CORTEX_ENVELOPE_BODIES", "4"))
_MAX_TOKENS = int(os.environ.get("CORTEX_ENVELOPE_MAX_TOKENS", str(DEFAULT_SUBAGENT_MAX_TOKENS)))
_VARIANTS = tuple(os.environ.get("CORTEX_ENVELOPE_ARMS", "raw,constrained").split(","))
_DRAWS = int(os.environ.get("CORTEX_ENVELOPE_DRAWS", "1"))
_TAG = os.environ.get("CORTEX_ENVELOPE_TAG", "")
_HEAD = int(os.environ.get("CORTEX_ENVELOPE_HEAD", "400"))
# Every variant of one draw sends the same seed and each later draw sends the next integer, so
# the variants of a draw can be compared and a second run at the same base draws the same replies.
_SEED = os.environ.get("CORTEX_ENVELOPE_SEED")
_SEED_BASE = int(_SEED) if _SEED is not None else None
_TRACE = os.environ.get("CORTEX_ENVELOPE_TRACE_TOKENS")
_TRACE_TOKENS = int(_TRACE) if _TRACE is not None else None
_UNPRINTED = frozenset({"instruction", "context", "output"})

_REPLY_DESCRIPTION = "The answer to the instruction, written out in full as plain text."
_DESCRIBED_ENVELOPE: JsonSchema = {
    **REPLY_ENVELOPE,
    "properties": {"reply": {"type": "string", "description": _REPLY_DESCRIPTION}},
}

_PREFACED_ENVELOPE: JsonSchema = {
    "type": "object",
    "properties": {
        "notes": {
            "type": "string",
            "description": "Any planning or restatement of the task, before the answer.",
        },
        "reply": {"type": "string", "description": _REPLY_DESCRIPTION},
    },
    "required": ["notes", "reply"],
    "additionalProperties": False,
}

_SCHEMAS: dict[str, JsonSchema | None] = {
    "raw": None,
    "constrained": REPLY_ENVELOPE,
    "bare": REPLY_ENVELOPE,
    "described": _DESCRIBED_ENVELOPE,
    "prefaced": _PREFACED_ENVELOPE,
}

_STRIPPING_VARIANTS = frozenset({"bare"})

_INSTRUCTION = os.environ.get(
    "CORTEX_ENVELOPE_INSTRUCTION", "Summarize the report below, keeping every detail."
)

_BODIES: dict[str, str] = {
    "warehouse": (
        "Site report, north warehouse, week 34. Inbound pallets 1,842, up from 1,610 the week "
        "before. Outbound 1,795. Dock 3 was out of service Tuesday 09:20 to 14:05 for a hydraulic "
        "leveller seal replacement; the two spare docks absorbed the traffic and the queue peaked "
        "at nine trailers against a normal four. Pick accuracy 99.2% over 14,300 lines, with 114 "
        "mispicks, 71 of them in the small-parts aisle where the new bin labels have not yet been "
        "applied. Two forklift near-misses were logged, both at the aisle 7 blind corner, and the "
        "mirror ordered in week 31 has still not arrived. Agency headcount averaged 11 against a "
        "planned 8, driven by four absences in the night shift. Fuel for the yard tractors cost "
        "1,340 against a budget of 1,100. The cold store held between 2.1 and 3.4 degrees all "
        "week, inside tolerance, though the chart recorder in unit 2 dropped six hours of trace "
        "on Thursday and the cause is not yet known."
    ),
    "clinic": (
        "Clinic operations note, month ending. 2,410 appointments offered, 2,188 attended, 149 "
        "cancelled with notice and 73 missed without. The missed rate of 3.0% is down from 4.4% "
        "since reminder texts moved to 48 hours before rather than 24. Mean wait from referral to "
        "first appointment is 19 days for routine and 3 days for urgent, against targets of 21 "
        "and 5. Two clinicians were on leave for the second half of the month, which pushed "
        "Thursday afternoon lists to an average of 22 patients against a normal 16, and the "
        "recorded overrun on those lists averaged 41 minutes. Phone abandonment reached 14% in "
        "the first week, when the switchboard ran one seat short, and settled to 6% afterwards. "
        "Prescription turnaround held at under 24 hours except on the 12th, when the printer "
        "failed and 63 scripts went out the following morning. Three complaints were received, "
        "two about waiting-room noise and one about parking, and all three were acknowledged "
        "within the five-day standard."
    ),
    "fleet": (
        "Fleet maintenance summary, quarter three. 47 vehicles in service, four of them added in "
        "August. Scheduled services completed 138 of a planned 144; the six missed were all on "
        "the long-haul units and each was deferred by under a fortnight. Unplanned repairs "
        "numbered 61, costing 38,900 against a quarterly provision of 30,000, and the largest "
        "single item was a gearbox rebuild on unit 22 at 6,750. Tyre spend fell 12% after the "
        "move to the retread contract, though two retreads failed in service and both were "
        "replaced under warranty. Average fuel economy was 7.8 litres per hundred kilometres "
        "across the light fleet and 31.4 across the heavy, the heavy figure worsening 4% on the "
        "quarter, which the workshop attributes to the two new units still bedding in. Downtime "
        "totalled 214 vehicle-days, of which 96 were waiting on parts. The telematics rollout "
        "reached 39 vehicles; the remaining eight are the oldest units and need a harness that is "
        "on back order until November."
    ),
    "network": (
        "Network operations report, fortnight 18. Core availability 99.97%, with one incident: a "
        "line card in the east aggregation switch failed at 02:14 on the 9th and traffic "
        "reconverged in 47 seconds, inside the 60-second objective. Peak egress reached 41.2 "
        "gigabits against a provisioned 60, up from 37.8 the previous fortnight, and the growth "
        "is concentrated in the evening video window. Ninety-four change requests were raised, 88 "
        "approved, 4 rejected for insufficient rollback detail and 2 withdrawn. Two changes were "
        "backed out, one a firewall rule set that broke an internal API and one a firmware "
        "upgrade that reset a QoS profile. Mean time to acknowledge alerts was 4.1 minutes and "
        "mean time to resolve 38 minutes, both inside target, though the median hides a single "
        "11-hour ticket for a customer circuit awaiting a third-party field visit. Certificate "
        "expiry monitoring found three certificates inside 30 days, all renewed. The wireless "
        "controller upgrade is deferred a second time, now to fortnight 21, pending a maintenance "
        "window the retail sites will accept."
    ),
}


class _Wire(httpx.AsyncHTTPTransport):
    """The shipped request with a seed added below the port, and a copy of what went out."""

    def __init__(self) -> None:
        super().__init__()
        self.seed: int | None = None
        self.sent: dict[str, object] | None = None

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.path != "/v1/chat/completions":
            return await super().handle_async_request(request)
        body = cast("dict[str, object]", json.loads(request.content))
        if self.seed is not None:
            body["seed"] = self.seed
        self.sent = body
        if self.seed is None:
            return await super().handle_async_request(request)
        # Rebuilt rather than patched: the new body changes content-length, which httpx writes
        # from the content it is handed.
        length = b"content-length"
        headers = [(key, value) for key, value in request.headers.raw if key.lower() != length]
        seeded = httpx.Request(
            request.method,
            request.url,
            headers=headers,
            content=json.dumps(body).encode("utf-8"),
            extensions=request.extensions,
        )
        return await super().handle_async_request(seeded)


class _Recording:
    """An ``InferenceBackend`` that passes everything through and keeps the server's own numbers."""

    def __init__(
        self,
        inner: InferenceBackend,
        *,
        substitute: JsonSchema | None = None,
        strip_instruction: bool = False,
    ) -> None:
        self._inner = inner
        self._substitute = substitute
        self._strip_instruction = strip_instruction
        self.cadence: DecodeCadence | None = None
        self.stop: DecodeStop | None = None
        self.ttft_s: float | None = None
        self.instruction = ""
        self.text = ""
        self.reasoning = ""

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        started = time.monotonic()
        asked = self._substitute if schema is not None and self._substitute is not None else schema
        sent = self._without_instruction(messages) if self._strip_instruction else messages
        asks = [message.text for message in sent if message.role is Role.USER]
        assert len(asks) == 1, f"one user message is the subtask, got {len(asks)}"
        self.instruction = asks[0]
        held = (
            bounds
            if _TRACE_TOKENS is None
            else replace(bounds or GenerationBounds(), trace_tokens=_TRACE_TOKENS)
        )
        events = self._inner.stream(model, sent, tools=tools, schema=asked, bounds=held)
        async for event in events:
            if isinstance(event, TextChunk):
                if self.ttft_s is None:
                    self.ttft_s = time.monotonic() - started
                self.text += event.text
            if isinstance(event, ReasoningChunk):
                self.reasoning += event.text
            if isinstance(event, DecodeCadence):
                self.cadence = event
            if isinstance(event, DecodeStop):
                self.stop = event
            yield event

    @staticmethod
    def _without_instruction(messages: Sequence[Message]) -> list[Message]:
        """``messages`` with the runner's appended sentence taken back off, and a check that it was
        there: a variant that silently stripped nothing would report the shipped path twice.
        """
        stripped = [
            replace(message, text=message.text.replace(f" {REPLY_INSTRUCTION}", ""))
            for message in messages
        ]
        assert stripped != list(messages), "nothing to strip: the runner sent no instruction"
        return stripped


def _roster(backend: InferenceBackend) -> SubagentRoster:
    """Build a roster from the shipped entry's numbers, with every spawn kept on the CPU path."""
    resources = SubagentResources(
        backends={PlacementTarget.GPU: backend, PlacementTarget.CPU: backend},
        scheduler=ResourceBudgetScheduler(4.0, 8.0),
        placer=VramBudgetPlacer(soft_cap_gb=11.0, cortex_reservation_gb=11.0),
        request=PlacementRequest(_MODEL, vram_gb=3.5, cpus=2.0, memory_gb=3.0),
    )
    return SubagentRoster(entries={_MODEL: SubagentProfile(resources=resources)}, default=_MODEL)


async def _one(
    client: httpx.AsyncClient, wire: _Wire, name: str, body: str, *, variant: str, draw: int
) -> dict[str, Any]:
    """Run one body on one shape through the real runner and report what came back."""
    schema = _SCHEMAS[variant]
    recorder = _Recording(
        LlamaCppBackend(
            SingleResidentModelManager(_MODEL, _ENDPOINT or ""),
            client,
            send_trace_budget=_TRACE_TOKENS is not None,
        ),
        substitute=schema,
        strip_instruction=variant in _STRIPPING_VARIANTS,
    )
    store = InMemoryTaskStore()
    runner = SubagentRunner(
        store,
        _roster(recorder),
        SystemClock(),
        constrain_output=schema is not None,
        bounds=AttemptBounds(max_tokens=_MAX_TOKENS, timeout_s=DEFAULT_SUBAGENT_RUN_TIMEOUT_S),
    )
    task_id = f"{name}-{variant}-{draw}"
    await store.put_task(
        SubagentTask(id=task_id, instruction=_INSTRUCTION, context=body, at=datetime.now(UTC))
    )
    wire.sent = None
    started = time.monotonic()
    result = await runner.run(task_id)
    wall = time.monotonic() - started
    assert wire.sent is not None, "no completion went out on the wire"
    seed = wire.sent.get("seed")
    trace_budget = wire.sent.get(TRACE_BUDGET_KEY)
    assert seed == wire.seed, f"the wire carried seed {seed!r} where {wire.seed!r} was asked"
    assert trace_budget == _TRACE_TOKENS, (
        f"the wire carried {TRACE_BUDGET_KEY} {trace_budget!r} where {_TRACE_TOKENS!r} was asked"
    )
    turn = {
        "question": name,
        "arm": variant,
        "draw": draw,
        "seed": seed,
        "trace_budget": trace_budget,
        "cap": _MAX_TOKENS,
        "ttft": recorder.ttft_s if recorder.ttft_s is not None else wall,
        "wall": wall,
        "tokens": recorder.cadence.tokens if recorder.cadence else None,
        "tok_per_s": recorder.cadence.tokens_per_second if recorder.cadence else None,
        "stop": recorder.stop.reason.value if recorder.stop else None,
        "ok": result.ok,
        "detail": result.detail,
        "output_chars": len(result.output),
        "stream_text_chars": len(recorder.text),
        "reasoning_chars": len(recorder.reasoning),
        "instruction": recorder.instruction,
        "context": body,
        "output": result.output,
        "stream_head": recorder.text[:_HEAD],
        "reasoning_head": recorder.reasoning[:_HEAD],
    }
    printed = {key: value for key, value in turn.items() if key not in _UNPRINTED}
    print(f"  {task_id}: {json.dumps(printed)}", flush=True)  # noqa: T201 -- the report is the point
    return turn


def _write(variant: str, turns: list[dict[str, Any]]) -> None:
    """Rewrite one variant's sample file, so a run cut short still leaves the draws it finished."""
    _OUT.mkdir(parents=True, exist_ok=True)
    path = _OUT / f"envelope-{variant}{_TAG}.json"
    sample = {"arm": variant, "control": _SCHEMAS[variant] is None, "turns": turns}
    path.write_text(json.dumps(sample, indent=2) + "\n", encoding="utf-8")


@pytest.mark.integration
@pytest.mark.skipif(not _ENDPOINT, reason="set CORTEX_SUBAGENTS_ENDPOINT to a live subagent server")
async def test_the_envelope_against_the_raw_shape_over_the_same_bodies() -> None:
    turns: dict[str, list[dict[str, Any]]] = {variant: [] for variant in _VARIANTS}
    wire = _Wire()
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None), transport=wire) as client:
        if _TRACE_TOKENS is not None:
            assert await reads_a_trace_budget(_ENDPOINT or "", _MODEL, client), (
                f"this engine does not read {TRACE_BUDGET_KEY}, so no trace arm can be drawn on it"
            )
        for name, body in list(_BODIES.items())[:_LIMIT]:
            for draw in range(1, _DRAWS + 1):
                wire.seed = None if _SEED_BASE is None else _SEED_BASE + draw - 1
                for variant in _VARIANTS:
                    turns[variant].append(
                        await _one(client, wire, name, body, variant=variant, draw=draw)
                    )
                    _write(variant, turns[variant])
    written = " ".join(
        str((_OUT / f"envelope-{variant}{_TAG}.json").resolve()) for variant in _VARIANTS
    )
    print(  # noqa: T201 -- the report is the point
        f"\nwrote {len(_VARIANTS)} arm sample(s): {written}\n"
        "  none of this is a comparison until the control arm is published:\n"
        f"  just envelope-floor {written}",
        flush=True,
    )
    asked = [
        [(turn["question"], turn["draw"], turn["seed"]) for turn in seen] for seen in turns.values()
    ]
    assert all(seen == asked[0] for seen in asked), f"the arms asked different bodies: {asked}"
    everything = [turn for seen in turns.values() for turn in seen]
    assert all(turn["tokens"] is not None for turn in everything), "a run reported no timings"
