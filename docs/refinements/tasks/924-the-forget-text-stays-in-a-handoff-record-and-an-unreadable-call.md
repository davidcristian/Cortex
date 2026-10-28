# The forget text stays in a handoff record and an unreadable call

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-28

`ToolSpec.private_arguments` keeps the `forget_memories` text out of the tool audit, and a row on
the `cortexn9` stack found it nowhere else in the logs
([readings](../../readings/forget-chosen-memories.md#a-forget-and-a-new-fact-in-one-message-2026-10-28)).
Two places read from the code still keep it:

- **The handoff record.** A turn whose cortex calls the forget and then escalates stores the
  loop tail, the call's arguments included, in Redis under `cortex:handoff:<id>`
  (`handoff_codec.py`), kept for an hour after the handoff ends.
- **An unreadable call.** `finish_calls` (`cortex_inference/decode.py`) puts the raw argument text
  in `MalformedToolCallError`, and `TurnEngine` logs it with its traceback, so a forget call the
  model wrote as broken JSON puts the value in the brain log.

The subagent and ticker dispatchers have no private names, but their registries do not hold the
forget, so a call to it there needs a model to name a tool it was never shown.

## What to do

1. Write the loop tail with each private call's arguments replaced by `<redacted>`; the deep
   model needs the call's name and id, not its text. The private names are in the dispatch policy,
   which the handoff path must be given.
2. Name the tool and the argument length in the unreadable call's error instead of the text, and
   check what the readings that diagnose unreadable calls rely on before removing it.

## History

- 2026-10-28: filed from the second audit of the forget tool.
