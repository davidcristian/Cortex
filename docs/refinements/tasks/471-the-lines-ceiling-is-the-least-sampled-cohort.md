# The line's ceiling is the least sampled cohort

**Status:** open, fix when it bites
**Area:** cross-cutting
**Trigger:** a change to `turn_context.DEFAULT_RECALL_K` or to `ranking.DROPPED_TRAIL_LIMIT`,
either of which moves the widest line into a shape this run barely produced. Both are module
constants and neither is read from the environment, so the change is a diff in this tree and not a
deployment's setting: `grep -rn "DEFAULT_RECALL_K\|DROPPED_TRAIL_LIMIT" brain/packages/*/src`
reports every place either is spelled.
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-09-14

Opened 2026-08-27 by the close of
[R-453](453-the-harness-reads-one-field-off-a-line-it-has-whole.md), which measured the whole trail
line and found its maximum sitting in the rarest cohort of the run.

The recall trail line is widest when the rank **keeps** notes, because a kept hit costs about 100
rendered characters against a dropped candidate's 73, and the two lists are complementary. So the
widest line of the 466 measured, at 1,800 characters, is one of only 9 lines where the judge kept
three notes, while the field's own maximum came from a cohort of 72. The shipped `k` is five and no
line in the run kept four or five, so the widest shape the deployment admits was never written.

The arithmetic covers it: at the measured per-entry costs, five kept hits and fifteen dropped
candidates come to roughly 2,200 characters, an eighth of the 16,383 the log driver ends a message
at. That is why this is filed rather than fixed. It is an unsampled corner of a distribution whose
whole range sits an order of magnitude under the number anybody cares about.

**What would close it.** A corpus, or a question set, that makes the judge keep the whole of `k`,
run through the same harness, which would put a measured line under the arithmetic rather than
beside it. The cheaper half is to say so in the report: the harness has the candidates a line
named and could name the cohorts it never saw.

## Trail

- 2026-08-27: opened by the close of
  [R-453](453-the-harness-reads-one-field-off-a-line-it-has-whole.md), whose cohort table runs
  backwards, the widest field sitting on the narrowest line.
- 2026-09-09: swept, and the trigger re-aimed at what could actually fire it. Every measurement
  above still stands as a reading of the run it came from, and the two numbers it depends on are
  unchanged: `DEFAULT_RECALL_K` is 5 (`brain/packages/core/src/cortex_core/turn_context.py`) and
  `DROPPED_TRAIL_LIMIT` is 20 (`brain/packages/core/src/cortex_core/ranking.py`). What was wrong
  was the trigger's subject. It said a deployment raises `k`, and no deployment can: neither
  constant has an env variable, and `k` reaches the recall from one call site that passes
  `DEFAULT_RECALL_K` and nothing else. So the trigger fires on a commit here, which is a thing a
  reader of this file can watch for, rather than on a setting nobody can write.
- 2026-09-14: swept. The two constants and the trigger still stand: `DEFAULT_RECALL_K` is 5
  (`turn_context.py:39`), reaching a recall from the one call site at `turn_context.py:216`, and
  `DROPPED_TRAIL_LIMIT` is 20 (`ranking.py:111`). What the entry did not say is that the bound is
  slack at the shipped shape and the comment on it now does: the pool is twenty and five are
  recalled at a pool factor of four, so a rank keeping the whole of `k` drops fifteen and the
  twenty-candidate bound bites only where a deployment over-fetches wider than what ships.

  The arithmetic no longer stands alone. The trigger-sweep addendum of 2026-09-08 rendered one
  trail record at its shipped caps and measured it, 2,264 characters plain then 2,258 on the run
  four days later, and says in as many words that this is the near-2,200 this entry computed. So
  the unsampled corner has a measured width beside its estimate. It is not the reading this entry
  asks for: that record was built with five hits and **twenty** dropped candidates, which is wider
  than the shipped pool can produce, and it was constructed rather than drawn from a judged run, so
  what is still unmeasured is a real corpus in which the judge keeps all five.

  The cheaper half is still undone, and `scripts/trailwidth.py` is where it would go.
  `by_entries` groups only the readings a capture held and `report` walks `sorted(grouped)`, so a
  cohort with no lines is absent rather than named as empty. One thing to know before writing it:
  the harness groups by the candidates a line **dropped**, and this entry argues in kept notes, so
  a cohort named here is a dropped-count row there, the two numbers summing to the pool that run
  fetched rather than to the shipped twenty.
