# The leak's denominator is 53 in the runbook and 58 in the three other places that publish it

**Status:** done 2026-09-08
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)

One session of 2026-08-29 produced the only leak this repo has seen, the well formed envelope whose
whole answer is the channel name. Four places publish what it was one of, and they did not agree.
The request-setting table said `0 of 58 deliberated` for that cell,
[495](495-the-forced-thought-can-leak-its-own-start-tag.md) says `1 of 58 draws`, the probe's own
docstring (`brain/packages/inference/tests/test_trace_budget_live.py`) says `1 of 58`, and
[docs/runbooks/llamacpp-gpu.md](../../runbooks/llamacpp-gpu.md) said `One draw in 53`. Three against
one is not evidence about which is right, and the runbook is what an operator reads before running
the probe.

Settled by the session's own draws on 2026-09-08, read back out of that session's recorded output,
which is kept outside this repository: the budgeted cell was drawn through the committed probe three
times, 5 draws, then 20, then 5 again, and the leak is the fifth draw of the second run, a
24-character reply of `{"reply": "thought"}` with no trace. Those 30 draws and the 28 drawn earlier
through the raw wire are the 58. The documents were written while the session's running total stood
at 53, the third run took it to 58, and the pass that followed searched for the string `of 53`,
which the runbook's `One draw in 53` does not contain. So one sentence kept the earlier total and
four took the later one. The fourth place was never in disagreement: the request-setting table's
`0/58` is a different numerator over the same 58 draws.

## History

- 2026-09-07: opened by the trigger review of the trace budget
  ([ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)), which drew the budgeted cell
  again at a hundred draws on each of two builds, saw no leak in 600 draws, and quoted the 58 in
  reporting the rate.
- 2026-09-08: done. The runbook now reads 58 and states the set that denominator is over, every draw
  of the measuring session made with `reasoning_budget_tokens: 0`, 28 through the raw wire and 30
  through the probe the paragraph tells an operator to run. What was read, run by run, is in
  [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md).
