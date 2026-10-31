# A reply after a refused file call can say it has no access

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)
**Verified:** 2026-10-31

On a request to remember that names a value by the file holding it, such as "Remember the address
on my lease.", `unasked_sidecar_tools` (`unasked_tools.py`) reads no source, so a call to a file tool
is refused by name. The reply then asks the person where the file is, and 10 of 34 baseline draws
said they have no access, which is not exact while the sidecar is reachable
([readings](../../readings/sidecar-tools-on-remember.md#a-value-named-by-a-record-the-draws-2026-10-31)).
With the file in the sidecar's root the baseline stated its value in 0 of 26 draws, against 25 of 26
for a reader that let the call through. The person's next message reaches the tool once it names the
file.

## What to do

1. A reader that reads "the X from, on or in my Y" as a source when Y is a word for a written record
   passed every part of its rule but one: a reply said it noted the value with no note beside it.
   `claims_kept` now reads that reply
   ([replay](../../readings/claim-reader-replays.md#a-later-verb-after-an-earlier-one-2026-10-31)).
2. Do not drop the word list. The same shape with any Y lost the message of `Remember the meeting on
   my birthday.` in 3 of 4 draws, since a file tool's result taints the turn.
3. Draw that reader again under a new rule, with the rows of that record. Each of 36 mutations of
   its code made a near-miss test fail, and the patch is
   `/tmp/claude-1000/-home-david-Files-Git-Cortex/545ea45a-902e-44a3-86aa-5ec869e6c085/scratchpad/slot3/reader962c.patch`.
   Weigh the 5 of 8 candidate draws that also called `forget_memories` in the rule.
4. Prefer that over a new wording of `UNASKED_MSG`, which every refusal of `set_volume` and
   `schedule_task` shares.

## History

- 2026-10-31: filed from the rows of
  [R-950](950-a-request-to-remember-can-call-a-file-tool-and-store-nothing.md).
- 2026-10-31: corrected. Two rules ran on a reader of the message's shape: the first found 2 of 10
  baseline draws saying they have no access, under its bound of 3, and the second reverted the reader
  on 9 of 12 stored W draws against a bound of 10. A third rule on a reader limited to words for a
  written record reverted it on one reply the claim reader missed.
