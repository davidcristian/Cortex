# The leak's denominator is 53 in the runbook and 58 in the three other places that publish it

**Status:** landed 2026-09-08
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

**Settled by the session's own draws, and the runbook was stale rather than narrower.** Read back
out on 2026-09-08 from that session's recorded output, which is kept outside this repository: the
budgeted cell was drawn through the committed probe three times, 5 draws, then 20, then 5 again,
and the leak is the fifth draw of the second run, a 24-character reply of `{"reply": "thought"}`
with no trace. Those 30 draws and the 28 drawn earlier through the raw wire are the 58. The
documents were written while the session's running total stood at 53, the third run took it to 58,
and the sweep that followed searched for the string `of 53`, which the runbook's `One draw in 53`
does not contain. So one sentence kept the earlier total and four took the later one, and no set of
that session's draws comes to 53 once the third run has landed. The runbook now says 58 and names
the set it is over.

**The fourth place was never in disagreement.** The request-lever addendum's capability table cell
reads `0/58` deliberated, which is a different numerator over the same 58 draws as the leak's `1 of
58`, so the disagreement was only ever the runbook against the other three.

## Trail

- 2026-09-07: opened by the trigger sweep recorded in the
  [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) trigger-sweep addendum, which re-drew the
  budgeted cell at a hundred draws on each of two builds, saw no leak in 600 draws, and quoted the
  58 in reporting the standing rate.
- 2026-09-08: **landed.** The archaeology succeeded, so the entry's fallback was not taken. The
  runbook's sentence now reads 58 and states the set that denominator is over, every draw of the
  measuring session carrying `reasoning_budget_tokens: 0`, 28 through the raw wire and 30 through
  the probe the paragraph tells an operator to run. What was read, run by run, and why the sweep
  that corrected the count everywhere else did not reach the runbook: the
  [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) leak-denominator addendum.
