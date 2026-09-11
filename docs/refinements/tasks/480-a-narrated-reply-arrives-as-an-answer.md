# A reply that is a plan still arrives as an answer, and nothing says so

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)
**Verified:** 2026-09-11

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
  against 90, so the trigger as written would not have gone off. But its failures go unreported where
  the default pick's are refusals: **8 of its 13 constrained non-deliveries come back `ok=True`**,
  against none of the default pick's 6. So the answer rate does not predict the quiet failures it
  was made to stand for, and the trigger now names the failure kind directly. On that pick the
  quiet pass is the ordinary failure and not a rarity, which is closer to firing this entry than
  anything measured before it, and the argument for leaving it undetected is unchanged, being about
  what a detector over prose can do rather than about a rate.
- 2026-09-02: the close of
  [R-511](511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md) measured a flag arm on
  which this failure is the ordinary one. `--reasoning-budget 0` without the kwarg, on the E4B pick,
  lost 11 of 40 seed-paired constrained draws with no reasoning character: 9 arrived `ok=True` as a
  narration or a plan and 2 were a thinking process written into `reply` and cut at the cap, against
  0 of 40 on the shipped pair. That arm does not ship and the pair stays, so the trigger has not
  fired; the reading says what the quiet failure looks like when a flag rather than a pick moves it.
- 2026-09-11: **the trigger's second half had fired on the day it was written, and the entry is
  re-filed as actionable** ([ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)
  re-filing addendum of this date). The trigger, until today, named a roster pick measured whose
  constrained non-deliveries come back `ok=True` more often than refused, and the bullet above
  reports the roster alternate at 8 of 13 against 5 refused, which is that condition, while reading
  it as short of firing. Two later readings on the origin record say the same of the smallest pick:
  the row addendum's 26 of 30 on 2026-08-28, and the sweep-columns addendum's 288 seeded runs on
  the current image on 2026-09-11, where the constrained arm stood 83 of 96 and delivered 53, so at
  least 30 of its 43 non-deliveries came back `ok=True` and at most 13 were refused. On the default
  pick the count is still 0 of 6, so what the firing changes is which picks a judge would pay for
  and not whether the default needs one. The recommended first step is the cheap one the body
  names: ask the tier that wrote each non-delivery whether it answered, over seeded samples the
  sweep can draw again by number, before any `SubagentRunner` change, and whether a delegated run
  should pay a second completion at all is the owner's call. The two quiet kinds the 2026-09-11
  sweep filed on their own, the body handed back and an invented lookup instance, are
  [R-634](634-the-body-handed-back-passes-both-rates.md) and
  [R-635](635-the-lookup-judge-passes-an-invented-instance-beside-the-bodys-phrase.md); this entry
  keeps the plan and the narration.
