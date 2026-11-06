# The 00:00 refusal, recorded as a patch

The typed refusal of a `schedule_task` or `edit_scheduled` call whose time of day is 00:00 when
the person named no midnight, built and drawn on 2026-11-06 (the result of the 00:00 refusal in
[schedule-day-only-times](schedule-day-only-times.md)). It did not ship: the pass rule of those
rows also needs the reply to name the stored time, which the refusal does not change. The patch
is kept here so the next build starts from it and not from the task's prose. Its 38 tests
(`test_schedule_midnight.py`) are listed as cases in that readings file, and the night's scratch
copies of both files are under
`/tmp/claude-1000/-home-david-Files-Git-Cortex/a64866e3-d614-4e2e-a757-12775f4290c0/scratchpad/slot4/`.
The module docs `brain-core-tools.md` and `brain-core-residency.md` name the new member beside
`YEARLY_DATE` when it ships.

```diff
diff --git a/brain/packages/core/src/cortex_core/schedule_midnight.py b/brain/packages/core/src/cortex_core/schedule_midnight.py
new file mode 100644
@@ -0,0 +1,42 @@
+"""Read whether a schedule call sets 00:00 as its time of day when the person named no midnight."""
+
+import re
+
+from cortex_core.schedule_tools import SCHEDULE_TOOL_NAME
+from cortex_core.schedule_verbs import EDIT_SCHEDULED_TOOL_NAME
+from cortex_core.tools import ToolCall
+
+MIDNIGHT_TIME_MSG = (
+    "REFUSED: this call sets the time of day to 00:00 and the person named no midnight, so it was "
+    "not run. A reminder at 00:00 fires while the person is likely asleep. Call again with the "
+    "time of day the person meant, or with the default 09:00 in the schedule zone when they named "
+    "none."
+)
+
+_SCHEDULING = frozenset({SCHEDULE_TOOL_NAME, EDIT_SCHEDULED_TOOL_NAME})
+_MIDNIGHT = re.compile(
+    r"\bmidnight\b|\b0?0:00\b(?!\s*[ap]\.?m\b)|\b12(?::00)?\s*a\.?m\b", re.IGNORECASE
+)
+_AT_TIME = re.compile(r"^\s*0?0:00\s*$")
+_AT = re.compile(r"[T ]0?0:00(?::00(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?\s*$", re.IGNORECASE)
+
+
+def names_midnight(message: str) -> bool:
+    """Whether ``message`` names midnight as a word, as 0:00 or 00:00, or as 12 am."""
+    return _MIDNIGHT.search(message) is not None
+
+
+def sets_midnight(call: ToolCall) -> bool:
+    """Whether ``call`` schedules or edits a reminder whose ``at_time`` or ``at`` time is 00:00."""
+    if call.name not in _SCHEDULING:
+        return False
+    at_time = call.arguments.get("at_time")
+    at = call.arguments.get("at")
+    return (isinstance(at_time, str) and _AT_TIME.match(at_time) is not None) or (
+        isinstance(at, str) and _AT.search(at) is not None
+    )
+
+
+def midnight_unasked(call: ToolCall, query: str) -> bool:
+    """Whether ``call`` sets 00:00 as the time of day while the ``query`` names no midnight."""
+    return sets_midnight(call) and not names_midnight(query)
diff --git a/brain/packages/core/src/cortex_core/brain_phase.py b/brain/packages/core/src/cortex_core/brain_phase.py
@@ -14,6 +14,7 @@ from cortex_core.handoff_view import (
     declined_calls,
     deep_history,
     deep_tail,
+    midnight_refused_calls,
     yearly_refused_calls,
 )
 from cortex_core.output_channels import open_output_channels
@@ -107,6 +108,7 @@ class BrainPhase:
             generating=_DEEP_GENERATING,
             declined=declined_calls(record),
             yearly_refused=tuple(yearly_refused_calls(record)),
+            midnight_refused=tuple(midnight_refused_calls(record)),
             results_spent=sum(len(m.text) for m in tail if m.role is Role.TOOL),
             query=query,
         )
diff --git a/brain/packages/core/src/cortex_core/dispatch.py b/brain/packages/core/src/cortex_core/dispatch.py
@@ -11,6 +11,7 @@ from cortex_core.errors import ToolError
 from cortex_core.log_secrets import REDACTED
 from cortex_core.ports import Clock, Confirmer, ToolAuditSink, ToolRegistry
 from cortex_core.progress import hold_wait
+from cortex_core.schedule_midnight import MIDNIGHT_TIME_MSG
 from cortex_core.schedule_yearly import YEARLY_DATE_MSG
 from cortex_core.tool_budget import UNIFORM_COST, ToolCostPolicy
 from cortex_core.tool_round import MAX_CALLS_PER_ROUND
@@ -82,6 +83,7 @@ class DispatchRefusal(Enum):
 
     BUDGET = BUDGET_EXHAUSTED_MSG
     DECLINED = ALREADY_DECLINED_MSG
+    MIDNIGHT_TIME = MIDNIGHT_TIME_MSG
     REDUNDANT = REDUNDANT_MSG
     ROUND_OVERSIZED = ROUND_OVERSIZED_MSG
     UNASKED = UNASKED_MSG
diff --git a/brain/packages/core/src/cortex_core/dispatch_round.py b/brain/packages/core/src/cortex_core/dispatch_round.py
@@ -14,6 +14,7 @@ from cortex_core.memory_forget_chosen import FORGET_CHOSEN_TOOL_NAME
 from cortex_core.ports import Clock
 from cortex_core.progress import ProgressSink, hold_wait
 from cortex_core.provenance import SourceKind, as_source
+from cortex_core.schedule_midnight import midnight_unasked
 from cortex_core.schedule_yearly import monthly_for_yearly, same_month_days, stores_monthly
 from cortex_core.stops import StopLedger
 from cortex_core.tool_budget import DispatchBudget
@@ -56,6 +57,8 @@ class ToolLoopContext:
     query: str = ""
     # The monthly schedule calls refused for a yearly date in a loop this one continues.
     yearly_refused: tuple[ToolCall, ...] = ()
+    # The 00:00 schedule calls refused in a loop this one continues; the next one runs.
+    midnight_refused: tuple[ToolCall, ...] = ()
 
     @property
     def unit_id(self) -> str:
@@ -73,6 +76,8 @@ class LoopRecord:
     unasked: frozenset[str] = frozenset()
     # The monthly schedule calls refused for a yearly date; a retry on the same days runs.
     yearly_refused: list[ToolCall] = field(default_factory=list[ToolCall])
+    # The 00:00 schedule calls refused once in this turn; a second one runs.
+    midnight_refused: list[ToolCall] = field(default_factory=list[ToolCall])
 
 
 def _unasked_refusal(
@@ -85,6 +90,9 @@ def _unasked_refusal(
     if not retried and monthly_for_yearly(call, context.query):
         record.yearly_refused.append(call)
         return DispatchRefusal.YEARLY_DATE
+    if not record.midnight_refused and midnight_unasked(call, context.query):
+        record.midnight_refused.append(call)
+        return DispatchRefusal.MIDNIGHT_TIME
     return None
 
 
diff --git a/brain/packages/core/src/cortex_core/handoff_view.py b/brain/packages/core/src/cortex_core/handoff_view.py
@@ -6,6 +6,7 @@ from dataclasses import replace
 from cortex_core.conversation import Message, Role, ToolRun
 from cortex_core.escalate import ESCALATION_QUEUED_MSG
 from cortex_core.handoff import HandoffRecord
+from cortex_core.schedule_midnight import MIDNIGHT_TIME_MSG
 from cortex_core.schedule_yearly import YEARLY_DATE_MSG
 from cortex_core.tools import ToolCall
 from cortex_core.untrusted import says_declined
@@ -44,18 +45,26 @@ def declined_calls(record: HandoffRecord) -> list[ToolCall]:
     ]
 
 
-def yearly_refused_calls(record: HandoffRecord) -> list[ToolCall]:
-    """The monthly schedule calls refused for a yearly date before the handoff, from the tail."""
+def _refused_calls(record: HandoffRecord, refusal: str) -> list[ToolCall]:
+    """The calls in the tail whose result starts with ``refusal``, read by id."""
     refused = {
-        message.tool_call_id
-        for message in record.loop_tail
-        if message.text.startswith(YEARLY_DATE_MSG)
+        message.tool_call_id for message in record.loop_tail if message.text.startswith(refusal)
     }
     return [
         call for message in record.loop_tail for call in message.tool_calls if call.id in refused
     ]
 
 
+def yearly_refused_calls(record: HandoffRecord) -> list[ToolCall]:
+    """The monthly schedule calls refused for a yearly date before the handoff, from the tail."""
+    return _refused_calls(record, YEARLY_DATE_MSG)
+
+
+def midnight_refused_calls(record: HandoffRecord) -> list[ToolCall]:
+    """The schedule calls refused for an unasked 00:00 before the handoff, from the tail."""
+    return _refused_calls(record, MIDNIGHT_TIME_MSG)
+
+
 def deep_tail(record: HandoffRecord) -> tuple[Message, ...]:
     """The record's tail, with the escalation's result addressed to the deep model."""
     taken = HANDOFF_TAKEN_MSG.format(brief=record.brief)
diff --git a/brain/packages/core/src/cortex_core/tool_loop.py b/brain/packages/core/src/cortex_core/tool_loop.py
@@ -116,6 +116,7 @@ async def stream_tool_loop(
         room=ResultRoom(context.room_chars, spent=context.results_spent),
         unasked=unasked,
         yearly_refused=list(context.yearly_refused),
+        midnight_refused=list(context.midnight_refused),
     )
     said: list[str] = []
     for _step in range(MAX_TOOL_STEPS):
```
