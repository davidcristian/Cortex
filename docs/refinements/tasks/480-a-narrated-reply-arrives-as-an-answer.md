# A reply that is a plan still arrives as an answer, and nothing says so

**Status:** declined 2026-09-11
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

A constrained subagent whose `reply` contains a plan instead of an answer is an `ok=True`
`SubagentResult`, and the cortex is handed a sentence about summarizing as though it were a summary.
That was three draws in four before the shipped sentence existed and is about one in twenty after
it. It is the quietest failure this path has, because every other one arrives as a refusal the
cortex can read.

Nothing in the core can tell a plan from an answer without judging prose. A keyword detector
misfires on an answer whose subject happens to be a request, and a false positive is worse than the
quiet pass, since it destroys an answer the cortex had. So the only accurate judge is another
completion.

## The bar, written 2026-09-11 before the judge ran

The judge is the tier that wrote the reply, on the same image and flags, handed the run's own
prompt with its reply as the assistant turn and asked one closed question, its answer limited to
`yes` or `no` by a schema. It is scored over one pick's constrained runs in the re-table samples,
each run classified first by the corrected machine judge and read by eye. On the pick it would
protect it must do all of these:

1. Catch at least 80% of the quiet non-deliveries, the runs that came back `ok=True` and are not an
   answer, by answering `no`. On Qwen3.5-2B that is at least 26 of its 32.
2. Call at most one delivered answer in fifty a non-answer. On Qwen3.5-2B that is at most 1 of its
   59, since 59 is short of the 100 that would allow a second.
3. Catch at least 80% of the quiet non-deliveries that are not copies, on its own. A copy of the
   report has a detector that costs no completion, a comparison against the context the runner
   already has. On Qwen3.5-2B that is 4 of its 5.

A judge completion that does not parse, or is cut at the cap, is scored as `yes`, since a runner
whose judge did not answer can only pass the reply on as it stood. The two halves are priced by what
each error costs the cortex: a missed quiet failure leaves the cortex where it is today, while a
false call turns an answer into a refusal. One in fifty is read as a count on the sample, not as an
interval: the upper Wilson bound of 0 of 59 is 0.06, so an interval bar at 0.02 could not be
cleared by any sample in these directories.

## History

- 2026-08-28: opened by the close of
  [R-476](476-the-envelopes-answer-rate-is-an-instruction.md), which decided against detecting this
  and recorded the argument rather than the mechanism.
- 2026-08-28: the trigger's measure was wrong and was rewritten rather than fired.
  [R-481](481-the-sentence-is-measured-on-one-pick.md) measured the Qwen roster alternate at 288
  runs and it comes within seven draws of the default pick's constrained answer rate, 83 of 96
  against 90, so the trigger as written would not have gone off. But its failures go unreported
  where the default pick's are refusals: 8 of its 13 constrained non-deliveries come back `ok=True`,
  against none of the default pick's 6. So the answer rate does not predict the quiet failures it
  was made to stand for, and the trigger now names the failure kind directly.
- 2026-09-02: the close of
  [R-511](511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md) measured a flag combination
  on which this failure is the ordinary one. `--reasoning-budget 0` without the kwarg, on the E4B
  pick, lost 11 of 40 seed-paired constrained draws with no reasoning character: 9 arrived `ok=True`
  as a narration or a plan and 2 were a thinking process written into `reply` and cut at the cap,
  against 0 of 40 on the shipped pair. That combination does not ship, so the trigger has not fired.
- 2026-09-11: the trigger's second half had fired on the day it was written, and the entry was
  re-filed as actionable. It named a roster pick whose constrained non-deliveries come back
  `ok=True` more often than refused, and the roster alternate stood at 8 of 13 against 5 refused.
  Two later readings say the same of the smallest pick: the five-pick envelope review's 26 of 30 on
  2026-08-28, and the reader-column review of the smallest pick's 288 seeded runs on the current
  image on 2026-09-11, where the constrained runs stood 83 of 96 and delivered 53. On the default
  pick the count is still 0 of 6. The two quiet kinds that review filed on their own are
  [R-634](634-the-body-handed-back-passes-both-rates.md) and
  [R-635](635-the-lookup-judge-passes-an-invented-instance-beside-the-bodys-phrase.md).
- 2026-09-11: the default pick's quiet count is no longer 0 on the current image, and the kind that
  moved it is not this entry's. The five-pick re-table of 2026-09-11 drew the default pick seeded on
  `sha256:952424b09abc`: its constrained runs have 19 non-deliveries in 96, 14 of them `ok=True`,
  and all 14 are the report body handed back on the summarization shape, 12 of them identical to it
  in letters and digits. None is a plan or a narration, so this entry's own kind still reads 0 on
  the default pick. Filed as
  [R-641](641-the-shipped-sentence-hands-the-report-back-on-a-summarization.md).
- 2026-09-11: declined on the measurement
  ([ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md) decision 9). Each pick's server
  was started on the re-table's image, argv and caps, and the tier was handed its own prompt with
  its reply as the assistant turn and asked the question the reply-envelope readings quote, seeded,
  over every accepted run of its constrained set. No pick clears both the first and the second line,
  and every pick fails the second; the 0.8B clears the first only by answering `no` to 41 of its 42
  answers as well. On Qwen3.5-2B the judge answers `no` to 13 of its 32 quiet non-deliveries and to
  40 of its 59 delivered answers; the lowest false-call count on any pick is the default's 16 of 77,
  against a limit of one in fifty. A second wording without the copy clause fails on every pick too.
  The entry's premise about the roster alternate was also wrong: none of its 32 quiet failures is a
  plan or a narration, and 27 are the report handed back, which
  [R-641](641-the-shipped-sentence-hands-the-report-back-on-a-summarization.md) covers. No judge is
  built. Samples are under `measurements/self-judge-2026-09-11/`, which git ignores.
