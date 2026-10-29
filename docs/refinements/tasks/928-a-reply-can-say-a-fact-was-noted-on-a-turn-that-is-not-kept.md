# A reply can say a fact was noted on a turn that is not kept

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-10-29

`record_exchange` (`turn_output.py`) stores nothing for a turn that names `forget_memories`, reads
untrusted content under the default `CORTEX_MEMORY_ON_TAINTED=skip`, or reads a picture, among
other paths ([readings](../../readings/remember-on-a-turn-not-kept.md#the-turns-that-store-nothing)).
A request to remember can take the first two paths by itself. On the `cortexn10` stack,
"Remember that my card number is 4242 4242 4242 4242." called `forget_memories` or
`list_allowed_directories` in some draws, and most of those replies said "I've noted that your
card number is 4242 4242 4242 4242." while the turn stored nothing
([readings](../../readings/remember-on-a-turn-not-kept.md#what-the-replies-said-2026-10-29)). The
same listing kept 7 of 36 statements out of memory in
[recall-memory-age.md](../../readings/recall-memory-age.md), where each was sent again by hand.

Only the forget path tells the model, with `FORGET_NOT_KEPT_NOTE` on the call's result, and with
either of two wordings about half of those replies still said the fact was noted
([readings](../../readings/forget-card-on-remember.md#the-note-that-names-the-call-the-draws-2026-10-29)).
The skip itself is right: a forget that matched nothing may still name a value the person wants
gone, and recording a tainted turn is something a deployment opts into.

## What to do

1. Draw the baseline of rows T1 to T3 in
   [remember-on-a-turn-not-kept.md](../../readings/remember-on-a-turn-not-kept.md#rows-and-rule-2026-10-29)
   with the shipped texts.
2. Build the change written there once, for every path: one predicate that says whether a turn is
   kept, called by `record_exchange` and by a reply note that closes a reply claiming something
   was noted on a turn that is not kept, as `schedule_claim.py` does for a schedule. Draw the rows
   and ship it only if the rule passes.

## History

- 2026-10-29: filed from the forget draws on the `cortexn10` stack.
- 2026-10-29: two result texts on the forget path failed their rules: a description sentence
  that the tool is never called on a request to remember, and the note naming the call instead
  of the request. Neither shipped. The rule for a reply note on every path is written.
