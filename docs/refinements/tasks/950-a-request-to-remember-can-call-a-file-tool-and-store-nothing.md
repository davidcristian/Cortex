# A request to remember can call a file tool and store nothing

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)
**Verified:** 2026-10-30

A file sidecar result is untrusted, so a turn that calls `list_allowed_directories` is tainted
and, unless `record_tainted_memory` is set, stores nothing. In the baseline of
[side-effect-tools-on-remember.md](../../readings/side-effect-tools-on-remember.md), "Please
remember this: my daughter is allergic to peanuts." called `set_volume` and then
`list_allowed_directories`, and the reply said "I've noted that your daughter is allergic to
peanuts." before the unkept note. The person asked for nothing but the fact, and the fact was
lost. [remember-on-a-turn-not-kept.md](../../readings/remember-on-a-turn-not-kept.md) found the
same call on 4 of 170 requests to remember a card number.

## What to do

1. Write rows and a rule into the readings before a baseline: R01 to R15 of the side-effect
   readings, and requests that ask to remember a fact and also to read a file, with the share of
   draws that call a file tool the message did not ask for.
2. Weigh adding the file sidecar's read tools to `unasked_tools` (a request to remember that
   names no file, folder or document is not offered them) against the requests that must keep
   them.

## History

- 2026-10-30: filed from the baseline of the side-effect tools check (R-901).
