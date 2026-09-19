# A tier can be asked at boot which of its own bounds are safe, and nothing asks

**Status:** declined 2026-08-29
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)

[ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md) decided that no capability probe
was possible, because `GET /props` reports a tier's template and not what the pick does with a
grammar in front of it. That ground moved twice. Naming the mechanism made `POST /apply-template`
worth asking, since it says whether the key reached the template at all, and asking every remaining
lineup entry found that the same rendering predicts the constrained result on all eleven: a tier
whose template renders the kwarg as a thought already closed honours the switch under a
`response_format`, and one that drops the think block and adds nothing does not.

The probe would be the sibling of `cortex_orchestrator.vision`, which already asks
`GET {endpoint}/props` for a tier's modalities. It would render the same short message twice, once
with `chat_template_kwargs` and once without, and report which of three states the tier is in: the
template ignores the key, reads it and leaves the thought open, or reads it and closes the thought.
Only the third is a tier where a bound pairing a cap with `thinking=False` and a schema returns a
short answer rather than none, and `rank_bounds` with `ORDER_ENVELOPE` is that pairing.

## History

- 2026-08-28: opened by the close of [R-465](465-the-switch-across-the-lineup.md), which turned a
  mechanism read off two picks into a prediction measured over the whole lineup and left it unread
  by anything that runs.
- 2026-08-29: declined by ADR-0049, which checked this entry against the tree the request value left
  and found its hazard sentence out of date. `rank_bounds(k)`, `TITLE_BOUNDS` and `RECAP_BOUNDS`
  each send `trace_tokens=0` now, so on a deployment whose engine reads that key the template's
  rendering decides nothing about any shipped bound. Measured on the failing tier of the pair,
  gemma-4-E4B on `b10666-4e97ac86e`, the constrained cell with the switch deliberated on 5 draws of
  5 and returned an empty reply every time, and the same cell sending `reasoning_budget_tokens: 0`
  deliberated on 0 of 5 and returned the envelope every time. The probe also cannot be written the
  way this entry describes it: both renderings were read in full, and the failing tier's two prompts
  differ (194 against 162 characters) while their tails are byte identical, so two string
  comparisons sort nothing and the prediction really turns on the tail closing a thought, which
  needs a per-pick template token this port exists not to know. What the entry wanted said at boot
  is [R-497](497-nothing-reports-a-trace-budget-that-went-unread.md). What the decline loses is
  [R-499](499-the-rendering-predictor-is-asserted-nowhere.md).
