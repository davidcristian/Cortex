# A reply after a listing writes a body no read returned

**Status:** open, actionable
**Area:** email
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)
**Verified:** 2026-11-28

On the `named_uid` row of `test_uid_reading_live.py`, seed 2 of the shipped text, the cortex tier
searched, got the listing, and then replied with no call: "Here is the content:" with the sender,
subject and date of the listing's line for uid 1238, then a body ("This is a final notice
regarding your overdue electricity bill...") that no tool answer held. No `read_email` call had
returned that uid. It is one draw of twenty on one row
([cortex uid reads](../../readings/cortex-uid-reads.md)).

Closing it means a row that counts this form first: the turn ends on a listing after a request to
read one message, at least 20 seeds, and a typed reader that marks a reply presenting a message
body in a turn where no `read_email` answer returned that uid, with its rule written before the
draw. If the form recurs, the remedy is a note the brain appends after that typed check, saying no
message was read in the turn; its safe direction is that the note shows.

## History

- 2026-11-28: opened by the close of
  [1382](1382-the-not-found-correction-is-undrawn-on-a-turn-that-holds-no-listing.md), whose row
  drew it once.
