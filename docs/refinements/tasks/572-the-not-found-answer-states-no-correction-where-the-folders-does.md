# The not-found answer states no correction where the folder's does

**Status:** done 2026-09-06
**Area:** email
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)

`FOLDER_UNKNOWN` in `brain/packages/email/src/cortex_email/values.py` states its correction in the
answer itself: call `list_folders` and use a name written as that list returns it. The not-found
answer, `message <uid> not found in <folder>` built in `server.py`, states none, so a model that
reads it has only `UID_HELP` to say the answer is final, a description it read before the call and
may not read again. `SEARCH_REFUSED` and `FOLDER_UNKNOWN` both state the correction where the model
is looking when it needs one, and the read's answer is the one of the three that does not.

The not-found text is an own text: `cortex_orchestrator/own_texts.py` repeats it and
`OwnTextToolRegistry` marks it trusted on byte equality (ADR-0013 decision 10), and
`scripts/emailcouplings.py` compares the two copies. A correction added to it is a change on both
sides of that boundary and to bytes the brain trusts, so it is its own slice.

## History

- 2026-09-05: opened by the close of
  [552](552-the-uid-parameter-of-read-email-carries-no-description.md), which described the
  parameter and left the answer's bytes alone.
- 2026-09-06: done as written. The account of the boundary held: the brain's `OwnTextToolRegistry`
  is the side that marks the result trusted, on byte equality between the result's whole content and
  what one `OwnText` builds from the brain's own copy of the call's arguments. `NOT_FOUND` now lives
  in `cortex_email/values.py` in `FOLDER_UNKNOWN`'s form, `read_email` uses it in place of its
  f-string, `own_texts.py` repeats it, and the registry entry has two declarations with the server's
  use compared against the binding name. The rule is
  [ADR-0056](../../adr/ADR-0056-email-reader-answers.md) decision 13. What it left is
  [582](582-the-not-found-answer-is-the-one-correction-the-audit-records-as-ok.md): the answer now
  states a correction like the two refusals and is still the one of the three the audit records as
  ok.
