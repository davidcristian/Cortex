# The token cap's derivation is written against a shape the default stack does not run

**Status:** satisfied 2026-08-28
**Area:** subagents
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)

`DEFAULT_SUBAGENT_MAX_TOKENS` is 1024, about five times a 199-token reply measured on the
unconstrained (tools-enabled) shape. A subagents-only stack runs the constrained shape, which cost
1.01 to at least 2.36 times the tokens for the same subtask over the same three report bodies and
reached the cap on one narrow summarization in three. So the sentence under the number, that
reaching the cap shows a model talking rather than working, did not describe the shape the default
stack runs.

The cap was not the defect. The extra tokens went to a reasoning trace that the constrained request
re-enabled, which is [R-456](456-a-constrained-request-loses-the-thinking-switch.md).

This entry was recorded to wait for that one to close, at which point the constrained shape would be
measured again through `brain/packages/orchestrator/tests/test_envelope_cost_live.py` and the cap
either recomputed from a reply with no trace in it or confirmed where it stood.

## History

- 2026-08-26: opened by the close of
  [R-431](431-the-token-cap-fires-on-the-shape-that-ships.md), which measured the gap between the
  shape the cap was derived on and the shape the compose override ships.
- 2026-08-26: the reasoning trace was turned off with `--reasoning-budget 0` on every subagent
  server, so the blocking premise no longer applied. Re-measured at the shipped cap over the same
  three bodies, constrained: 63 to 89 decoded tokens, all three finished, 223 to 395 characters,
  against the 550 to at least 1024 this entry was written over. A new cap could not be computed
  from those replies, because all three narrated the task instead of answering it.
- 2026-08-28: satisfied. [R-459](459-what-the-envelope-costs-the-answer.md) drew forty runs of the
  shipped tool-less shape, ten of them real answers at 256 to 429 decoded tokens, plus thirty nine
  under an instruction that recovers the answer, 38 of those between 248 and 323. Five times the
  longest answer is 2145 and five times the instructed longest is 4560, above the 4096 tokens a
  slot gets, so the rule that produced 1024 no longer produces a usable number. What replaces it is
  a confirmation: 1024 is above every answer this tier has been measured writing on the shape that
  ships, and every run in two hundred that reached the cap reached it on narration or on a
  reasoning trace. The second question, which of the two limits binds, depends on the host: at this
  tier's measured 0.18 to 1.35 tok/s the 2400 s deadline admits about 425 decoded tokens on a busy
  host and about 3200 on an idle one, against a slot context of about 3820 after a 261 to 282 token
  prompt. The deadline binds first everywhere on the measured range, and on a busy host it falls
  below the cap. Written into ADR-0048. Opened by it:
  [R-477](477-the-caps-margin-over-an-answering-run.md) and
  [R-478](478-two-ceilings-on-one-run-and-no-ordering.md).
