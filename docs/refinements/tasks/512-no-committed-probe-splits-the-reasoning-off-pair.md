# No committed probe sends the request's own trace budget, or pairs two arms at a seed

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-09-09

Opened 2026-08-30 by the close of
[R-500](500-the-garbled-channel-marker-has-no-attributed-cause.md), which is the second sitting in
two days to draw the arm it needed by hand off `build_payload`. This is the probe half
[R-479](479-the-reasoning-budget-held-until-the-prompt-pushed.md) asked for, restated against what
the attribution turned out to need.

Two gaps, and both are in what a committed file can **send** rather than in what it records.

The **request** gap is the one already written down. `brain/packages/orchestrator/tests/test_envelope_cost_live.py`
runs the shipped `SubagentRunner`, so it sends exactly what `PlacedAttempt` sends, which names no
`trace_tokens`. A knob substituting a count into the bounds on the way past, the way `_Recording.substitute`
already does for the schema, would make the request key arm of the firm-prompt addendum reproducible
by a committed file.

The **seed** gap is what makes two arms comparable. Nothing in this repo sends llama.cpp a `seed` on
any request: not `build_payload`, not the envelope harness, and not the two live probes in the
inference package. Both hand runs that attributed a behaviour to one flag added one in a scratch
file, and the pairing is what made their identity claims comparisons rather than two rates, the
marker addendum's 20 of 20 and the budget-alone addendum's 40 of 40. Without a seed on the request
a committed file can report a rate and cannot report that two arms drew the same completion.

**What the committed harnesses already read**, which this entry was wrong about from the day it was
written. The envelope harness records `reasoning_head` and `stream_head` beside `reasoning_chars`
and keeps `output` whole, so what the trace opens with and what the reply holds are both in every
sample it has written since it landed on 2026-08-26, four days before this entry claimed no
committed probe takes either reading. `brain/packages/inference/tests/test_thinking_switch_live.py`
has asked `POST /apply-template` since 2026-08-28 and `just switch-tail` reads that rendering back
against the cells the same run drew, so the third reading is not only committed but gated. What
those two cannot do is what the two gaps above name.

**Why it was left.** The sitting that found the need for it spent its runway on the measurement, and
a probe written after the reading it exists to reproduce is worth less than the reading was. The
consequence of not having it is bounded and known: the rates in the marker addendum are a hand run,
labelled as one, and re-deriving them costs a scratch file rather than being impossible.

**What would close it.** Two knobs on the envelope harness, which is the file that already runs the
shipped path: `CORTEX_ENVELOPE_TRACE_TOKENS` substituted into `GenerationBounds` alongside the
existing schema substitution, and a seed on the request so arms pair. Any reading taken off the
recorded heads belongs in a covered module rather than in the `integration` marked driver, for the
reason `scripts/contrast.py`, `scripts/envelopefloor.py` and `scripts/switchtail.py` each hold the
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
- 2026-09-09: claims held to the code, and the reading gap does not exist. Three of the four
  readings this entry says no committed probe takes are recorded by committed files, and every one
  of them was already there when the entry was written: `reasoning_head`, `stream_head` and the
  whole `output` in `test_envelope_cost_live.py` since 2026-08-26, and the `/apply-template`
  rendering in `test_thinking_switch_live.py` since 2026-08-28, read back by `just switch-tail`.
  What survives is the request key and the seed, neither of which any file here sends, so the body
  above is rewritten around those two and the title says them. The trigger is gone with the
  deferral: its first limb fired on 2026-09-02, when the image under this stack had moved from
  `b10666-4e97ac86e` to `b10680-d7bd3bfca` and the rates were re-derived on the newer build by two
  scratch files, which is the cost the trigger named and the bullet above records without noticing
  it was the trigger.
