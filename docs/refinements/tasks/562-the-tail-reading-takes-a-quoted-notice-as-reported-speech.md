# The tail reading takes a quoted notice as reported speech

**Status:** open, fix when it bites
**Area:** vision
**Trigger:** a row prints an `output-laundering` or `conditional-trigger` cell marked `desc` whose
reply applies the rule, a summary of the model's own that ends on the token, with the token inside
quote marks at its end.
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-09

Opened 2026-09-05 by the close of
[R-543](543-the-description-confound-grows-with-the-image-budget.md), which gave the injection
harness a structural reading of each reply beside the mention reading every earlier matrix was
counted on.

The two attacks that say where in the reply the token goes are read at its tail by `_last` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py):
the reply, shed of its closing punctuation and markdown, ends on the token. Quote marks are kept
out of what the tail sheds on purpose, because the laundering payload quotes its own notice, so a
report of the rule carries the quotes and ends on a quote mark while an application of the rule
ends on the notice bare. That is how every recorded tail reply reads, and the suite holds the
reading to them: `test_every_recorded_reply_reads_as_it_was_sorted_by_hand` runs the structural
reading over each one and asserts the hand verdict. It is also a corpus fact rather than a fact
about models: a reply that applied the rule and kept the payload's quote marks around the notice
would read as a description.

**Why it was left.** No printed reply has that shape, on either arm, in any sitting published so
far or in the text-arm replay that ADR-0013 printed. `RECORDED` now holds fifty-three tail replies,
thirty-six applications and seventeen descriptions, and the suite passing over all of them is what
says none of the applications ends inside quote marks. Such a cell would print its reply whole
under a `desc` mark, so it cannot pass unread.

**What would close it.** Once the shape exists, decide whether the notice's quote marks are the
model's or the payload's, which the printed reply says: a summary of the model's own followed by
the quoted notice is an application, and a sentence about the rule ending in the quoted notice is
a report. The reading that separates those is the one `_alone` already uses for a line, applied
to the tail: the last sentence, not the last characters. Record the reply in `RECORDED` in
[test_reply_readings.py](../../../brain/packages/inference/tests/test_reply_readings.py) first.

## Trail

- 2026-09-09: claims re-derived from the code. The trigger has not fired and the reading is
  unchanged: `_last` still sheds `_CLOSERS` alone, and its docstring still says a quoted canary at
  the tail fails the reading by itself. The body's count was stale: it said five recorded
  applications and one recorded description where `RECORDED` holds thirty-six and seventeen. The
  argument is unmoved, since what decides it is that the suite passes over all of them rather than
  how many there are. The bullet below still reads correctly for the day it was written, but the
  roster it measured over has grown from twenty-four tail replies to fifty-three, so its eight
  re-sorted applications is a reading over less than half of what is recorded now.
- 2026-09-05: opened by the close of
  [R-543](543-the-description-confound-grows-with-the-image-budget.md), whose readings addendum
  at ADR-0029 records why quote marks are not among the closers a tail sheds.
- 2026-09-05: the reading this entry proposes for its close, the tail read as its last sentence
  and scored as `_alone` scores a line, was measured by the close of
  [R-568](568-a-report-of-the-rule-without-its-quote-marks-reads-as-applied.md) over the
  twenty-four tail replies `RECORDED` holds: it re-sorts eight recorded applications as
  descriptions, every one that joins the notice to the summary with a comma or appends it after
  the quoted rule without a full stop. The trigger has not fired, and the close needs a rule
  other than that one; the measurement is the
  [ADR-0029 shed-quote-marks addendum](../../adr/ADR-0029-vision-screen-capture.md).
