# A request to use the forget tool reads as no forget

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

`asks_to_forget` (`memory_request.py`) reads a forget verb at a clause start. A request that names
the tool first puts the verb after `to`, so `Use your forget tool to forget what I told you about
my dentist.` reads as asking to forget nothing, while `Forget what I told you about my dentist.`
and `Please forget what I told you about my dentist.` read as a forget. The row the person asked
to delete is kept, which is the safe direction and a cost.

Drawn live on 2026-11-26 (build b12375, the cortex gemma-4-12B, the deep pick Qwen3.8-27B): the
message `Hand this to the deep model with your escalate tool: use your forget tool to forget what
I told you about my dentist, then tell me what was forgotten.` One stored row named the dentist.
The cortex's `forget_memories` call was refused as asking to forget nothing, and the deep model's
call `{"text": "dentist"}` was refused with `nothing was forgotten`; the row was kept, and the
reply said nothing was found to delete. Logs: `logs/draw2/` of
`~/.cache/cortex-run/2026-11-26/s1/`.

## What to do

1. Add the form to the forget generator (a verb of use or of calling naming the tool, then `to`
   and a forget verb) in the five note languages, and count the rows it keeps before any change.
2. Do not add a word to a list. Prefer a rule that reads a forget verb after `to` when the clause
   names the forget tool, and replay it over the word pairs: it may only narrow a call, never list
   a row the call text did not name.
3. Check the reply: a refused forget the reply reports as "nothing found" is a wrong statement
   about the stored row, which a note on the reply could correct.

## History

- 2026-11-26: filed by the live draw of
  [R-1308](1308-the-deep-picks-prompt-cache-restores-every-returning-conversation.md), whose turn
  with a deep tool call used this form.
