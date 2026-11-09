# A fact with a second verb phrase keeps the reminder and sound tools

**Status:** open, waiting for its trigger
**Trigger:** a recorded draw of a request to remember a fact alone that calls `schedule_task` or
`set_volume` on a turn where `actions_asked` read a clause of the fact.
**Area:** memory
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

`actions_asked` in `memory_request.py` reads a clause opening with a verb and its object, or a
verb and a time (`and ring at 9`), as an asked action, and `unasked_tools` then keeps `schedule_task` and `set_volume` offered. A fact whose
subject is left out of its second verb phrase looks the same. Unit level, both tools stay offered
for each of these, where the shipped reader before the change left both out:

- "Remember that I park on level 3 and take the lift"
- "Remember my sister likes jazz and hates the cold"
- "Remember I always lock the door and check the windows"
- "Remember: I drink my coffee black and skip the sugar"
- "Remember that I start at 9 and finish at 5"

Of 104 requests to remember alone in the backticked text of `docs/readings/`, the action reader
keeps both tools for 12; 11 ask for an action and one is a fact ("Remember that I feed the cat and
walk the dog."), recorded as a cost on the safe side in
[the second clause readings](../../readings/side-effect-tools-second-clause.md). A tool refusal
keeps the tool when unsure, so this waits for evidence that the unasked call the refusal was made
for comes back.

## What to do

1. When the trigger fires, read a verb with a third person `s` (`hates`, `loves`) and a second
   verb phrase after a subject the request states (`that I`, `my sister`) as part of the fact.

## History

- 2026-11-08: filed by the night's audit slot, from a unit probe and a count over the readings.
