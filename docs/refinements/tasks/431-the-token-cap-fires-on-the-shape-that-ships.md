# The token cap was reached by a narrow subtask running the configuration this repo ships

**Status:** done 2026-08-26
**Area:** subagents
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)

`CORTEX_SUBAGENTS_MAX_TOKENS` is 1024, five times the longest reply a narrow subtask was measured
writing, and its derivation is that reaching it is itself the evidence that the model is talking
rather than working. A subagents-only stack hands its subagents no dispatcher, so `constrain_output`
is on and every reply is decoded into the fixed `{"reply": ...}` envelope. That is the
configuration the compose override ships.

Run once on that configuration, through the real runner against the live CPU tier, a summarization
subtask of exactly the kind the batch measured decoded 1024 tokens, reached the cap, and came back
to the cortex as `FAILED: the subtask stopped at a token limit ... treat the subtask as
unanswered`. The same subtask unconstrained decodes about 300 tokens in 222.8 to 324.3 s; this one
spent 740.4 s to produce a refusal. The grammar itself is not the cost, the run decoding at
1.41 tok/s against the batch's 1.26 to 1.35; what changed is how much the model wrote inside the
envelope.

One sample distinguishes nothing between three explanations: the envelope inviting a longer answer,
this particular report body, and ordinary sampling variance on a 4B model.

## History

- 2026-08-25: opened by the close of [R-207](207-whole-subtask-figure-off.md), whose control for
  the constrained configuration reached the token cap on a subtask the unconstrained one answers in
  a third of the time.
- 2026-08-26: closed. Both configurations were run over the same three report bodies, serialized
  through the real runner against the live CPU tier, and the effect is the envelope's rather than
  the body's or the sample's: paired, the envelope costs 1.01 to at least 2.36 times the raw
  configuration's decoded tokens, 550 to at least 1024 against 366 to 544, never less, and one of
  the three reached the cap and came back refused. It is not the envelope inviting a longer answer,
  which is what this entry assumed: the envelope's replies are shorter, 158 and 1176 characters
  against 1559 and 2211 raw. The tokens go to a reasoning trace, and that is the finding. A probe
  at a cap of 200 decoded 200 tokens of which none were reply text and 763 characters were
  reasoning, so the tier's `--chat-template-kwargs '{"enable_thinking": false}'` stops taking
  effect once a request has a `response_format`, and a delegated run discards every reasoning delta
  unread. The cap is therefore not what is wrong and does not move here; the retune is filed with
  the fix as [R-456](456-a-constrained-request-loses-the-thinking-switch.md) and
  [R-457](457-the-caps-derivation-on-the-shape-that-ships.md). Recorded with the paired table and
  the interval `scripts/contrast.py` reads off it; the runbook now tells an operator that a cap
  refusal on ordinary narrow work is this. The second question this entry asked is answered yes,
  live: the cut happened mid-envelope and was reported as the cap,
  `AttemptFailure.TRUNCATED` naming the deployment's own 1024, never as a malformed envelope. Two
  things came with it. The measurement is now a committed harness rather than a scratch file,
  `brain/packages/orchestrator/tests/test_envelope_cost_live.py`. And the cap turned out to be the
  only one of the four bounds around a delegated run that the constant scan did not compare with
  the runbook and the module contract quoting it, which is now closed, so the retune those two
  entries describe is one a check will catch.
