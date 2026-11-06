# The forget after a delete, recorded as a patch

The result a `forget_memories` call reads when it matches nothing after an earlier call in the same
turn whose card deleted a row, built and drawn on 2026-11-06 (step 1 of R-969; the rule and the
draws are in [forget-no-match-on-remember](forget-no-match-on-remember.md)). It did not ship: the
form it changes came in 1 of the 30 draws its rule counted. The patch is kept here so the next build
starts from it and not from the task's prose. Its seven tests (`test_forget_after_delete.py`) are one
each for a later unmatched call in the same turn naming the delete, a repeat of the deleting text
naming it too, an unmatched call in a later turn saying none was stored, two unmatched calls with no
delete both saying so, a failed delete leaving the turn without one, a later call matching a new row
still getting a card, and only the latest turns keeping their delete; the night's scratch copies of
both files are under
`/tmp/claude-1000/-home-david-Files-Git-Cortex/a64866e3-d614-4e2e-a757-12775f4290c0/scratchpad/slot8/`.
The module doc `brain-core-memory.md` names the new result beside `_NONE_FOUND` when it ships.

```diff
diff --git a/brain/packages/core/src/cortex_core/memory_forget_chosen.py b/brain/packages/core/src/cortex_core/memory_forget_chosen.py
@@ -18,6 +18,11 @@ _NONE_FOUND = (
     "nothing was forgotten: no remembered exchange contains that text, so tell the user that "
     "nothing about it was stored, and do not ask the user for the value"
 )
+_ALREADY_DELETED = (
+    "nothing more was forgotten: no remembered exchange contains that text, and an earlier call "
+    "in this turn already deleted what the user asked to forget, so tell the user it was deleted "
+    "and do not say that it was not stored or could not be found"
+)
 
 FORGET_NOT_KEPT_NOTE = (
     "Nothing in this message is kept in memory, because it asked to forget something, so do not "
@@ -48,6 +53,7 @@ class ForgetChosenTool:
         self._store = store
         self._scope = scope
         self._shown: dict[str, tuple[str, ...] | str] = {}
+        self._deleted_turns: dict[str, None] = {}
 
     @property
     def result_note(self) -> str:
@@ -111,6 +117,8 @@ class ForgetChosenTool:
                 f"nothing was forgotten: more than {FORGET_CHOSEN_LIMIT} remembered exchanges "
                 "contain that text, so ask the user for a longer, more exact text"
             ), None
+        if not found and call.stamp.turn_id in self._deleted_turns:
+            return _ALREADY_DELETED, None
         if not found:
             return _NONE_FOUND, None
         lines = "\n".join(f"- {_excerpt(record, _text(call))}" for record in found)
@@ -133,9 +141,12 @@ class ForgetChosenTool:
         if shown is None:
             return self._result(call, "nothing was forgotten: no card listed what to delete")
         if isinstance(shown, str):
-            return self._result(call, shown, error=shown != _NONE_FOUND)
+            return self._result(call, shown, error=shown not in (_NONE_FOUND, _ALREADY_DELETED))
         try:
             removed = await self._store.delete_ids(shown)
+            self._deleted_turns[call.stamp.turn_id] = None
+            while len(self._deleted_turns) > _PENDING_CALLS:
+                del self._deleted_turns[next(iter(self._deleted_turns))]
             left = await self._found(call)
         except MemoryStoreError as err:
             return self._result(call, f"the memory store failed during the forget: {err}")
```
