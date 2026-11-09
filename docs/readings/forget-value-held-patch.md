# The note on a forget that matched nothing while its value is held, recorded as a patch

A note the brain appends when a `forget_memories` call matched nothing (`_NONE_FOUND`) while a
memory holds a whole value the call's text names, built and drawn on 2026-11-09 for
[R-1061](../refinements/tasks/1061-a-forget-of-what-was-just-said-can-match-nothing-and-say-it-was-never-stored.md);
the rule and the draws are in [forget-what-was-just-said](forget-what-was-just-said.md). It did not
ship: the form it changes came in none of the draws its rule counted. The patch is kept here so the
next build starts from it.

The new module `forget_value_held.py` holds `VALUE_HELD_NOTE` and `value_held`, which runs
`value_searches` for each whole value of the text and returns whether a found row holds the same
value, and `False` on a `MemoryStoreError`. The tool asks it only for a `_NONE_FOUND` result and
marks `ToolResult.value_held`; the round ORs that into `TaintLedger.forget_value_held`, which the
handoff record and its codec keep; `limit_notes` appends the note when the mark is set and no forget
of the turn deleted a memory. Its tests (`test_forget_value_held.py`, 15 of them, plus one deep
reply test in `test_handoff_reply_flags.py` and two codec tests in `test_handoff_store_contract.py`)
cover a German phrase, a separated number and an English phrase holding the value; near misses with
no value, a longer number, no rows, the new value and a year; a store failure; more than 20 matches;
and three turns: the note on an unmatched call, no note after a later delete, and the note kept
after a later unmatched call naming no value. Eight mutation rows over those three files (96 tests)
all failed: the search never true, any found row counted, the failure not caught, the mark set on
every result without a card, the note after a delete, a later call overwriting the mark, and the
handoff and the codec dropping it. The night's copies are under
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot5/final/`.
When it ships, ADR-0075 and the module doc `brain-core-memory.md` name the note.

```diff
diff --git a/brain/packages/core/src/cortex_core/closing_notes.py b/brain/packages/core/src/cortex_core/closing_notes.py
--- a/brain/packages/core/src/cortex_core/closing_notes.py
+++ b/brain/packages/core/src/cortex_core/closing_notes.py
@@ -7,8 +7,14 @@ from cortex_core.chat_only_claim import KEPT_BEYOND_CHAT_NOTE, claims_chat_only
 from cortex_core.conversation import ToolRun
 from cortex_core.events import TurnEvent
 from cortex_core.file_claim import UNREAD_FOLDERS_NOTE, unread_folders_claim
-from cortex_core.forget_claim import UNFORGOTTEN_CLAIM_NOTE, names_removal, unforgotten_claim
+from cortex_core.forget_claim import (
+    UNFORGOTTEN_CLAIM_NOTE,
+    deleted_memory,
+    names_removal,
+    unforgotten_claim,
+)
 from cortex_core.forget_unfound_claim import DELETED_UNFOUND_NOTE, unfound_claim
+from cortex_core.forget_value_held import VALUE_HELD_NOTE
 from cortex_core.memory_claim import (
     UNKEPT_CLAIM_NOTE,
     claims_kept,
@@ -68,6 +74,7 @@ def limit_notes(  # noqa: PLR0913 -- each claim note reads its own part of the t
     )
     held = numbers_left_claim(reply, left=taint.forget_numbers_left)
     unfound = unfound_claim(made, reply, unmatched=taint.forget_unmatched)
+    held_unfound = taint.forget_value_held and not deleted_memory(made, taint.forget_unmatched)
     unread = unread_folders_claim(taint, query, reply)
     unsearched = unsearched_files_claim(taint, reply)
     yield from cap_note(stops, parts)
@@ -92,6 +99,7 @@ def limit_notes(  # noqa: PLR0913 -- each claim note reads its own part of the t
         (unforgotten, UNFORGOTTEN_CLAIM_NOTE),
         (held, in_language(NUMBERS_LEFT_NOTE, NUMBERS_LEFT_NOTES, language)),
         (unfound, DELETED_UNFOUND_NOTE),
+        (held_unfound, VALUE_HELD_NOTE),
         (unread, UNREAD_FOLDERS_NOTE),
         (unsearched, UNSEARCHED_FILES_NOTE),
     ):
diff --git a/brain/packages/core/src/cortex_core/dispatch_round.py b/brain/packages/core/src/cortex_core/dispatch_round.py
--- a/brain/packages/core/src/cortex_core/dispatch_round.py
+++ b/brain/packages/core/src/cortex_core/dispatch_round.py
@@ -185,6 +185,7 @@ def _stamp(context: ToolLoopContext) -> TurnStamp:
 def _note_forget(taint: TaintLedger, result: ToolResult) -> None:
     """Record in ``taint`` whether a ``forget_memories`` result matched nothing or left numbers."""
     taint.forget_unmatched += int(result.matched_nothing)
+    taint.forget_value_held = taint.forget_value_held or result.value_held
     if result.numbers_left is not None:
         taint.forget_numbers_left = result.numbers_left
 
diff --git a/brain/packages/core/src/cortex_core/forget_value_held.py b/brain/packages/core/src/cortex_core/forget_value_held.py
new file mode 100644
--- /dev/null
+++ b/brain/packages/core/src/cortex_core/forget_value_held.py
@@ -0,0 +1,27 @@
+"""Show that a forget which matched nothing named a value a remembered exchange still holds."""
+
+from collections.abc import Sequence
+
+from cortex_core.errors import MemoryStoreError
+from cortex_core.memory_values import value_searches, whole_values
+from cortex_core.ports import MemoryStore
+
+VALUE_HELD_NOTE = (
+    "\n\n(No remembered exchange holds the whole text the forget searched for, so nothing was "
+    "deleted, but a number or code from that text is still held in memory.)"
+)
+
+
+async def value_held(
+    store: MemoryStore, text: str, scopes: Sequence[str] | None, *, limit: int
+) -> bool:
+    """Whether a memory of ``scopes`` holds a whole value ``text`` names; ``False`` on a failure."""
+    try:
+        for key, form in whole_values(text).items():
+            for search in value_searches(key, form):
+                found = await store.find_text(search, limit=limit, scopes=scopes)
+                if any(key in whole_values(record.text) for record in found):
+                    return True
+    except MemoryStoreError:
+        return False
+    return False
diff --git a/brain/packages/core/src/cortex_core/handoff.py b/brain/packages/core/src/cortex_core/handoff.py
--- a/brain/packages/core/src/cortex_core/handoff.py
+++ b/brain/packages/core/src/cortex_core/handoff.py
@@ -56,6 +56,7 @@ class HandoffRecord:
     forget_unmatched: int = 0
     forget_refused: bool = False
     forget_numbers_left: bool = False
+    forget_value_held: bool = False
     sidecar_refused: bool = False
     monthly_stored: bool = False
     stored_time: str = ""
@@ -86,6 +87,7 @@ class HandoffRecord:
             forget_unmatched=self.forget_unmatched,
             forget_refused=self.forget_refused,
             forget_numbers_left=self.forget_numbers_left,
+            forget_value_held=self.forget_value_held,
             sidecar_refused=self.sidecar_refused,
             monthly_stored=self.monthly_stored,
             stored_time=self.stored_time,
@@ -163,6 +165,7 @@ class EscalationSlot:
             forget_unmatched=self.refs.taint.forget_unmatched,
             forget_refused=self.refs.taint.forget_refused,
             forget_numbers_left=self.refs.taint.forget_numbers_left,
+            forget_value_held=self.refs.taint.forget_value_held,
             sidecar_refused=self.refs.taint.sidecar_refused,
             monthly_stored=self.refs.taint.monthly_stored,
             stored_time=self.refs.taint.stored_time,
diff --git a/brain/packages/core/src/cortex_core/memory_forget_chosen.py b/brain/packages/core/src/cortex_core/memory_forget_chosen.py
--- a/brain/packages/core/src/cortex_core/memory_forget_chosen.py
+++ b/brain/packages/core/src/cortex_core/memory_forget_chosen.py
@@ -2,10 +2,11 @@
 
 import re
 from collections.abc import Sequence
-from dataclasses import dataclass
+from dataclasses import dataclass, replace
 
 from cortex_core.errors import MemoryStoreError
 from cortex_core.forget_unnamed import KEPT_ALL, KEPT_LINE, forgot, unnamed
+from cortex_core.forget_value_held import value_held
 from cortex_core.memory import MemoryRecord
 from cortex_core.memory_values import code_runs, digit_runs, value_searches, whole_values
 from cortex_core.ports import MemoryStore
@@ -261,7 +262,12 @@ class ForgetChosenTool:
         if shown is None:
             return self._result(call, "nothing was forgotten: no card listed what to delete")
         if isinstance(shown, str):
-            return self._result(call, shown, error=shown not in (_NONE_FOUND, _ALREADY_DELETED))
+            result = self._result(call, shown, error=shown not in (_NONE_FOUND, _ALREADY_DELETED))
+            scopes, limit = self._scope.read_scopes(call.stamp.session_id), FORGET_CHOSEN_LIMIT
+            held = shown == _NONE_FOUND and await value_held(
+                self._store, _text(call), scopes, limit=limit
+            )
+            return replace(result, value_held=held)
         try:
             removed = await self._store.delete_ids(shown.ids)
             turn = call.stamp.turn_id
diff --git a/brain/packages/core/src/cortex_core/tools.py b/brain/packages/core/src/cortex_core/tools.py
--- a/brain/packages/core/src/cortex_core/tools.py
+++ b/brain/packages/core/src/cortex_core/tools.py
@@ -101,6 +101,8 @@ class ToolResult:
     # Set by a forget that deleted rows: whether rows still hold a number a row it or an earlier
     # call of the turn deleted held. ``None`` leaves the turn's earlier answer as it is.
     numbers_left: bool | None = None
+    # Set by a forget that matched nothing while a memory holds a whole value its text names.
+    value_held: bool = False
 
 
 @dataclass(frozen=True, slots=True)
diff --git a/brain/packages/core/src/cortex_core/untrusted.py b/brain/packages/core/src/cortex_core/untrusted.py
--- a/brain/packages/core/src/cortex_core/untrusted.py
+++ b/brain/packages/core/src/cortex_core/untrusted.py
@@ -144,6 +144,8 @@ class TaintLedger:
     # Whether the last delete by ``forget_memories`` left rows holding a number a row it or an
     # earlier delete of the turn held.
     forget_numbers_left: bool = False
+    # Whether a ``forget_memories`` call matched nothing while a memory holds a value it named.
+    forget_value_held: bool = False
     # Whether a sidecar call, or a call that runs sidecar tools, was refused as unasked.
     sidecar_refused: bool = False
     # Whether a ``schedule_task`` call stored a rule that repeats on days of every month.
diff --git a/brain/packages/session/src/cortex_session/handoff_codec.py b/brain/packages/session/src/cortex_session/handoff_codec.py
--- a/brain/packages/session/src/cortex_session/handoff_codec.py
+++ b/brain/packages/session/src/cortex_session/handoff_codec.py
@@ -73,6 +73,7 @@ def encode_record(record: HandoffRecord) -> str:
             "forget_unmatched": record.forget_unmatched,
             "forget_refused": record.forget_refused,
             "forget_numbers_left": record.forget_numbers_left,
+            "forget_value_held": record.forget_value_held,
             "sidecar_refused": record.sidecar_refused,
             "monthly_stored": record.monthly_stored,
             "stored_time": record.stored_time,
@@ -130,6 +131,7 @@ def decode_record(raw: bytes | str, handoff_id: str) -> HandoffRecord:
             forget_unmatched=fields.get("forget_unmatched", 0),
             forget_refused=fields.get("forget_refused", False),
             forget_numbers_left=fields.get("forget_numbers_left", False),
+            forget_value_held=fields.get("forget_value_held", False),
             sidecar_refused=fields.get("sidecar_refused", False),
             monthly_stored=fields.get("monthly_stored", False),
             stored_time=fields.get("stored_time", ""),
```
