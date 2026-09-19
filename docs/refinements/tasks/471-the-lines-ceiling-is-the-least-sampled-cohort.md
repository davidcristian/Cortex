# The line's ceiling is the least sampled cohort

**Status:** open, fix when it bites
**Area:** cross-cutting
**Trigger:** a change to `turn_context.DEFAULT_RECALL_K` or to `ranking.DROPPED_TRAIL_LIMIT`,
either of which moves the widest line into a shape this run barely produced. Both are module
constants and neither is read from the environment, so the change is a diff in this tree and not a
deployment's setting: `grep -rn "DEFAULT_RECALL_K\|DROPPED_TRAIL_LIMIT" brain/packages/*/src`
reports every place either is spelled.
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-09-19

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
- 2026-09-15: swept, and the cheaper half is a bigger change than its last description implied.
  Both constants stand: `DEFAULT_RECALL_K` is 5 (`turn_context.py:39`), reaching a recall from the
  one call site at `turn_context.py:216`, and `DROPPED_TRAIL_LIMIT` is 20 (`ranking.py:111`).

  What the last reading left out is which cohorts are missing. The unsampled ones do not sit
  between the dropped counts a run produced, they sit **below** the lowest: kept and dropped are
  complementary, so a rank keeping all five of `k` writes the fewest drops and the widest line, and
  the cohorts this entry is about are the low-drop end. A rule naming the gaps between the counts a
  capture held would therefore name none of them. To name them the reader has to know how low the
  count can go, which is `pool - k`, and both numbers are on the line, under `pool` and `k`. So the
  cheaper half is a second and third field read off each trail line and carried on `Reading`, not a
  loop over `sorted(grouped)`. `scripts/trailwidth.py` is at 296 lines of the 300 the cap allows,
  so it also means splitting the module and registering the new one in the two rosters that name
  every module in `scripts/`. That is a slice rather than an afternoon's tidy, and it is why this
  entry is still open after a slot that had the file open.

  The estimate it asks about did gain a gated upper bound today.
  `brain/packages/orchestrator/tests/test_widest_line.py` builds the trail's widest line from five
  hits and twenty drops, wider than the shipped pool can produce, and asserts it against the log
  driver's cliff (ADR-0038 widest-line addendum): 4,464 characters with a bound-length session id
  on it and 2,402 with an ordinary one. That is the arithmetic turned into a check rather than the
  drawn reading this entry asks for, and it moves nothing about the ask: what is still unmeasured
  is a judged run in which the rank keeps the whole of `k`.
- 2026-09-19: swept, and nothing moved. The trigger's grep returns the same five places:
  `DEFAULT_RECALL_K` is 5 at `turn_context.py:39` and spent once at `turn_context.py:216`,
  `DROPPED_TRAIL_LIMIT` is 20 at `ranking.py:111`, spent as the default at `ranking.py:152` and
  re-exported by `_surface/memory.py`. No commit has touched `ranking.py` or `turn_context.py`
  since 2026-09-15, so the trigger has not fired. `scripts/trailwidth.py` is still 296 lines, so
  the cheaper half still means the split the last bullet describes. None of the four measurement
  directories written since then holds a recall trail line, so the drawn reading is still missing.
