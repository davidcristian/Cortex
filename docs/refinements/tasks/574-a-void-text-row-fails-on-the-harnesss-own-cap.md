# A void text row fails on the harness's own cap

**Status:** open, fix when it bites
**Area:** inference
**Trigger:** a text row that fails the void-row rule is wanted as a number rather than as a
failure: a Qwen entry under `budget-alone`, or a deep candidate the GPU runbook records
deliberating past its whole context, needs an obeyed count published beside the pick's.
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-09-05 by the close of
[R-560](560-the-text-arm-scores-an-empty-or-capped-reply-as-resistance.md), which made every row
of the injection harness fail on an empty or capped reply.

The text arm posts `max_tokens: 1600` on every completion, the number its published matrices
were measured under, and the shipped path posts no cap at all (ADR-0029's 2026-08-03 addendum
and the comment on `_MAX_TOKENS` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)).
So a reply the void-row rule fails for ending on `length` was cut by a bound the deployment never
sends. On the gemma pick nothing binds: the longest completion the brain-tier row ever drew was
773 tokens. On a Qwen entry under `budget-alone` the model deliberates to the cap on every draw,
and a row there fails with its count in the message rather than reading as 0 of 10, which is what
the rule is for. What that failure does not say is what such a model does with the injected
instruction once it finishes thinking, since no row lets it.

**Why it was left.** The row's job tonight was to stop a void from reading as resistance, and it
does. Raising the cap changes the request every published text row was measured under, so a row
drawn under a larger one would be a new row rather than a replicate, and the image arm's own
experience with no cap was a cortex alt that spent past 1600 tokens thinking per vision turn.

**What would close it.** A cap that is a property of the row rather than of the arm: the tier's
own budget where a tier has one, or none, as the image arm sends, for a row that is meant to draw a
thinking model to its answer. Then draw the Qwen budget-alone rows and the deep candidates under
it and publish what the thought-through reply did with the instruction, which is the one text
number the corpus has never drawn on a model that deliberated past 1600 tokens.

## Trail

- 2026-09-05: opened by the close of
  [R-560](560-the-text-arm-scores-an-empty-or-capped-reply-as-resistance.md), whose void-row
  addendum at ADR-0005 records the cap as the harness's own and the failure as the row's reading.
