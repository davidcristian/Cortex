# The not found answer reaches the meant read in 7 of 20 with no listing

**Status:** open, actionable
**Area:** email
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)
**Verified:** 2026-11-28

On the `named_uid` row of `test_uid_reading_live.py`, a read of a uid the request named and no
message has, with no search before it, the shipped `NOT_FOUND` led to a search and then the read of
uid 1238 in 7 of 20 draws on the cortex tier
([cortex uid reads](../../readings/cortex-uid-reads.md)). The other 13 fell into two
groups. Seven called `list_folders` first, which the row does not follow further, so what they read
after the folder list is unknown. Six searched and then replied with no call: five named uid 1238
off the listing and asked whether to read it, one wrote a body no answer held
([1389](1389-a-reply-after-a-listing-writes-a-body-no-read-returned.md)). Without the correction
the tier called `list_folders` in 19 of 20, so the text helps, but it does not reach the 16 of 20
the rule asked for.

Closing it means four steps, each rule written before its draw:

1. Draw the shipped text again on seeds 20 to 39, since one row's count is not yet a design case.
2. Follow a `list_folders` call: the sidecar answers it and the next call is drawn, up to the
   read, so those draws are scored on what they read and not on their first call.
3. Decide whether a reply that names the listed line and asks before reading counts as right.
   The request named a uid that does not exist, so asking first may be the correct behaviour.
4. If the shipped text still fails, draw a rewritten `NOT_FOUND` over the same row: one that says
   the folder exists, so no folder list is needed, and that the next step is the read of the line
   the request means. A rewording changes `own_texts.py` too, since the brain restates the text and
   `scripts/emailcouplings.py` compares the two.

## History

- 2026-11-28: opened by the close of
  [1382](1382-the-not-found-correction-is-undrawn-on-a-turn-that-holds-no-listing.md), whose rule
  filed the rewritten text and its row when neither the shipped text nor the one without its
  correction reached 16 of 20.
