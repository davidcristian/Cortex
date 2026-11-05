# A reply after a refused file call can say it has no access

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)
**Verified:** 2026-11-05

On a request to remember that names a value by the file holding it, such as "Remember the address
on my lease.", `unasked_sidecar_tools` (`unasked_tools.py`) reads no source, so a call to a file tool
is refused by name. The reply then asks the person where the file is, and 10 of 34 baseline draws
said they have no access, which is not exact while the sidecar is reachable
([readings](../../readings/sidecar-tools-on-remember.md#a-value-named-by-a-record-the-draws-2026-10-31)),
and 2 of 8 more on 2026-11-05 ([draws](../../readings/no-access-after-a-refused-file-call.md)).
With the file in the sidecar's root the baseline stated its value in 0 of 26 draws, against 25 of 26
for a reader that let the call through. The person's next message reaches the tool once it names the
file.

## What to do

1. Build the brain-appended note of
   [the rule](../../readings/no-access-after-a-refused-file-call.md#rows-and-the-rule-2026-11-05):
   a `TaintLedger` flag set when a sidecar call is refused as `UNASKED`, a typed reader of a reply
   sentence saying it has no access, and a note in `closing_notes.py` that no file was searched and
   that naming the file has it read. Near misses first: access named in a condition or a question.
2. Replay the reader over the baseline replies of that record and every reply quoted in the readings,
   then draw one candidate row, as the rule says. The request the model gets is the same on both
   builds, so more draws measure only noise.
3. If the note fails its rule, a refusal text for sidecar tools apart from `UNASKED_MSG`, which every
   refusal of `set_volume` and `schedule_task` shares, comes next. A reader of "the X on my Y" as a
   source is not the remedy: with any Y it lost `Remember the meeting on my birthday.` in 3 of 4
   draws, and limited to words for a written record it failed its rule on one reply.

## History

- 2026-10-31: filed from the rows of
  [R-950](950-a-request-to-remember-can-call-a-file-tool-and-store-nothing.md).
- 2026-10-31: corrected. Two rules ran on a reader of the message's shape: the first found 2 of 10
  baseline draws saying they have no access, under its bound of 3, and the second reverted the reader
  on 9 of 12 stored W draws against a bound of 10. A third rule on a reader limited to words for a
  written record reverted it on one reply the claim reader missed.
- 2026-11-05: corrected. The reader patch its steps named was in a scratchpad a reboot removed, and
  the remedy order is now a note the brain appends after a typed check. Its rows and rule are
  written, and the baseline found 2 of 8 more replies saying they have no access.
