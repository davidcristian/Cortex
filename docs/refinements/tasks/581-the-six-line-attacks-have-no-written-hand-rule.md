# The six line attacks have no written hand rule

**Status:** open, fix when it bites
**Area:** inference
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-19
**Trigger:** a printed reply on one of the six whose sort is argued rather than read off the line, which is any reply carrying the token on a line with the model's own words that a sitting wants to count as obedience.

Opened 2026-09-06 by the close of
[R-576](576-the-two-applications-every-boundary-rule-re-sorts-were-sorted-by-an-unwritten-rule.md),
which wrote the hand rule for the two attacks whose instruction names the tail.

The roster comment of
[test_reply_readings.py](../../../brain/packages/inference/tests/test_reply_readings.py) now says
what a hand sort reads on `output-laundering` and `conditional-trigger`. The six attacks whose
instruction is the token itself have nothing written: their structural reading is `_alone`, a line
that is the token and nothing else, and the only thing recorded beside it is one edge, a token on a
line with words of the model's own
([R-561](561-a-token-beside-the-models-own-words-is-read-as-a-description.md)). Every recorded
description of those six is a report of the dialog that paraphrases its instruction and quotes the
token inside the report, which the reading and any sort agree on, so nothing has yet needed the
rule.

**Why it was left.** A rule with no case that tests it is a guess. The tail rule was written
because four printed replies of one shape forced a class on the record; the line attacks have
produced no reply where a reading and a sort could part.

**What would close it.** Write the rule for the six the way the tail rule is written, in the roster
comment beside it, and record the reply that made it necessary. If the trigger has not fired by the
time the line reading changes for another reason, close this as declined and say that the line
reading needed no hand rule.

## Trail

- 2026-09-19: claims re-derived and the entry stands. The roster comment still writes a hand
  rule for the two tail attacks alone. The trigger has not fired: both unattended sittings, of
  2026-09-17 and of tonight, drew `output-laundering` in every cell. The one row since the last
  reading that drew the six, the cortex alt's `4800x2700` matrix drawn early on 2026-09-13, which
  the bullet below missed, printed four reports of the screen's instruction and two tokens alone,
  none a token beside words of the model's own. The body's "word for word" was wrong: the
  recorded descriptions paraphrase the instruction.
- 2026-09-13: claims re-derived from the code and the entry stands. The roster comment still
  writes a hand rule for the two tail attacks and nothing for the six read by `_alone`, and the
  ten recorded replies for those six are unchanged: three descriptions, each a report of the
  dialog word for word, and seven obediences, each the token alone. The trigger has not fired,
  and today's three image rows could not have fired it, because a payload sweep draws the
  `output-laundering` attack alone.
- 2026-09-06: opened by the close of
  [R-576](576-the-two-applications-every-boundary-rule-re-sorts-were-sorted-by-an-unwritten-rule.md),
  whose [ADR-0029 one-class addendum](../../adr/ADR-0029-vision-screen-capture.md) wrote the tail
  rule and named this as what it does not cover.
