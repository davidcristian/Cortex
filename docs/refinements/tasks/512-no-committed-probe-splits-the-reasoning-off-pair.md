# No committed probe can send one flag of the reasoning-off pair, or read what came back

**Status:** open, fix when it bites
**Area:** inference
**Trigger:** a llama.cpp image upgrade under this stack, or any change to which flags a subagent
server carries, either of which moves a rate that today only a scratch file can re-derive.
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-30 by the close of
[R-500](500-the-garbled-channel-marker-has-no-attributed-cause.md), which is the second sitting in
two days to draw the arm it needed by hand off `build_payload`. This is the probe half
[R-479](479-the-reasoning-budget-held-until-the-prompt-pushed.md) asked for, restated against what
the attribution turned out to need.

Two gaps, and the second one moved.

The **request** gap is the one already written down. `brain/packages/orchestrator/tests/test_envelope_cost_live.py`
runs the shipped `SubagentRunner`, so it sends exactly what `PlacedAttempt` sends, which names no
`trace_tokens`. A knob substituting a count into the bounds on the way past, the way `_Recording.substitute`
already does for the schema, would make the request key arm of the firm-prompt addendum reproducible
by a committed file.

The **reading** gap is the one the attribution needs and is the larger of the two. That harness
records `reasoning_chars`, and a trace that opens with a marker fragment and one that opens with a
plan are two different findings a length cannot tell apart. The attribution rested on three readings
none of the committed probes take: what the trace **opens** with, whether two arms drew the **same**
completion at the same seed, and what `POST /apply-template` renders for each arm. The first two
want a seed on the request, which nothing here sends.

**Why it was left.** The sitting that found the need for it spent its runway on the measurement, and
a probe written after the reading it exists to reproduce is worth less than the reading was. The
consequence of not having it is bounded and known: the rates in the marker addendum are a hand run,
labelled as one, and re-deriving them costs a scratch file rather than being impossible.

**What would close it.** Two knobs and one column on the envelope harness, which is the file that
already runs the shipped path. `CORTEX_ENVELOPE_TRACE_TOKENS` substituted into `GenerationBounds`
alongside the existing schema substitution, and a seed on the request so arms pair; then a recorded
reading of what the trace opened with, beside `reasoning_chars` rather than instead of it. The
detector belongs in a covered module rather than in the `integration` marked driver, for the reason
`scripts/contrast.py`, `scripts/envelopefloor.py` and `scripts/switchtail.py` each hold the
arithmetic behind a published claim: a number a document quotes should come out of something a gate
runs. `brain/packages/inference/tests/test_thinking_switch_live.py` is **not** the home for the
request half: its control asserts that the no-switch arm deliberated, which a correctly flagged
server will not do.

## Trail

- 2026-08-30: opened by the close of
  [R-500](500-the-garbled-channel-marker-has-no-attributed-cause.md), whose ADR-0005 marker addendum
  drew six arms by hand off `build_payload` and named the three readings no committed probe takes.
- 2026-09-02: a third hand run, by the close of
  [R-511](511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md), which drew 320 arms off
  `build_payload` and the injection harness's corpus from two scratch files. It adds a fourth
  reading to the three above, the one the marker addendum's budget arm lacked and the one that
  decided that close: what the **reply** holds. A thought the channel no longer shows can arrive
  inside `reply` as a narration or a plan, so a committed probe has to read the reply beside
  `reasoning_chars` and not only what the trace opens with.
