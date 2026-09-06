# The not-found answer states no correction where the folder's does

**Status:** landed 2026-09-06
**Area:** email
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Opened 2026-09-05 by the close of
[552](552-the-uid-parameter-of-read-email-carries-no-description.md), which put the correction
for a uid into the parameter's description and left the answer as it was.

`FOLDER_UNKNOWN` in `brain/packages/email/src/cortex_email/values.py` states its correction in
the answer itself: call `list_folders` and use a name spelled as that list returns it. The
not-found answer, `message <uid> not found in <folder>` composed in `server.py`, states none, so
a model that reads it has only `UID_HELP` to say the answer is final, a description it read before
the call and may not reread after. `SEARCH_REFUSED` and `FOLDER_UNKNOWN` both state the
correction where the model is looking when it needs one, and the read's answer is the one of the
three that does not.

**Why it was left.** The not-found text is an own text: `cortex_orchestrator/own_texts.py`
restates it and `OwnTextToolRegistry` re-stamps it trusted on byte equality (ADR-0013 own-text
addendum), and `scripts/emailcouplings.py` holds the two spellings together. A correction added to
it is a change on both sides of that seam and to bytes the brain trusts, which is its own slice
rather than a sentence added beside a description.

**What would close it.** A `NOT_FOUND` sentence in `values.py` in the shape `FOLDER_UNKNOWN` has,
spent by `read_email` in place of the f-string, restated in `own_texts.py`, and held by the
existing registry row for the answer to reading a uid that is not there, whose mention would then
be a binding rather than a literal; plus the server test and the live own-text row moving onto
the new bytes.

## Trail

- 2026-09-05: opened by the close of
  [552](552-the-uid-parameter-of-read-email-carries-no-description.md), which described the
  parameter and left the answer's bytes alone.
- 2026-09-06: landed as written. The account of the seam held on re-derivation: the brain's
  `OwnTextToolRegistry` is the side that re-stamps, on byte equality between the result's whole
  content and what one `OwnText` renders from the brain's own copy of the call's arguments.
  `NOT_FOUND` now lives in `cortex_email/values.py` in `FOLDER_UNKNOWN`'s shape, `read_email`
  spends it in place of its f-string, `own_texts.py` restates it, and the registry row has two
  declaring sites with the server's spend held to the binding name. The ADR-0022 addendum of that
  date carries the mutation tables. What it left is
  [582](582-the-not-found-answer-is-the-one-correction-the-audit-records-as-ok.md): the answer now
  states a correction like the two refusals and is still the one of the three the audit records
  as ok.
