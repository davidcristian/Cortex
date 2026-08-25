# The token cap fired on a narrow subtask running the shape this repo ships by default

**Status:** open, actionable
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
