# A dispatched call's own id reaches no line

**Status:** done 2026-08-22
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

The audit line names the tool, the outcome and the work a call was made for, and it does not name
the call. `ToolCall.id` is what matches a call with its `ToolResult` across the loop, and
`ToolInvocation` has no such field, so `ToolDispatcher._audited` drops the one id that would let a
line be paired with the `Role.TOOL` message it produced. Two identical calls in one turn write two
lines nothing can tell apart.

It costs one field and one copy, and the question is whose string it is. A cortex call's id is
written by the model: `stream_tool_loop` takes whatever the backend emitted, and the fenced-content
rules elsewhere in this repo exist because a model-authored string on a surface can be influenced
by an attacker. On the audit line it would be bounded by `VALUE_CHARS` like every other rendered
value and withheld by name like every other field, and nothing would read it back. The alternative
is to record it only where the brain wrote it.

The schedule ticker is what made this visible. It builds its dispatch as
`ToolCall(id=f"schedule-{item.id}", ...)`, and that call id is the only place a fired item's
identity appears on the dispatch path: the line has the chat that scheduled the item and nothing
about which item ran.

## History

- 2026-08-21: Opened by the close of [342](342-the-audit-trail-cannot-name-the-turn.md), which put
  the chat, the turn and the task on the line and left the call itself unnamed. Recorded in
  ADR-0009 decision 16.
- 2026-08-22: Fixed as both options, which the entry framed as alternatives. `ToolInvocation` gains
  `call_id`, copied off `ToolCall.id` by `ToolDispatcher._audited`, model-authored and all: the
  audit line records what was asked for, which is why it has always had the model's `tool` and
  `arguments`, and refusing the id would have left the correlation gap open for nearly every
  dispatch. `TurnStamp` and `ToolInvocation` gain `item_id`, which the ticker sets and no other
  caller does, because the fired item read out of the `schedule-` prefix is a fact a model can fake
  by choosing that prefix, and a fact off the stamp is one it cannot. The field name is what tells
  the two apart on the line. Recorded in ADR-0009 decision 16, which also narrows three of this
  entry's claims: the withheld-by-name rule is one `call_id` is subject to and never triggers, the
  `Role.TOOL` message the id pairs with is turn-local (`store_codec` persists no `tool_call_id`),
  and `RepeatSalience` already stops two identical calls in one turn from writing two lines that
  agree in every field. Opened [380](380-a-fires-delegates-do-not-name-the-item.md), the item
  stopping at the spawn call.
