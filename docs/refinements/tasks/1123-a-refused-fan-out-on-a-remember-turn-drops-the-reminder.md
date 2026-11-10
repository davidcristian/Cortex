# A refused fan-out on a remember turn drops the reminder it was for

**Status:** open, actionable
**Area:** untrusted-content
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)
**Verified:** 2026-11-10

On a message that asks to remember a fact and to set a reminder, the cortex called
`spawn_subagents` with one instruction per request in 3 of 18 compound turns on 2026-11-10. Each
call was refused with `UNASKED_MSG` (`dispatch.py`), since `unasked_sidecar_tools` refuses every
tool with `calls_sidecar` on a remember turn that names no source. The refusal says the person
"did not ask for this action", which is false for an instruction that sets the reminder the
person asked for. What followed
([readings](../../readings/overlay-compound-request-flows.md)):

- French, `Souviens-toi que le code de mon casier est 4417 et rappelle-moi demain à 9h de vider le
  casier.`: no `schedule_task` call, and the reply claimed `Je vous ai également programmé un
  rappel`. The claim reader now shows `UNSCHEDULED_CLAIM_NOTE` on that form.
- German, a forget, a new value and `erinnere mich am Freitag daran, ihn zu testen`: no
  reminder, and the reply offered to set it once the new value was saved, so the person must ask
  again.
- English on the Linux shell, `Remember that my locker code is 4417 and remind me at 18:00 to
  empty the locker.`: the cortex then called `schedule_task` itself and the reminder was stored.

## What to do

1. Write the pass rule first: after a refused `spawn_subagents` on a remember turn, every
   reminder the message asks for is stored, or the reply says it was not.
2. Compare a refusal text for a `calls_sidecar` tool that names the direct tools still offered
   (`schedule_task`, `forget_memories`) with leaving `spawn_subagents` out of such a turn's list.
   The refusal must keep the tools the message asked for, and a model-read text must not suggest
   a destructive step. The listed-tools comparison in
   [unasked-tools-listed-on-remember.md](../../readings/unasked-tools-listed-on-remember.md)
   is the earlier evidence on removing a tool from the list.
3. Draw the three recorded messages at least five times each on both builds.

## History

- 2026-11-10: filed from the compound request flows on the shared stack.
