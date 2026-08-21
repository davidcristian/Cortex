# A dispatched call's own id reaches no line

**Status:** open, actionable
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

The audit line now names the tool, the outcome and the work a call was made for, and it still does
not name the **call**. `ToolCall.id` is what correlates a call with its `ToolResult` across the
loop, and `ToolInvocation` carries no such field, so `ToolDispatcher._audited` drops the one id
that would let a line be paired with the `Role.TOOL` message it produced. Two identical calls in
one turn write two lines nothing can tell apart, which is the shape a repeat-refusal or a
confirmation loop actually takes.

It costs one field and one copy, and the reason it is not a footnote on the change that named the
work is whose string it is. A cortex call's id is written by the model: `stream_tool_loop` takes
whatever the backend emitted, and the fenced-content rules elsewhere in this repo exist because a
model-authored string on a surface is attacker-influenceable. On the audit line it would be bounded
by `VALUE_CHARS` like every other rendered value and withheld by name like every other field, and
nothing would read it back, so the question is whether "a durable record of an id the model chose"
is a fact worth keeping or a string worth refusing. The alternative shape is to record it only
where the brain authored it, which is the narrower and duller answer.

The second reading is the one that made this visible. The schedule ticker builds its dispatch as
`ToolCall(id=f"schedule-{item.id}", ...)`, and that call id is the **only** place a fired item's
identity appears on the dispatch path: the line carries the chat that scheduled the item and
nothing about which item fired. So a scheduled fire is the one caller whose own subject the trail
cannot name, and it is also the caller nobody is watching when it runs.

## Trail

- 2026-08-21: Opened by the close of
  [342](342-the-audit-trail-cannot-name-the-turn.md), which put the chat, the turn and the task on
  the line and left the call itself unnamed. Recorded in the ADR-0009 named-work addendum.
