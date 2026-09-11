# A reply that is a plan still arrives as an answer, and nothing says so

**Status:** declined 2026-09-11
**Area:** subagents
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

## The bar, written 2026-09-11 before the judge ran

The judge is the tier that wrote the reply, on the same image and flags, handed the run's own
prompt with its reply as the assistant turn and asked one closed question, its answer held to
`yes` or `no` by a schema. It is scored over one pick's constrained arm in the re-table samples,
each run classified first by the corrected machine judge and read by eye. On the pick it would
protect it must do both of these:

1. **Catch at least 80% of the quiet non-deliveries**, the runs that came back `ok=True` and are
   not an answer, by answering `no`. On Qwen3.5-2B that is at least 26 of its 32.
2. **Call at most one delivered answer in fifty a non-answer.** On Qwen3.5-2B that is at most 1 of
   its 59, since 59 is short of the 100 that would allow a second.
3. **Catch at least 80% of the quiet non-deliveries that are not copies**, on its own. A copy of
   the report has a detector that costs no completion, a comparison against the context the runner
   already holds, so a judge that clears the first line only by catching copies is paying a second
   completion on every run for what a string comparison does free. On Qwen3.5-2B that is 4 of its 5.

A judge completion that does not parse, or is cut at the cap, is scored as `yes`, since a runner
whose judge did not answer can only pass the reply on as it stood.

**Why these numbers.** The two halves are priced by what each error costs the cortex. A missed
quiet failure leaves the cortex where it is today, holding a non-answer it believes, which is the
state this entry exists to reduce and not a new harm. A false call is a new harm: it turns an
answer the cortex had into a refusal, so the judge would destroy work to report it. The first half
is therefore a floor on usefulness and the second a ceiling on damage, and the ceiling is the strict
one. One in fifty is read as a count on the sample, not as an interval: the upper Wilson bound of
0 of 59 is 0.06, so an interval bar at 0.02 is one no sample in these directories could clear, and
a bar that cannot be passed decides nothing. A pick whose judge makes two false calls on 59 has
made them at 3.4%, which already fails the count.

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
- 2026-09-11: **the default pick's quiet count is no longer 0 on the current image, and the kind
  that moved it is not this entry's.** The re-table addendum at the origin drew the default pick
  seeded on `sha256:952424b09abc` and read it under the corrected rules: its constrained arm has 19
  non-deliveries in 96, 14 of them `ok=True`, and all 14 are the report body handed back on the
  summarization shape, 12 of them identical to it in letters and digits. None is a plan or a
  narration, so this entry's own kind still reads 0 on the default pick. The sentence above that
  rests on "0 of 6" therefore holds for plans and does not hold for quiet failures as a whole, and
  a copy, unlike a plan, is a string comparison against the context the runner already holds.
  Filed as [R-641](641-the-shipped-sentence-hands-the-report-back-on-a-summarization.md), which
  says where the two disagree.
- 2026-09-11: **declined on the measurement**
  ([ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md) self-judge addendum of this
  date). The bar above was written before the first judge request. Each pick's server was started
  on the re-table's image, argv and caps, and the tier was handed its own prompt with its reply as
  the assistant turn and asked the question the addendum quotes, seeded, over every accepted run of
  its constrained arm. No pick clears either the first or the second line. On Qwen3.5-2B the judge
  answers `no` to 13 of its 32 quiet non-deliveries and to 40 of its 59 delivered answers; the
  lowest false-call count on any pick is the default's 16 of 77, against a ceiling of one in fifty.
  On the three Qwen picks the judge says `no` to answers as often as to non-answers. A second
  wording without the copy clause, run after the first was read, fails on every pick too. The
  entry's premise about the roster alternate was also wrong: none of its 32 quiet failures is a
  plan or a narration, and 27 are the report handed back, which
  [R-641](641-the-shipped-sentence-hands-the-report-back-on-a-summarization.md) holds. No judge is
  built. Samples are under `measurements/self-judge-2026-09-11/`, which git ignores.
