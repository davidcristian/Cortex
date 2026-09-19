# The widest trail line comes from the least sampled cohort

**Status:** open, waiting for its trigger
**Area:** cross-cutting
**Trigger:** a change to `turn_context.DEFAULT_RECALL_K` or to `ranking.DROPPED_TRAIL_LIMIT`,
either of which moves the widest line into a shape this run barely produced. Both are module
constants and neither is read from the environment, so the change is a diff in this tree and not a
deployment's setting: `grep -rn "DEFAULT_RECALL_K\|DROPPED_TRAIL_LIMIT" brain/packages/*/src`
reports every place either is written.
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)
**Verified:** 2026-09-19

The recall trail line is widest when the rank keeps notes, because a kept hit costs about 100
rendered characters against a dropped candidate's 73, and the two lists are complementary. So the
widest line of the 466 measured, at 1,800 characters, is one of only 9 lines where the judge kept
three notes, while the field's own maximum came from a cohort of 72. The shipped `k` is five and no
line in the run kept four or five, so the widest shape the deployment allows was never written.

The arithmetic covers it: at the measured per-entry costs, five kept hits and fifteen dropped
candidates come to roughly 2,200 characters, an eighth of the 16,383 the log driver ends a message
at. This is filed rather than fixed because it is an unsampled corner of a distribution whose whole
range sits an order of magnitude under the number anybody cares about. Closing it needs a corpus in
which the judge keeps the whole of `k`, run through the same harness. The cheaper half is for the
report to name the cohorts it never saw.

## History

- 2026-08-27: opened by the close of
  [R-453](453-the-harness-reads-one-field-off-a-line-it-has-whole.md), whose cohort table runs
  backwards, the widest field appearing on the narrowest line.
- 2026-09-09: reviewed, and the trigger re-aimed at what could fire it. `DEFAULT_RECALL_K` is 5 and
  `DROPPED_TRAIL_LIMIT` is 20, both unchanged. The old trigger said a deployment raises `k`, and no
  deployment can: neither constant has an env variable, and `k` reaches the recall from one call
  site. So the trigger now fires on a commit here.
- 2026-09-14: reviewed. `DEFAULT_RECALL_K` is 5 (`turn_context.py:39`), reaching a recall from the
  one call site at `turn_context.py:216`, and `DROPPED_TRAIL_LIMIT` is 20 (`ranking.py:111`). The
  bound is slack at the shipped shape and the comment on it now says so: the pool is twenty and five
  are recalled at a pool factor of four, so a rank keeping the whole of `k` drops fifteen. A review
  on 2026-09-08 rendered one trail record at its shipped caps and measured it, 2,264 characters
  plain then 2,258 four days later, which is the near-2,200 this entry computed. That record was
  built with five hits and twenty dropped candidates, wider than the shipped pool can produce, and
  it was constructed rather than drawn from a judged run, so a real corpus in which the judge keeps
  all five is still unmeasured. The cheaper half would go in `scripts/trailwidth.py`, where
  `by_entries` groups only the readings a capture held and `report` walks `sorted(grouped)`, so an
  empty cohort is absent rather than named.
- 2026-09-15: reviewed, and the cheaper half is a bigger change than that description implied. Both
  constants stand. The unsampled cohorts do not sit between the dropped counts a run produced, they
  sit below the lowest, because kept and dropped are complementary, so a rule naming the gaps
  between observed counts would name none of them. To name them the reader has to know how low the
  count can go, which is `pool - k`, and both numbers are on the line, so the cheaper half is two
  more fields read off each trail line and kept on `Reading`. `scripts/trailwidth.py` is at 296 of
  the 300 lines the cap allows, so it also means splitting the module and registering the new one in
  the two lists that name every module in `scripts/`. Separately,
  `brain/packages/orchestrator/tests/test_widest_line.py` now builds the widest line from five hits
  and twenty drops and asserts it against the log driver's limit (ADR-0051 decision 15): 4,464
  characters with a maximum-length session id and 2,402 with an ordinary one. That is the arithmetic
  turned into a test, not the drawn reading this entry asks for.
- 2026-09-19: reviewed, and nothing moved. The trigger's grep returns the same five places:
  `DEFAULT_RECALL_K` is 5 at `turn_context.py:39` and used once at `turn_context.py:216`,
  `DROPPED_TRAIL_LIMIT` is 20 at `ranking.py:111`, used as the default at `ranking.py:152` and
  re-exported by `_surface/memory.py`. No commit has touched `ranking.py` or `turn_context.py` since
  2026-09-15. `scripts/trailwidth.py` is still 296 lines, and none of the four measurement
  directories written since then contains a recall trail line.
