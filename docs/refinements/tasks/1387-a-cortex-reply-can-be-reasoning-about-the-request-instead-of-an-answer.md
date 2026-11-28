# A cortex reply can be reasoning about the request instead of an answer

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)
**Verified:** 2026-11-28

On the cortex tier as the stack starts it (`gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, engine build
b12375, no reasoning flag), 2 of the 24 second-turn replies drawn for
[R-1381](1381-a-forget-result-left-without-its-not-kept-note-stays-without-it-after-a-later-taint.md)
were the model working through the request in the answer text: `The user's request has two
parts: ...`, then `Wait, let me re-read the forget_memories tool definition`, a list of the tools
it was given, and so on for 7,016 and 2,296 characters. The server sent no reasoning field on
either request, so the brain streamed that text to the person as the answer. One came after a
failed `schedule_task` call, the other after a forget call made once the listing was read
([readings](../../readings/forget-later-taint.md)).

## What to do

1. Draw how often it happens on a plain message with one failed tool call and on one with none,
   12 draws each, so the count says whether a failed call is part of the cause.
2. Name a remedy that does not judge prose, such as turning the cortex's thinking on so the
   working goes to the reasoning field, and state its cost in tokens per reply; a reader of the
   reply's words is the last choice.

## History

- 2026-11-28: filed from R-1381, whose draws showed it on one HEAD draw and one draw of the
  fixed build.
