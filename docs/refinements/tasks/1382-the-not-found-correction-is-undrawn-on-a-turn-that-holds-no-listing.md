# The not found correction is undrawn on a turn that holds no listing

**Status:** open, actionable
**Area:** email
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)
**Verified:** 2026-11-27

`NOT_FOUND` tells the model to search the folder again and copy a uid from that answer. Every row
of `test_uid_reading_live.py` opens with a search, so the listing is in the turn when the
not-found answer arrives, and on the cortex tier the shipped text, the text without its correction
and the bare failure all drew the same retry with the listed uid
([imap server answers](../../readings/imap-server-answers.md)). The correction is the only path
on a turn whose read did not follow a search, such as a request that names a uid itself, and no
row draws that turn.

Closing it means a row whose first step is a read of a uid no message has, with no search before
it, drawn over the three answers of the after not found row, with its pass rule written first.

## History

- 2026-11-27: opened by the close of
  [584](584-the-uid-rows-are-measured-where-the-listing-answers-the-ask.md), whose three
  after not found variants read the same on a turn that held the listing.
