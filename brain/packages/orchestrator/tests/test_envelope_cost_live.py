"""Integration: what the reply envelope costs a narrow subtask, measured paired (ADR-0028).

`CORTEX_SUBAGENTS_MAX_TOKENS` is derived from replies measured on the **unconstrained** shape,
which is the tools-enabled one. A subagents-only stack hands its subagents no dispatcher, so
`constrain_output` is on and every reply is decoded into the fixed `{"reply": ...}` envelope. That
is the shape `docker/docker-compose.subagents.yml` ships, and one run of it hit the cap on a
summarization the raw shape answers well inside it. One sample cannot separate the envelope from
the body it ran over or from sampling variance on a 4B model, so this driver runs **both shapes
over the same bodies** and leaves the pairing to arithmetic rather than to a reading.

Blocked, paired, and serialized: for each report body every arm runs in turn and every draw of the
body repeats that block, one stream at a time against one `llama-server`, so the arms of a body see
the same machine and the wall clocks stay comparable with the batch this repo already measured.
Each body is its own report, so no two *bodies* share a slot's prompt cache; the arms of one draw
share it by construction, being the same prompt, which is what makes them paired and which costs
every arm after the first about ten seconds less prompt eval than the first paid.

It writes one `contrast.py` sample per arm (`arm`, and `turns` carrying `question`/`ttft`/`wall`),
rewritten after every completed run so a run cut short still leaves whole draws behind. Each turn
also carries the reading this measurement is really about, `tokens` off the server's own
`timings.predicted_n`, plus the stop reason and what the runner told the cortex; `contrast.py`
reads the seconds and ignores the rest.

Integration-marked, so CI and the coverage gate never see it. Bring up the subagent server
(docs/runbooks/subagents-cpu.md section 1), then:

    cd brain && CORTEX_SUBAGENTS_ENDPOINT=http://127.0.0.1:8082 \\
      CORTEX_ENVELOPE_OUT=../measurements \\
      uv run pytest -m integration --no-cov -s \\
      packages/orchestrator/tests/test_envelope_cost_live.py

Six knobs size a run to a budget or turn it into a probe. `CORTEX_ENVELOPE_BODIES` runs only
the first N bodies; `CORTEX_ENVELOPE_ARMS` runs a subset of
`raw,constrained,bare,described,prefaced`;
`CORTEX_ENVELOPE_DRAWS` repeats every arm of every body that many times, because one draw of a
sampled model is a single sample rather than a measurement; `CORTEX_ENVELOPE_MAX_TOKENS` overrides
the cap the runs are given, which is how the length the constrained arm would write is read past
the shipped cap that truncates it; and `CORTEX_ENVELOPE_TAG` suffixes the sample names so a probe
cannot overwrite the run it sits beside. `CORTEX_ENVELOPE_HEAD` sets how much of each half of the
stream is kept verbatim, which is separate from `output`: the reply itself is always kept whole,
because what an answer says is the reading this harness takes. `CORTEX_ENVELOPE_INSTRUCTION`
replaces the subtask every body is given, which is the only place this engine lets anything be
said to the model about the envelope at all.

Three arms exist for questions `raw` and `constrained` cannot ask between them. `raw` and
`constrained` differ in whether a grammar is in play at all, and since the runner appends
`REPLY_INSTRUCTION` to every constrained subtask they now differ in a sentence too (ADR-0028
instruction addendum); `bare` is the shipped constrained path with that sentence taken back off on
the wire, which is the envelope as it stood before the sentence existed and the counterfactual every
rate below is read against. `described` is the shipped envelope with one sentence added to
its `reply` property saying what the field is for, so the difference between it and `constrained`
is the description and nothing else. The shipped `REPLY_ENVELOPE` is a bare typed string, which
tells a model the shape of the field and nothing about its purpose, and whether saying nothing
about its purpose costs the answer anything can be measured by changing the schema. `prefaced`
then asks the other question, whether what lands in `reply` is there because the grammar offers it
nowhere else to go, by adding a required field ahead of it that it can go to.

What it found on 2026-08-26, recorded in full in the ADR-0005 envelope addendum: the envelope
cost 1.01 to at least 2.36 times the raw shape's tokens for a shorter reply, the tokens going to a
reasoning trace the run then dropped unread. The lever that stops that trace is a server flag
rather than a request key (ADR-0005 thinking-lever addendum), so **a server started without
`--reasoning-budget 0` reproduces the defect rather than the fix**: with it, the same three
bodies at the shipped cap finish at 63 to 89 decoded tokens with no trace at all, and without it
the first of them spends 200 tokens on trace alone.

What it found on 2026-08-28, once the arms above existed and every cell was drawn ten times
(ADR-0005 answer addendum): those short finished replies are the defect rather than the fix. Over
four bodies at ten draws the unconstrained arm returned a summary on 40 of 40 and the shipped
envelope on 10 of 40, the rest narrating the subtask rather than doing it, and neither schema arm
moved that.
So a run of this harness that reports the envelope finishing quickly inside its cap is reporting
the failure, and `output` is the field that says which it is.

What it found the same night once the sentence shipped, over three subtask shapes rather than one
(ADR-0028 instruction addendum): the sentence is the repair, and `CORTEX_ENVELOPE_INSTRUCTION` is
how another shape is asked. That knob replaces the subtask; the runner still appends the shipped
sentence to whatever it is on the constrained path, so the way to measure a candidate wording is to
change the constant and re-run rather than to type a longer instruction here.

**Every rate this produces is read against `raw`, and that arm is held to a floor elsewhere**
(ADR-0028 control-arm addendum). It returned 96 of 96 on three picks and then 93 and 92 on two
more, both times because the pick failed the subtask rather than because the envelope took an
answer away, so the arm every number here is divided by is a measurement and not a constant. This
file records what each run did, including the instruction the arm really sent, the report body it
was given and whether the arm is the control, and `scripts/envelopefloor.py` turns those records
into rates with the interval the addenda publish and refuses to publish a comparison at all when a
control cell is proven below nine tenths of its own runs. It publishes two rates per cell, what a
run stood and what a reply delivered, the second judged per subtask shape against the body this
file records (ADR-0028 judged-delivery addendum). The arithmetic is over there rather than here
for the reason
`contrast.py` holds the turn-cost interval: a published number's arithmetic belongs in a file the
gate covers, and nothing covers this one.
"""

import json
import os
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import replace
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
# How many times each arm of each body is drawn. One, so every recipe written before this knob
# existed still means what it said. Above one is what a quality reading needs: this tier samples,
# and a cell read once is a draw that a reader will quote as a rule.
_DRAWS = int(os.environ.get("CORTEX_ENVELOPE_DRAWS", "1"))
# Named where the sample is written as well as where the run is configured, so a diagnostic at a
# raised cap cannot silently overwrite the shipped-cap sample it is meant to sit beside.
_TAG = os.environ.get("CORTEX_ENVELOPE_TAG", "")
# How much of each half is kept verbatim. A count says the tokens went somewhere other than
# the reply and cannot say where, and where is the whole of what a retune would rest on.
_HEAD = int(os.environ.get("CORTEX_ENVELOPE_HEAD", "400"))
# The fields the sample keeps whole and the per-run line drops: all three are long and two of them
# are the same string on every run of an arm, so printing any buries the numbers a reader watches.
_UNPRINTED = frozenset({"instruction", "context", "output"})

# The shipped envelope with one sentence added, and the only difference between the `constrained`
# arm and the `described` one. It says what the field is for and nothing about how to fill it: a
# description that told the model not to narrate would measure the instruction rather than the
# schema, and the question here is what an empty property costs, not what a better prompt buys.
# Built from the shipped constant rather than retyped, so it cannot drift from the grammar it is
# a variant of, and it lives here rather than in the core because a probe arm is not a shape
# anything ships.
#
# It has been run and it changes nothing, which is a reading about the engine rather than about the
# wording: this build renders the same prompt with a schema and without one, so a `description` here
# reaches the grammar builder and no model (ADR-0005 answer addendum). The arm stays because that is
# the sort of claim a later build could falsify, and re-running it is how anyone would find out.
_REPLY_DESCRIPTION = "The answer to the instruction, written out in full as plain text."
_DESCRIBED_ENVELOPE: JsonSchema = {
    **REPLY_ENVELOPE,
    "properties": {"reply": {"type": "string", "description": _REPLY_DESCRIPTION}},
}

# The fourth arm, and the one that asks about the cause rather than about the cost. A tier told not
# to think still opens a summarization by planning it, and under the shipped envelope the only
# grammatical position for that text is inside `reply`, which is why a reader gets a plan where an
# answer belongs. This envelope gives the plan a field of its own, ahead of the reply and required
# so the grammar cannot skip it, leaving `reply` the position it was always meant to hold. The
# runner unwraps `reply` and nothing else, so what the cortex would be handed is unchanged, and so
# is the appended-structure guarantee (ADR-0028): the extra field is inside the grammar, not after
# it. It is a probe and not a proposal; what it measures is whether the narration has somewhere
# else to go.
#
# The answer is that it does not need one. Run at ten draws over four bodies it lands on the same
# rate as the arm with no such field, the model filling `notes` with a plan and `reply` with more
# plan, so what arrives in `reply` is not overflow: this pick is treating a plan as the whole of its
# output, and no rearrangement of the fields talks it out of that.
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

# Which schema each arm's request carries, and therefore what the arm is. `None` is the raw shape,
# which is also the shape that tells the runner not to unwrap anything.
_SCHEMAS: dict[str, JsonSchema | None] = {
    "raw": None,
    "constrained": REPLY_ENVELOPE,
    "bare": REPLY_ENVELOPE,
    "described": _DESCRIBED_ENVELOPE,
    "prefaced": _PREFACED_ENVELOPE,
}

# The one arm that is the shipped path with something taken away. `constrained` now carries
# `REPLY_INSTRUCTION` because the runner appends it to every constrained subtask (ADR-0028
# instruction addendum); `bare` runs that same shipped path and removes the sentence again on the
# wire, so what it measures is the envelope as it stood before the sentence existed. It is the
# counterfactual arm, and it exists here rather than as a config knob because the sentence and the
# grammar are one contract: a deployment turns both off together or neither, and only a measurement
# wants the halves apart. Stripping is exactly the instrument `substitute` already is, one request
# field changed on the way past with every other line of the run the shipped one.
_STRIPPING_ARMS = frozenset({"bare"})

# The summarization shape the total-cap addendum found longest of the narrow four, over four
# report bodies of about the same length. Different subject matter each time, so a body that
# happens to invite a long answer shows up as one pair out of line rather than as the reading.
#
# Overridable, and for one reason worth stating where the override is. This build shows the model
# no part of a `response_format` schema: the rendered prompt is byte-identical with the envelope
# and without it, so a property's `description` is read by the grammar builder and by nothing else.
# Whatever an envelope could have told the model about its field can therefore only be said in the
# instruction, and the knob is what lets that be measured against the same bodies as the arms above.
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


class _Recording:
    """An ``InferenceBackend`` that passes everything through and keeps the server's own numbers.

    A decorator rather than a fork of the adapter, so what runs under measurement is the shipped
    ``LlamaCppBackend`` and the only thing added is a reading. ``DecodeCadence`` carries
    llama.cpp's ``predicted_n``, which is the decoded length this measurement is about, and
    ``DecodeStop`` carries why the completion ended, which is how the cap announces itself.

    ``substitute`` is the one thing it changes rather than records, and it changes exactly one
    request field. The runner reaches for ``REPLY_ENVELOPE`` by name, so an arm that differs only
    in the schema cannot be configured from outside it; swapping the schema here keeps every other
    line of the run the shipped one, including the unwrap, which still finds ``reply`` because
    every arm's grammar still declares it.
    """

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
        # The instruction this arm really put on the wire, observed rather than reconstructed: the
        # runner appends its own sentence on the constrained path and the stripping arm takes it
        # back off here, so what a reader would have to re-derive from two rules is instead read
        # off the messages. It is what `scripts/envelopefloor.py` judges an echoed reply against,
        # and it is the field that says which subtask shape a run belongs to.
        self.instruction = ""
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
        asked = self._substitute if schema is not None and self._substitute is not None else schema
        sent = self._without_instruction(messages) if self._strip_instruction else messages
        asks = [message.text for message in sent if message.role is Role.USER]
        assert len(asks) == 1, f"one user message is the subtask, got {len(asks)}"
        self.instruction = asks[0]
        events = self._inner.stream(model, sent, tools=tools, schema=asked, bounds=bounds)
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
        """``messages`` with the runner's appended sentence taken back off, and a check that it
        was there: an arm that silently stripped nothing would report the shipped path twice."""
        stripped = [
            replace(message, text=message.text.replace(f" {REPLY_INSTRUCTION}", ""))
            for message in messages
        ]
        assert stripped != list(messages), "nothing to strip: the runner sent no instruction"
        return stripped


def _roster(backend: InferenceBackend) -> SubagentRoster:
    """Build a roster from the shipped entry's own numbers, with every spawn kept on the CPU path.

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
    client: httpx.AsyncClient, name: str, body: str, *, arm: str, draw: int
) -> dict[str, Any]:
    """Run one body on one shape through the real runner and report what came back."""
    schema = _SCHEMAS[arm]
    recorder = _Recording(
        LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT or ""), client),
        substitute=schema,
        strip_instruction=arm in _STRIPPING_ARMS,
    )
    store = InMemoryTaskStore()
    runner = SubagentRunner(
        store,
        _roster(recorder),
        SystemClock(),
        constrain_output=schema is not None,
        bounds=AttemptBounds(max_tokens=_MAX_TOKENS, timeout_s=DEFAULT_SUBAGENT_RUN_TIMEOUT_S),
    )
    task_id = f"{name}-{arm}-{draw}"
    await store.put_task(
        SubagentTask(id=task_id, instruction=_INSTRUCTION, context=body, at=datetime.now(UTC))
    )
    started = time.monotonic()
    result = await runner.run(task_id)
    wall = time.monotonic() - started
    turn = {
        "question": name,
        "arm": arm,
        "draw": draw,
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
        # The three fields the sample keeps whole and the printed line drops, being long and being
        # the same on every run of an arm. A length says a reply happened; whether it answered the
        # instruction or described answering it is in the words, and that reading is what this
        # harness was extended to support. The instruction beside it is what the floor reader
        # groups a shape by and judges an echoed reply against, and the body beside that is what
        # the shape's own judge reads the reply against: a number recall or a reporting period is
        # a claim about this report and about no other (ADR-0028 judged-delivery addendum).
        "instruction": recorder.instruction,
        "context": body,
        "output": result.output,
        "stream_head": recorder.text[:_HEAD],
        "reasoning_head": recorder.reasoning[:_HEAD],
    }
    printed = {key: value for key, value in turn.items() if key not in _UNPRINTED}
    print(f"  {task_id}: {json.dumps(printed)}", flush=True)  # noqa: T201 -- the report is the point
    return turn


def _write(arm: str, turns: list[dict[str, Any]]) -> None:
    """Rewrite one arm's sample, so a run cut short still leaves the draws it finished."""
    _OUT.mkdir(parents=True, exist_ok=True)
    path = _OUT / f"envelope-{arm}{_TAG}.json"
    sample = {"arm": arm, "control": _SCHEMAS[arm] is None, "turns": turns}
    path.write_text(json.dumps(sample, indent=2) + "\n", encoding="utf-8")


@pytest.mark.integration
@pytest.mark.skipif(not _ENDPOINT, reason="set CORTEX_SUBAGENTS_ENDPOINT to a live subagent server")
async def test_the_envelope_against_the_raw_shape_over_the_same_bodies() -> None:
    """Every shape over each body, raw first, writing after every completed run."""
    turns: dict[str, list[dict[str, Any]]] = {arm: [] for arm in _ARMS}
    # No request timeout: a CPU subtask streams for minutes and the stall ceiling is per read.
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None)) as client:
        for name, body in list(_BODIES.items())[:_LIMIT]:
            # Draws inside a body and arms inside a draw, so a run cut short loses whole draws of
            # a whole body rather than one arm of one, which is the unit the pairing is over.
            for draw in range(1, _DRAWS + 1):
                for arm in _ARMS:
                    turns[arm].append(await _one(client, name, body, arm=arm, draw=draw))
                    _write(arm, turns[arm])
    # Printed before the assertions below, so a run that fails one still names what it wrote.
    # The rates are not computed here: an arm's delivered rate is a published number and the
    # arithmetic behind one belongs in a gated tool, which is also what holds the control arm to
    # its floor and refuses to publish a comparison read against a control that fell through it.
    # Resolved rather than as written: `_OUT` is read relative to `brain/`, and the line below is
    # pasted into a shell that is somewhere else.
    written = " ".join(str((_OUT / f"envelope-{arm}{_TAG}.json").resolve()) for arm in _ARMS)
    print(  # noqa: T201 -- the report is the point
        f"\nwrote {len(_ARMS)} arm sample(s): {written}\n"
        "  none of this is a comparison until the control arm is published:\n"
        f"  just envelope-floor {written}",
        flush=True,
    )
    # The measurement is the numbers printed and written above. What has to hold whatever the
    # model decides is that every arm answered over the same bodies, which is what pairs them.
    asked = [[(turn["question"], turn["draw"]) for turn in seen] for seen in turns.values()]
    assert all(seen == asked[0] for seen in asked), f"the arms asked different bodies: {asked}"
    everything = [turn for seen in turns.values() for turn in seen]
    assert all(turn["tokens"] is not None for turn in everything), "a run reported no timings"
