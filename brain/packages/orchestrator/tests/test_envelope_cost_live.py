"""Integration: what the reply envelope costs a narrow subtask, measured paired (ADR-0028).

`CORTEX_SUBAGENTS_MAX_TOKENS` is derived from replies measured on the **unconstrained** shape,
which is the tools-enabled one. A subagents-only stack hands its subagents no dispatcher, so
`constrain_output` is on and every reply is decoded into the fixed `{"reply": ...}` envelope. That
is the shape `docker/docker-compose.subagents.yml` ships, and one run of it hit the cap on a
summarization the raw shape answers well inside it. One sample cannot separate the envelope from
the body it ran over or from sampling variance on a 4B model, so this driver runs **both shapes
over the same bodies** and leaves the pairing to arithmetic rather than to a reading.

Blocked, paired, and serialized: for each report body the raw arm runs and then the constrained
arm, one stream at a time against one CPU `llama-server`, so the two arms of a body see the same
machine and the wall clocks stay comparable with the batch this repo already measured. Each body
is its own report, so no two *pairs* share a slot's prompt cache; the two arms of one pair share it
by construction, being the same prompt, which is what makes them paired and which costs the second
arm about ten seconds less prompt eval than the first paid.

It writes one `contrast.py` sample per arm (`arm`, and `turns` carrying `question`/`ttft`/`wall`),
rewritten after every completed pair so a run cut short still leaves whole pairs behind. Each turn
also carries the reading this measurement is really about, `tokens` off the server's own
`timings.predicted_n`, plus the stop reason and what the runner told the cortex; `contrast.py`
reads the seconds and ignores the rest.

Integration-marked, so CI and the coverage gate never see it. Bring up the subagent server
(docs/runbooks/subagents-cpu.md section 1), then:

    cd brain && CORTEX_SUBAGENTS_ENDPOINT=http://127.0.0.1:8082 \\
      CORTEX_ENVELOPE_OUT=../measurements \\
      uv run pytest -m integration --no-cov -s \\
      packages/orchestrator/tests/test_envelope_cost_live.py

Four knobs size a run to a budget or turn it into a probe. `CORTEX_ENVELOPE_BODIES` runs only
the first N bodies; `CORTEX_ENVELOPE_ARMS` runs a subset of `raw,constrained`;
`CORTEX_ENVELOPE_MAX_TOKENS` overrides the cap the runs are given, which is how the length the
constrained arm would write is read past the shipped cap that censors it; and
`CORTEX_ENVELOPE_TAG` suffixes the sample names so a probe cannot overwrite the run it sits
beside. `CORTEX_ENVELOPE_HEAD` sets how much of each half of the stream is kept verbatim.

What it found on 2026-08-26, recorded in full in the ADR-0005 envelope addendum: the envelope
cost 1.01 to at least 2.36 times the raw shape's tokens for a shorter reply, the tokens going to a
reasoning trace the run then dropped unread. The lever that stops that trace is a server flag and
not a request key (ADR-0005 thinking-lever addendum), so **a server started without
`--reasoning-budget 0` reproduces the defect and not the fix**: with it, the same three bodies at
the shipped cap finish at 63 to 89 decoded tokens with no trace at all, and without it the first
of them spends 200 tokens on trace alone.
"""

import json
import os
import time
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
from cortex_inference import LlamaCppBackend

_ENDPOINT = os.environ.get("CORTEX_SUBAGENTS_ENDPOINT")
_MODEL = os.environ.get("CORTEX_SUBAGENTS_MODEL", "subagent")
_OUT = Path(os.environ.get("CORTEX_ENVELOPE_OUT", "."))
_LIMIT = int(os.environ.get("CORTEX_ENVELOPE_BODIES", "4"))
# The cap the runs are given, and which arms run at all. Both exist for the second question this
# harness has to answer: the shipped cap censors the constrained arm at 1024, so the length that
# arm would have written is a lower bound rather than a reading, and learning it means one run at
# a cap raised toward the server's own per-slot context. Naming the two as knobs keeps that
# diagnostic inside the harness, where the next reader finds it, instead of in a scratchpad.
_MAX_TOKENS = int(os.environ.get("CORTEX_ENVELOPE_MAX_TOKENS", str(DEFAULT_SUBAGENT_MAX_TOKENS)))
_ARMS = tuple(os.environ.get("CORTEX_ENVELOPE_ARMS", "raw,constrained").split(","))
# Named where the sample is written as well as where the run is configured, so a diagnostic at a
# raised cap cannot silently overwrite the shipped-cap sample it is meant to sit beside.
_TAG = os.environ.get("CORTEX_ENVELOPE_TAG", "")
# How much of each half is kept verbatim. A count says the tokens went somewhere other than
# the reply and cannot say where, and where is the whole of what a retune would rest on.
_HEAD = int(os.environ.get("CORTEX_ENVELOPE_HEAD", "400"))

# The summarization shape the total-cap addendum found longest of the narrow four, over four
# report bodies of about the same length. Different subject matter each time, so a body that
# happens to invite a long answer shows up as one pair out of line rather than as the reading.
_INSTRUCTION = "Summarize the report below, keeping every detail."

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


class _Recording:
    """An ``InferenceBackend`` that passes everything through and keeps the server's own numbers.

    A decorator rather than a fork of the adapter, so what runs under measurement is the shipped
    ``LlamaCppBackend`` and the only thing added is a reading. ``DecodeCadence`` carries
    llama.cpp's ``predicted_n``, which is the decoded length this measurement is about, and
    ``DecodeStop`` carries why the completion ended, which is how the cap announces itself.
    """

    def __init__(self, inner: InferenceBackend) -> None:
        self._inner = inner
        self.cadence: DecodeCadence | None = None
        self.stop: DecodeStop | None = None
        self.ttft_s: float | None = None
        # Both halves of what the model wrote, kept apart. A delegated run drops a reasoning
        # delta unread, so a tier that reasons spends its cap on text the cortex never sees and
        # a reading that counted only the reply would call that a short answer.
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
        events = self._inner.stream(model, messages, tools=tools, schema=schema, bounds=bounds)
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


def _roster(backend: InferenceBackend) -> SubagentRoster:
    """The shipped entry's own numbers, with every spawn kept on the CPU path.

    A zero-headroom placer is what a closed GPU tier leaves, and it is what the batch behind the
    whole-subtask interval used, so these readings sit beside that one.
    """
    resources = SubagentResources(
        backends={PlacementTarget.GPU: backend, PlacementTarget.CPU: backend},
        scheduler=ResourceBudgetScheduler(4.0, 8.0),
        placer=VramBudgetPlacer(soft_cap_gb=11.0, cortex_reservation_gb=11.0),
        request=PlacementRequest(_MODEL, vram_gb=3.5, cpus=2.0, memory_gb=3.0),
    )
    return SubagentRoster(entries={_MODEL: SubagentProfile(resources=resources)}, default=_MODEL)


async def _one(
    client: httpx.AsyncClient, name: str, body: str, *, constrain: bool
) -> dict[str, Any]:
    """Run one body on one shape through the real runner and say what came back."""
    recorder = _Recording(
        LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT or ""), client)
    )
    store = InMemoryTaskStore()
    runner = SubagentRunner(
        store,
        _roster(recorder),
        SystemClock(),
        constrain_output=constrain,
        bounds=AttemptBounds(max_tokens=_MAX_TOKENS, timeout_s=DEFAULT_SUBAGENT_RUN_TIMEOUT_S),
    )
    task_id = f"{name}-{'constrained' if constrain else 'raw'}"
    await store.put_task(
        SubagentTask(id=task_id, instruction=_INSTRUCTION, context=body, at=datetime.now(UTC))
    )
    started = time.monotonic()
    result = await runner.run(task_id)
    wall = time.monotonic() - started
    turn = {
        "question": name,
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
        "stream_head": recorder.text[:_HEAD],
        "reasoning_head": recorder.reasoning[:_HEAD],
    }
    print(f"  {task_id}: {json.dumps(turn)}", flush=True)  # noqa: T201 -- the report is the point
    return turn


def _write(arm: str, turns: list[dict[str, Any]]) -> None:
    """Rewrite one arm's sample, so a run cut short still leaves the pairs it finished."""
    _OUT.mkdir(parents=True, exist_ok=True)
    path = _OUT / f"envelope-{arm}{_TAG}.json"
    path.write_text(json.dumps({"arm": arm, "turns": turns}, indent=2) + "\n", encoding="utf-8")


@pytest.mark.integration
@pytest.mark.skipif(not _ENDPOINT, reason="set CORTEX_SUBAGENTS_ENDPOINT to a live subagent server")
async def test_the_envelope_against_the_raw_shape_over_the_same_bodies() -> None:
    """Both shapes over each body, raw first, writing after every completed pair."""
    turns: dict[str, list[dict[str, Any]]] = {arm: [] for arm in _ARMS}
    # No request timeout: a CPU subtask streams for minutes and the stall ceiling is per read.
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None)) as client:
        for name, body in list(_BODIES.items())[:_LIMIT]:
            for arm in _ARMS:
                turns[arm].append(await _one(client, name, body, constrain=arm == "constrained"))
                _write(arm, turns[arm])
    # The measurement is the numbers printed and written above; what must hold whatever the model
    # decides is that every arm answered over the same bodies, which is what makes them pairable.
    asked = [[turn["question"] for turn in seen] for seen in turns.values()]
    assert all(seen == asked[0] for seen in asked), f"the arms asked different bodies: {asked}"
    everything = [turn for seen in turns.values() for turn in seen]
    assert all(turn["tokens"] is not None for turn in everything), "a run reported no timings"
