# A reply that writes a message body no read returned has no note

**Status:** open, waiting for its trigger
**Area:** email
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)
**Trigger:** a row or a flow draws a second reply that gives a message body no `read_email`
answer of its turn returned.
**Verified:** 2026-11-28

On the `named_uid` row of `test_uid_reading_live.py` the cortex tier once searched, got the
listing, and replied with no call: the sender, subject and date of the listing's line for uid
1238, then a body ("This is a final notice regarding your overdue electricity bill...") that no
answer held. That is 1 of 60 turns drawn on the request; the `named_turn` row drew none in forty
more ([cortex uid reads](../../readings/cortex-uid-reads.md)). The person would act on that body,
and nothing in the reply says that no message was read.

## What to do

When the trigger fires, build a note the brain appends after a typed check of the reply. The check
is `marks_body` in the harness, moved into the core: in a turn that holds no `read_email` answer
that returned a message, a reply with no call is marked when one of its sentences neither ends in
`?` or `:` nor names a uid that a call or a `[uid]` listing line of the turn wrote. Its safe
direction is that it marks when unsure, so the note shows. The note says only that no message was
read in the turn, which is true on every turn the check reaches; it names no value and suggests no
step that deletes. Its cost is the note on a reply with a sentence that names no uid, such as one
saying the search found four messages. Test the check over true replies generated from the
listing's own words in the five note languages, then draw the build on the `named_turn` row.

## History

- 2026-11-28: opened by the close of
  [1382](1382-the-not-found-correction-is-undrawn-on-a-turn-that-holds-no-listing.md), whose
  follow-up row `named_turn` drew no body in forty draws, so the note waits for a second one.
