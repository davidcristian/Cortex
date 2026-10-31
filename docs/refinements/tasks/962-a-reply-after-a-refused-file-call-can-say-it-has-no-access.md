# A reply after a refused file call can say it has no access

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)
**Verified:** 2026-10-31

On a request to remember that names a value by the file holding it, such as "Remember the address
on my lease.", `unasked_sidecar_tools` (`unasked_tools.py`) reads no source, so a call to a file tool
is refused by name. The reply then asks the person where the file is, and 7 of 26 baseline draws
said they have no access, which is not exact while the sidecar is reachable
([readings](../../readings/sidecar-tools-on-remember.md#a-file-in-reach-the-draws-2026-10-31)). With
the file in the sidecar's root the baseline stated its value in 0 of 18 draws, against 17 of 18 for a
reader that let the call through. The person's next message reaches the tool once it names the file.

## What to do

1. Do not read "the X from, on or in my Y" as a source by its shape alone. That candidate lost the
   message of `Remember the meeting on my birthday.` in 3 of 4 draws, since a file tool's result
   taints the turn.
2. Try the same shape with Y limited to words for a written record, such as lease, contract,
   spreadsheet, invoice, passport, receipt or statement. It reads W01 to W03 of that record as
   before, so their cost is gone by construction. Near-miss tests come first, every recorded draw
   message is replayed through the old and new reader, and new rows with a word not used so far and
   a rule go in the readings before any draw.
3. Prefer that over a new wording of `UNASKED_MSG`, which every refusal of `set_volume` and
   `schedule_task` shares. A candidate also shows the reply "I have added this to my memory" beside
   the note that nothing was kept, so judge that reply in the rule.

## History

- 2026-10-31: filed from the rows of
  [R-950](950-a-request-to-remember-can-call-a-file-tool-and-store-nothing.md).
- 2026-10-31: corrected. Two rules ran on a reader of the message's shape: the first found 2 of 10
  baseline draws saying they have no access, under its bound of 3, and the second reverted the reader
  on 9 of 12 stored W draws against a bound of 10.
