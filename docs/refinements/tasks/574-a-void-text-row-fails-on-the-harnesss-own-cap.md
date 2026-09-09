# A void text row fails on the harness's own cap

**Status:** open, fix when it bites
**Area:** inference
**Trigger:** a text row that fails the void-row rule is wanted as a number rather than as a
failure, which on this corpus means one of the two mixture-of-experts deep candidates the GPU
runbook records consuming a whole context and answering nothing, or any row later found ending on
`length` at the arm's cap, needing an obeyed count published beside the pick's.
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-09-09

Opened 2026-09-05 by the close of
[R-560](560-the-text-arm-scores-an-empty-or-capped-reply-as-resistance.md), which made every row
of the injection harness fail on an empty or capped reply.

The text arm posts `max_tokens: 1600` on every completion, the number its published matrices
were measured under, and the shipped path posts no cap at all (ADR-0029's 2026-08-03 addendum
and the comment on `_MAX_TOKENS` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)).
So a reply the void-row rule fails for ending on `length` was cut by a bound the deployment never
sends. On the gemma pick nothing binds: the longest completion the brain-tier row ever drew was
773 tokens against that cap. The case is the two mixture-of-experts deep candidates in
`BRAIN_CANDIDATES`, which the GPU runbook's brain-tier section records consuming an entire
8192-token context and returning `"content":""`: a row for either fails with its count in the
message rather than printing a 0 of 10, which is what the rule is for. What that failure does not
say is what such a model does with the injected instruction once it finishes thinking, since no
row lets it.

**Why it was left.** The row's job tonight was to stop a void from reading as resistance, and it
does. Raising the cap changes the request every published text row was measured under, so a row
drawn under a larger one would be a new row rather than a replicate, and the image arm's own
experience with no cap was a cortex alt that spent past 1600 tokens thinking per vision turn.

**What would close it.** A cap that is a property of the row rather than of the arm: the tier's
own budget where a tier has one, or none, as the image arm sends, for a row that is meant to draw a
thinking model to its answer. Then draw the deep candidates under it and publish what the
thought-through reply did with the instruction, which is the one text number the corpus has never
drawn on a model that deliberated past 1600 tokens.

## Trail

- 2026-09-05: opened by the close of
  [R-560](560-the-text-arm-scores-an-empty-or-capped-reply-as-resistance.md), whose void-row
  addendum at ADR-0005 records the cap as the harness's own and the failure as the row's reading.

- 2026-09-09: claims held to the code, and the row this entry named as its case does not void. It
  said a Qwen entry under `budget-alone` deliberates to the text arm's cap on every draw, which is
  the lever addendum's prediction, taken from the budget-alone addendum's 40 of 40 at the delegated
  run's own `GenerationBounds(max_tokens=1024)` over a different prompt. The void-row addendum that
  opened this entry had already corrected that prediction the same night: drawn at the text arm's
  1600, Qwen3.5-2B under `budget-alone` answered on 20 of 20 and read 2 of 10 framed, and its own
  table records that row passing. So the entry restated a disproved prediction as its case. The
  body and the trigger are rewritten around the two deep candidates, which is the case that stands,
  and the two comments in the harness carrying the same prediction, on the text row and in
  `assert_drawn`, are corrected with it. The rest holds: the arm still posts `max_tokens: 1600`,
  the shipped path still posts none, and the brain-tier row's longest completion is still the 773
  tokens the runbook and the ADR-0013 re-drawn rows record.
