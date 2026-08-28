# A reply that is a plan still arrives as an answer, and nothing says so

**Status:** open, fix when it bites
**Area:** subagents
**Trigger:** a delegated reply that is a plan is seen reaching a cortex turn and shaping it, which
is what would make this cost something rather than merely be true; or a roster pick is measured
whose constrained non-deliveries come back `ok=True` more often than they come back refused, which
is the reading that says the quiet failures are common again on that pick. That second half was
first written as an answer rate and is now written as a failure kind, because the rate turned out
not to predict the thing it stood for: see the Trail.
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

Opened 2026-08-28 by the close of
[R-476](476-the-envelopes-answer-rate-is-an-instruction.md), which decided against detecting this
and recorded the argument rather than the mechanism.

A constrained subagent whose `reply` holds a plan instead of an answer is an `ok=True`
`SubagentResult`, and the cortex is handed a sentence about summarizing as though it were a summary.
That was three draws in four before the shipped sentence existed and is about one in twenty after
it, which is the whole of what changed: the failure got rarer and stayed quiet. It is the quietest
failure this path has, because every other one arrives as a refusal the cortex can read.

**Why it was left.** The decision is written out in full in the
[ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md) instruction addendum and it is a
decision rather than a deferral: nothing in the core can tell a plan from an answer without judging
prose. A keyword detector misfires on an answer whose subject happens to be a request, and a false
positive is strictly worse than the quiet pass, since it destroys an answer the cortex had and
converts a rare silent degradation into a refusal of good work. A structural detector cannot exist,
for the reason the ADR-0005 answer addendum established: the hazard is specific to a field whose
value is prose, and prose offers no grammatical position that separates a plan from a summary. So
the only honest judge is another completion.

**What would close it.** Either the trigger fires and the judge gets designed, or a reading closes
it the other way. The judge, if it is ever built, is a second completion on the same tier asked one
closed question about the reply it just wrote, which is a `SubagentRunner` change behind an
unchanged port and is not free: it doubles a delegated run's completions and asks the model that
narrated to notice that it narrated, which is the assumption worth testing first and cheaply, on
the replies the harness has already captured. The other close is a measurement: the number-recall
proxy the answer measurements are judged by separates the two populations cleanly on a
summarization, and if some cheap in-core signal separated them as well on every shape this tier is
asked for, this stops needing a model at all. The reason to doubt that is in the same reading:
the proxy is instruction-specific, and it is the *instruction's* checkable meaning that makes it
work, not anything about the reply.

## Trail

- 2026-08-28: opened by the close of
  [R-476](476-the-envelopes-answer-rate-is-an-instruction.md), which decided against detecting this
  and recorded the argument rather than the mechanism.
- 2026-08-28: **the trigger's proxy is wrong, and it is rewritten above rather than fired.**
  [R-481](481-the-sentence-is-measured-on-one-pick.md) measured the Qwen roster alternate at 288
  runs and it lands within seven draws of the default pick's constrained answer rate, 83 of 96
  against 90, so the trigger as written would not have gone off. But its failures are quiet where
  the default pick's are loud: **8 of its 13 constrained non-deliveries come back `ok=True`**,
  against none of the default pick's 6. So the answer rate does not predict the quiet failures it
  was made to stand for, and the trigger now names the failure kind directly. On that pick the
  quiet pass is the ordinary failure and not a rarity, which is closer to firing this entry than
  anything measured before it, and the argument for leaving it undetected is unchanged, being about
  what a detector over prose can do rather than about a rate.
