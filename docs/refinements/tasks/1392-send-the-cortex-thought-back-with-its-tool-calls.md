# Send the cortex's thought back with its tool calls

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)
**Verified:** 2026-11-28

On the cortex pick (`gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, engine build b12375) a round that
follows a tool result opens its thought inside the prompt, and the model writes nothing in it on
20 of 48 final rounds drawn. A reply from such a round can be the model's working instead of an
answer, streamed to the person: 1 of 16 draws on a message asking to remember a fact and list the
reminders, and three replies of earlier runs that night. The brain sends no round's thought back
to the engine: `_round_pieces` in `cortex_core/tool_loop.py` streams each `ReasoningChunk` to the
overlay and keeps nothing of it on the assistant message that holds the round's tool calls, and
`to_openai_message` in `cortex_inference/request.py` renders no `reasoning_content`.

The pick's template renders a thought sent back on that message before its tool calls. Sent back
by a recording proxy, it left 1 of 48 final rounds without a thought, and turning thinking off
after a tool result dropped a requested listing in 4 of 16 draws
([readings](../../readings/cortex-thought-after-a-tool-result.md)).

## What to do

1. Write the pass rule before the build's first draw: the shapes F, C and N of the readings, 16
   draws each, on the built brain; it passes when its final rounds without a thought are at most
   half the no-variant rows' (20 of 48) and no shape lists less often than its no-variant row.
2. Add the round's thought to the assistant message (`Message` in
   `cortex_core/conversation.py`), kept by the tool loop, stored by the session codec
   (`cortex_session/handoff_codec.py`) so it survives a model swap, and rendered by the adapter
   as `reasoning_content`, with a contract test and a fake.
3. Check what the deep pick's template and each subagent template do with the field before it
   reaches them; a template that renders an earlier turn's thought grows every later prompt.
4. Draw the rule, and count the working form and the thought tokens per reply beside it.

## History

- 2026-11-28: filed from the cortex working reply draws, where the thought sent back by a proxy
  was the remedy that judges no prose and keeps the thought the overlay shows.
