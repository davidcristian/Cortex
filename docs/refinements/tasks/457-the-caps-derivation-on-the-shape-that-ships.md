# The token cap's derivation is written against a shape the default stack does not run

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-26 by the close of
[R-431](431-the-token-cap-fires-on-the-shape-that-ships.md), which measured the gap between the
shape the cap was derived on and the shape the compose override ships.

`DEFAULT_SUBAGENT_MAX_TOKENS` is 1024, derived as roughly five times a 199-token reply measured on
the **unconstrained** shape, which is the tools-enabled one. A subagents-only stack runs the
constrained shape, and paired over the same three report bodies that shape costs 1.01 to at least
2.36 times the tokens for the same subtask, reaching the cap on one narrow summarization in three.
So the sentence under the number, that reaching the cap is itself evidence of a model talking rather
than working, is not true of the shape the default stack runs.

**Why it was left.** The cap is not the defect. The tokens go to a reasoning trace the constrained
request re-enables, which is [R-456](456-a-constrained-request-loses-the-thinking-lever.md), and
retuning a bound around a defect rather than fixing the defect is the wrong repair. The number that
would replace it also cannot be measured while the reasoning is running: the longest envelope
reading is a lower bound of 1024 rather than a length, and five times even that lower bound is
5120, above the 4096 tokens a slot gets from this compose file's 8192 across `--parallel 2`, so the
rule that produced 1024 has no room left to produce anything on this shape. Retuning on an
extrapolated number is precisely what the entry behind this measurement exists to warn against.

**Trigger:** R-456 landing, at which point the constrained shape is re-measured through
`brain/packages/orchestrator/tests/test_envelope_cost_live.py` and the cap is either re-derived from
an uncensored envelope reply or confirmed where it stands. The honest expectation is that the fix
removes most of the gap and this entry closes as satisfied, but the derivation is still written
against a shape nothing ships, so it wants restating either way. The second thing the re-measurement
should settle is which of the two ceilings is the binding one: at the tier's measured 1.3 tok/s a
2400 s run deadline is about 3100 decoded tokens and a slot's context is 4096 less the prompt, so
any cap materially above 1024 lands between two bounds that were never compared.

## Trail

- 2026-08-26: opened by the close of
  [R-431](431-the-token-cap-fires-on-the-shape-that-ships.md), whose paired run showed the cap's
  derivation does not describe the shape the compose override ships.
- 2026-08-26: The trigger fired. [R-456](456-a-constrained-request-loses-the-thinking-lever.md)
  landed as a tier flag (`--reasoning-budget 0` beside the template kwarg on every subagent server),
  and this entry's blocking premise, that the replacement number "cannot be measured while the
  reasoning is running", no longer holds. Re-measured at the shipped cap over the same three report
  bodies, constrained, through the same harness: **63 to 89 decoded tokens, all three finished, 223
  to 395 characters**, against the 550 to at least 1024 this entry was written over. So the cap is
  not close to firing on this shape any more and the pressure is off; what remains is that its
  derivation still describes the unconstrained shape.
  **It does not close here, and the reason is new.** The rule that produced 1024 is five times the
  longest reply this tier has been measured writing, and the replies above are short because they
  are the wrong text: all three narrate the task instead of performing it, the model writing into
  `reply` what it used to write into `reasoning_content`
  ([R-459](459-what-the-envelope-costs-the-answer.md)). Five times 89 is 445, and re-deriving a cap
  down to that from a reply nobody would accept is the same mistake as retuning it up around a
  reasoning trace. So the re-derivation waits on a constrained reply that is actually an answer, and
  the second question this entry asks, which of the two ceilings binds, is unchanged and unanswered.
