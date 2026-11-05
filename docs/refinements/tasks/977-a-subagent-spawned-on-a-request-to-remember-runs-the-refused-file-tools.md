# A subagent spawned on a request to remember runs the refused file tools

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)
**Verified:** 2026-11-05

On a message that asks to remember and names no source, `unasked_sidecar_tools` (`unasked_tools.py`)
refuses the cortex's calls to sidecar tools, because their untrusted results taint the turn and the
fact is then not kept as asked. The refused set is computed in `tool_loop.py` for the cortex's own
calls only. `spawn_subagents` is neither refused nor left out by `unasked_tools`, and the subagents it
starts are given their own tools.

One draw of M02 on 2026-11-05
([draws](../../readings/forget-no-match-on-remember.md#the-texts-of-the-forget-calls-on-a-new-value-2026-11-05)):
the cortex's `list_allowed_directories` was refused as unasked, and the cortex then called
`spawn_subagents` with "Search for any files that might contain phone numbers in the allowed
directories." The subagent called `list_allowed_directories`, `search_files` and `read_text_file`,
and its result came back fenced as untrusted. That turn was withheld anyway by its forget call, so the draw does not show what a plain
request to remember loses; that it loses the fact the way the cortex's own call did is an assumption
from ADR-0013's reason for the refusal.

## What to do

1. Read whether a subagent's file result taints the cortex's turn, and draw a plain request to
   remember that spawns one, to see the stored row.
2. If it does, decide where the refusal belongs: `spawn_subagents` added to the tools `unasked_tools`
   refuses on a message that names no source, or the refused sidecar names passed to the subagents'
   tool lists. Near-miss messages first, as for every reader of the person's message.

## History

- 2026-11-05: filed from the draws of
  [R-969](969-a-forget-of-the-old-value-can-match-nothing-and-say-none-is-stored.md).
