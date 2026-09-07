# The leak's denominator is 53 in the runbook and 58 in the three other places that publish it

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-09-07 by the trigger sweep over the four entries deferred at that ADR, which re-drew
the leak at a hundred draws a cell and had to quote the original denominator to compare against.

One session of 2026-08-29 produced the only leak this repo has ever seen, the well formed envelope
whose whole answer is the channel name. Four places publish what it was one of, and they do not
agree. The request-lever addendum's capability table says `0 of 58 deliberated` for that cell,
[docs/refinements/tasks/495-the-forced-thought-can-leak-its-own-start-tag.md](495-the-forced-thought-can-leak-its-own-start-tag.md)
says `1 of 58 draws`, the probe's own docstring
(`brain/packages/inference/tests/test_trace_budget_live.py`) says `1 of 58`, and
[docs/runbooks/llamacpp-gpu.md](../../runbooks/llamacpp-gpu.md) says `One draw in 53`.

Three against one is not evidence about which is right, which is why this is filed rather than
edited. The runbook's sentence may be counting a narrower set than the addendum's cell, that
session having drawn the same request against the raw wire and through the shipped adapter, and a
number reduced to a majority vote is a number nobody measured. What settles it is the session's own
log, or a re-derivation of the counts from whatever of that run survives.

The cost of leaving it is small and real: the runbook is what an operator reads before running the
probe, and the rate it quotes is the one they compare their own printed count against. A rate
published at two denominators is a rate published at neither.

**What would close it.** Read the 2026-08-29 session's draws back out, decide which set each
sentence is counting, and make the four agree, spelling out in the runbook which set its own
denominator is over if it turns out to be the narrower one. Failing that, drop the denominator from
the runbook and let it point at the addendum's table, which is the one place that says what its
cell was.

## Trail

- 2026-09-07: opened by the trigger sweep recorded in the
  [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) trigger-sweep addendum, which re-drew the
  budgeted cell at a hundred draws on each of two builds, saw no leak in 600 draws, and quoted the
  58 in reporting the standing rate.
