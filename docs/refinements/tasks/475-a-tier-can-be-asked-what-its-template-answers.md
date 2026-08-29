# A tier can be asked at boot which of its own bounds are safe, and nothing asks

**Status:** declined 2026-08-29
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-28 by the close of
[R-465](465-the-switch-across-the-lineup.md), which turned a mechanism read off two picks into a
predictor measured over the whole lineup and then left the predictor unread by anything that runs.

[ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)'s switch-is-advisory addendum decided that no
capability probe was possible, on the ground that `GET /props` reports a tier's template and not
what the pick does with a grammar in front of it. That ground has moved twice. Naming the mechanism
made `POST /apply-template` worth asking, since it says whether the key reached the template at all;
asking every remaining lineup entry then found that the same rendering predicts the constrained
verdict on **all eleven**. A tier whose template answers "do not think" by rendering a thought
already closed honours the switch under a `response_format`, and one that answers by dropping the
think block and adding nothing does not. Both answers are one HTTP call and two string comparisons,
on a server that is up and before it has served a turn.

**What this would be.** The sibling of `cortex_orchestrator.vision`, which already probes
`GET {endpoint}/props` for a tier's modalities and answers `False` on every failure. This one
renders the same short message twice, once with `chat_template_kwargs` and once without, and reports
which of three states the tier is in: the template ignores the key entirely, it reads the key and
leaves the thought open, or it reads the key and closes the thought. Only the third is a tier where
a bound pairing a cap with `thinking=False` **and a schema** returns a short answer rather than no
answer, and `rank_bounds` with `ORDER_ENVELOPE` is exactly that pairing.

**Why it is worth more than the warning already shipped.** `cortex_core.drain` warns after the fact,
once per completion, naming the trace nobody read. That is the right line to have and it fires on a
reply that has already been deleted. The probe answers before a deployment serves anything, which is
the difference between a runbook step an operator has to remember to run and a stack that says on
boot which of its own side calls its pick cannot support.

**What has to be decided rather than typed.** Three things.

- **What it does with the answer.** A warning at startup is the cheap version and is probably
  right; refusing to serve is not, since the plain-shape bounds are safe on every pick measured and
  a schema-carrying side call is one of four. A deployment carrying the tier flag the subagent
  servers already carry is also safe and would be warned at anyway, so the probe has to read the
  tier's argv or accept that it warns about a hazard the flag already covers.
- **The predictor is eleven readings, not a theorem.** It is a property of llama.cpp's gemma-4 and
  native handlers as this build writes them, and a handler that gates its reasoning rule on
  `enable_thinking`, which sibling handlers in the same file already do, would hold the switch with
  a template that renders nothing. So the probe reports a prediction and should say so where it is
  read, and the live probe stays the thing that measures.
- **Its overlap with the lever.** [R-474](474-the-switch-could-be-rendered-as-a-lever-that-holds.md)
  would render the port's switch as the per-request budget key this build reads, which holds on
  every shape and would make the prediction moot wherever the engine is new enough. That entry names
  its own floor problem, an older build that ignores the key silently, and a probe is one honest
  answer to it. Whichever lands first should be read against the other.

## Trail

- 2026-08-29: declined by the ADR-0005 template-probe addendum, which re-derived this entry against
  the tree the request lever left and found its own hazard sentence out of date. `rank_bounds(k)`,
  `TITLE_BOUNDS` and `RECAP_BOUNDS` each carry `trace_tokens=0` now, so on a deployment whose
  engine reads that key the template's answer decides nothing about any shipped bound. Measured on
  the failing tier of the pair, gemma-4-E4B on `b10666-4e97ac86e`, the constrained cell with the
  switch deliberated on 5 draws of 5 and returned an empty reply on every one, and the same cell
  carrying `reasoning_budget_tokens: 0` deliberated on 0 of 5 and returned the envelope every time.
  The probe this entry describes also cannot be written the way it describes it: both renderings
  were read in full, the failing tier's two prompts **differ** (194 against 162 characters) while
  their tails are byte identical, so "two string comparisons" sorts nothing and the predictor really
  turns on the tail closing a thought, which needs a per pick template token this port exists not to
  know. What the entry wanted said at boot is
  [R-497](497-nothing-reports-a-trace-budget-that-went-unread.md), from a composition root that
  already holds the lever. What the decline loses is
  [R-499](499-the-rendering-predictor-is-asserted-nowhere.md).
