# The token cap fired on a narrow subtask running the shape this repo ships by default

**Status:** landed 2026-08-26
**Area:** subagents
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-25 by the close of [R-207](207-whole-subtask-figure-off.md), whose batch was
measured unconstrained and whose one constrained control run then behaved differently.

`CORTEX_SUBAGENTS_MAX_TOKENS` is 1024, five times the longest reply a narrow subtask was measured
writing, and its derivation is that reaching it is itself the evidence: "a reply five times the
longest one this tier has been measured writing is a model that is talking rather than working".
A subagents-only stack hands its subagents no dispatcher, so `constrain_output` is on and every
reply is decoded into the fixed `{"reply": ...}` envelope (ADR-0028). That is the shape the compose
override ships.

Run once on that shape, through the real runner against the live CPU entry, a summarization subtask
of exactly the kind the batch measured decoded **1024 tokens**, hit the cap, and came back to the
cortex as `FAILED: the subtask stopped at a token limit ... treat the subtask as unanswered`. The
same subtask unconstrained decodes about 300 tokens in 222.8 to 324.3 s; this one spent **740.4 s**
to produce a refusal. The grammar itself is not the cost, the run decoding at 1.41 tok/s against the
batch's 1.26 to 1.35; what changed is how much the model wrote inside the envelope.

**Why it was left.** It is one sample, and one sample distinguishes nothing between three
explanations: the envelope inviting a longer answer, this particular report body, and ordinary
sampling variance on a 4B model. Acting on it would mean retuning a cap on a single reading, which
is what the entry this closes exists to warn against.

**What would close it.** Run the constrained and unconstrained shapes over the same several report
bodies and compare decoded lengths, which is a short measurement now that the harness exists. Then
pick between the honest answers. If the envelope really does multiply the reply, the cap wants
deriving from the constrained shape rather than from the raw one, since that is the shape the
default stack runs; if it does not, the sample was variance and the record should say so. Worth
checking in the same run: whether a reply cut mid-envelope is reported as the cap rather than as a
malformed envelope, which the attempt's arm ordering says it should be and which this run did
exercise.

## Trail

- 2026-08-25: opened by the close of [R-207](207-whole-subtask-figure-off.md), whose control for
  the constrained shape hit the token cap on a subtask the unconstrained shape answers in a third
  of the time.
- 2026-08-26: Landed. Both shapes were run over the same three report bodies, serialized through
  the real runner against the live CPU entry, and the effect is the envelope's rather than the
  body's or the draw's: paired, the envelope costs **1.01 to at least 2.36 times** the raw shape's
  decoded tokens, 550 to at least 1024 against 366 to 544, never less, and one of the three reached
  the cap and came back refused. It is not the envelope inviting a longer answer, which is what
  this entry assumed: the envelope's replies are **shorter**, 158 and 1176 characters against 1559
  and 2211 raw. The tokens go to a **reasoning trace**, and that is the finding. A probe at a cap
  of 200 decoded 200 tokens of which none were reply text and 763 characters were reasoning, so the
  tier's `--chat-template-kwargs '{"enable_thinking": false}'` stops taking effect once a request
  carries a `response_format`, and a delegated run drops every reasoning delta unread. The cap is
  therefore not what is wrong and does not move here; the retune is filed with the fix as
  [R-456](456-a-constrained-request-loses-the-thinking-lever.md) and
  [R-457](457-the-caps-derivation-on-the-shape-that-ships.md). Recorded in the ADR-0005 envelope
  addendum with the paired table and the interval `scripts/contrast.py` reads off it; the runbook
  now tells an operator that a cap refusal on ordinary narrow work is this. The second question
  this entry asked is answered yes, live: the cut landed mid-envelope and was reported as the cap,
  `AttemptFailure.TRUNCATED` naming the deployment's own 1024, never as a malformed envelope. Two
  things came with it. The measurement is now a committed harness rather than a scratchpad,
  `brain/packages/orchestrator/tests/test_envelope_cost_live.py`, which is what this entry could
  not assume the last one had left behind. And the cap turned out to be the only one of the four
  bounds around a delegated run that the constant scan did not hold to the runbook and the module
  contract quoting it, which is now closed, so the retune those two entries carry is one a gate
  will hold.
