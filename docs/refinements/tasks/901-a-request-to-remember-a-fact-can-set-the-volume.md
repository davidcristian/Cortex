# A request to remember a fact can set the volume

**Status:** open, waiting for its trigger
**Area:** tools
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** a volume change that no message of its chat asked for is reported from a real chat, or a second driver row shows one
**Verified:** 2026-10-26

On the brain directly, "Please remember this: I work as a nurse." in a new chat made the cortex
call `set_volume` with level 0.5 and mute false, and the reply said only that it had noted the
job ([readings](../../readings/forget-card-on-remember.md#results-with-the-tool-withheld-2026-10-26)).
The call failed there only because that stack has no audio backend; on a desktop it would have
changed the volume with no card and no word in the reply. It came in 1 of the 80 requests to
remember in that reading, and in none of the 40 before it.

## What to do

When the trigger fires, draw the request on 40 new chats under a rule written first: a row fails
when its turn calls `set_volume` or `get_volume`. A sentence in the `set_volume` description
saying it runs only when the person asks to change the sound is the candidate once 2 or more of
40 fail; a reply that names every tool it ran is the alternative to weigh beside it.

## History

- 2026-10-26: filed from the tainted pool run of the forget card readings.
