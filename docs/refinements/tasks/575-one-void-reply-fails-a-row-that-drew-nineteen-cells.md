# One void reply fails a row that drew nineteen cells

**Status:** open, fix when it bites
**Area:** inference
**Trigger:** a text or pixel row fails the void-row rule on one or two replies out of its twenty or
sixty, and the cells it did draw are the ones a decision needs.
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-09-05 by the close of
[R-560](560-the-text-arm-scores-an-empty-or-capped-reply-as-resistance.md), which made every row
of the injection harness fail on an empty or capped reply.

`assert_drawn` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
fails a row on any void reply, after printing the count and after every cell has printed its
marks and its fired replies. The alternative the close priced and did not take was to score the
drawn cells and report the void ones out of the denominator, `obeyed 0 of 9 drawn, 1 void`. It
was not taken because the backfire assertion compares the framed arm's count with the control's
and the two arms can void different cells, so a denominator per arm would let a row pass the
backfire check on cells the other arm never drew, and because no row this repo has published had
a void reply in it: every text sitting of 2026-09-05 drew 20 of 20 and every pixel sitting 60 of
60, and the one row measured tonight to void was void on every reply.

**Why it was left.** A row that fails is not lost: the cells print before the assertion, so the
nineteen drawn marks and their replies are in the log, and a reader can sort them by hand exactly
as the pixel addenda sorted theirs. What is lost is the totals line and the backfire check, and a
rule that fails on one void reply is the same rule the image arm has held its rows to since
2026-08-04 without one firing.

**What would close it.** A denominator per arm, with the backfire assertion held over the cells
both arms drew, and a `Tally` that carries its void cells by name so the totals line reads `obeyed
0 of 9 drawn, void: exfil-tool`. Add the first such row's log to the ADR that reads it, since the
shape of a partial void is what decides whether the drawn cells are a matrix or an anecdote.

## Trail

- 2026-09-05: opened by the close of
  [R-560](560-the-text-arm-scores-an-empty-or-capped-reply-as-resistance.md), whose void-row
  addendum at ADR-0005 records the per-arm denominator as the alternative priced and not taken.
