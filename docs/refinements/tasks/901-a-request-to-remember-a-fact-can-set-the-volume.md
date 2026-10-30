# A request to remember a fact can set the volume

**Status:** open, actionable
**Area:** tools
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Verified:** 2026-10-30

On the brain directly, "Please remember this: I work as a nurse." in a new chat made the cortex
call `set_volume` with level 0.5 and mute false, and the reply said only that it had noted the
job ([readings](../../readings/forget-card-on-remember.md#results-with-the-tool-withheld-2026-10-26)).
The call failed there only because that stack has no audio backend; on a desktop it would have
changed the volume with no card and no word in the reply. It came in 1 of the 80 requests to
remember in that reading, and in none of the 40 before it.

## What to do

Draw the request on 40 new chats under a rule written first: a row fails when its turn calls
`set_volume` or `get_volume`. A sentence in the `set_volume` description saying it runs only when
the person asks to change the sound is the candidate once 2 or more of 40 fail; a reply that
names every tool it ran is the alternative to weigh beside it.

## History

- 2026-10-26: filed from the tainted pool run of the forget card readings.
- 2026-10-30: the trigger has fired. On 2026-10-29 four driver draws called `set_volume` before a
  forget call ([readings](../../readings/forget-card-on-remember.md#the-forget-of-a-text-on-a-request-to-remember-the-draws-2026-10-29)),
  and on 2026-10-30 three of 88 requests to remember called it, where the Linux shell's volume
  call failed: `Please don't forget this: my gym class is on Tuesday.` in 1 of 4 draws
  ([readings](../../readings/forget-request-wordings.md#a-check-of-the-no-call-case-baseline-2026-10-30)),
  and two of the 56 drawn with schedules off
  ([readings](../../readings/forget-card-on-remember.md#more-forget-calls-with-schedules-on-the-separation-2026-10-30)).
  Actionable.
