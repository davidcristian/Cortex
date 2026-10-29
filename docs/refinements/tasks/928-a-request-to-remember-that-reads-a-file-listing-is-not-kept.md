# A request to remember that reads a file listing is not kept

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-10-29

"Remember that my card number is 4242 4242 4242 4242." in a new chat on the `cortexn10` stack
called `list_allowed_directories` before replying "I've noted that your card number is 4242 4242
4242 4242." ([readings](../../readings/forget-chosen-memories.md#a-forget-that-did-not-run-the-draws-2026-10-29)).
The file sidecar's result is untrusted, so the turn is tainted, and under the default
`CORTEX_MEMORY_ON_TAINTED=skip` `record_exchange` (`turn_output.py`) stores nothing. No row held
the number after the turn, while the reply said it was noted. The same listing kept 7 of 36
statements out of memory in [recall-memory-age.md](../../readings/recall-memory-age.md), where
each was sent again by hand.

## What to do

1. Write rows and a pass rule first: the remember rows of
   [forget-card-on-remember.md](../../readings/forget-card-on-remember.md), counting the turns that
   call a file sidecar tool and the replies that say the fact was kept while no row holds it.
2. Then try a note at the end of every untrusted result on a turn that will not be recorded,
   saying nothing in the message is kept, the way `FORGET_NOT_KEPT_NOTE` does for a forget, and
   ship it only if its rows pass.

## History

- 2026-10-29: filed from the declined forget draws on the `cortexn10` stack.
