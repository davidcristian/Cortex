# A reply after a refused file call can say it did not see the file

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)
**Verified:** 2026-11-05

On a request to remember that names no source, `unasked_sidecar_tools` (`unasked_tools.py`) refuses
the file calls, so no file is searched. One of six candidate draws of `Keep in mind the total from my
budget spreadsheet.` on 2026-11-05 replied "I don't see a budget spreadsheet in my accessible files",
which states the result of a search that did not run
([draws](../../readings/no-access-after-a-refused-file-call.md#the-candidate-2026-11-05)). The
2026-10-31 baseline replies also said "I don't see" or "I can't see" the file
([readings](../../readings/sidecar-tools-on-remember.md#a-value-named-by-a-record-the-draws-2026-10-31)).
`claims_no_access` (`access_claim.py`) reads only a claim of no access, so no note follows such a
reply.

## What to do

1. Count the replies that state a search result after a refused file call in the recorded draws,
   and write near misses ("I don't see why", "let me see") before any change to the reader.
2. Decide on that count whether `claims_no_access` should also read "don't see" or "can't find" a
   file. `UNSEARCHED_FILES_NOTE` is exact on every turn that refused a sidecar call, so a wrong read
   adds a correct note; write the rule before the draws.

## History

- 2026-11-05: filed from the candidate draws of
  [R-962](962-a-reply-after-a-refused-file-call-can-say-it-has-no-access.md).
