# The forget naming the new value, recorded as a patch

The result a `forget_memories` call reads when it matched nothing and its text is the new value the
person's message states beside a request to forget the old one, built and drawn on 2026-11-07
(step 2 of
[R-969](../refinements/tasks/969-a-forget-of-the-old-value-can-match-nothing-and-say-none-is-stored.md);
the rule and the draws are in [forget-naming-the-new-value](forget-naming-the-new-value.md)). It
did not ship: the form it changes came in none of the draws its rule counted. The patch is kept here
so the next build starts from it and not from the task's prose. The drawn build also returned the
result unchanged when it did not match nothing (`result.matched_nothing`); the patch leaves that
test out, because `named_new_value` changes only a content holding `_NONE_FOUND`, so no test could
fail without it.

Its tests (`test_forget_new_value.py`, 27 of them) are the two reader tables below and three loop
tests over the `_loop` shape of `test_forget_unmatched.py` with `query` set: the N01 call reads
`FORGET_NEW_VALUE` followed by `FORGET_NOT_KEPT_NOTE` and still counts as unmatched; the V01 call,
a `find` call returning the no-match text and a call with an integer text keep their result; and a
call naming the new value after a delete reads the delete. Fourteen mutation rows over that file
all failed (no request to forget needed, any word before the value, nine or two words between, `new`
or `to` or `previous` not read, the `I` or `we` habit read, `can you` not read, any tool rewritten,
a non-string text read, the result never rewritten, the no-match sentence kept). The night's copies
of all four files are under
`/tmp/claude-1000/-home-david-Files-Git-Cortex/37073e3c-5ca6-42f6-aae1-df9e67b0e4db/scratchpad/slot4/final/`.
When it ships, ADR-0075 and the module doc `brain-core-memory.md` name the new result beside
`_NONE_FOUND`.

```diff
diff --git a/brain/packages/core/src/cortex_core/dispatch_round.py b/brain/packages/core/src/cortex_core/dispatch_round.py
index ec8cca1fc..df6eda04d 100644
--- a/brain/packages/core/src/cortex_core/dispatch_round.py
+++ b/brain/packages/core/src/cortex_core/dispatch_round.py
@@ -6,11 +6,12 @@ from dataclasses import dataclass, field, replace
 from cortex_core.cadence import CadenceWatch
 from cortex_core.conversation import Message
 from cortex_core.dispatch import DispatchRefusal, ToolDispatcher
+from cortex_core.forget_new_value import states_new_value
 from cortex_core.handoff import EscalationSlot
 from cortex_core.inference import GenerationBounds, JsonSchema
 from cortex_core.loop_events import StepOutcome, ToolStep, step_summary
 from cortex_core.memory_forget import FORGET_UNTRUSTED_TOOL_NAME
-from cortex_core.memory_forget_chosen import FORGET_CHOSEN_TOOL_NAME
+from cortex_core.memory_forget_chosen import FORGET_CHOSEN_TOOL_NAME, named_new_value
 from cortex_core.ports import Clock
 from cortex_core.progress import ProgressSink, hold_wait
 from cortex_core.provenance import SourceKind, as_source
@@ -131,10 +132,15 @@ def _refused_by(
 def _told(
     result: ToolResult, refusal: DispatchRefusal | None, call: ToolCall, query: str
 ) -> ToolResult:
-    """The result the model reads: a wrong-date refusal names the date and the field to fix."""
-    if refusal is not DispatchRefusal.OFFSET_DATE:
+    """The result the model reads, rewritten for a wrong-date refusal or a new-value forget."""
+    if refusal is DispatchRefusal.OFFSET_DATE:
+        return replace(result, content=offset_refusal(query, call))
+    text = call.arguments.get("text")
+    if call.name != FORGET_CHOSEN_TOOL_NAME or not isinstance(text, str):
         return result
-    return replace(result, content=offset_refusal(query, call))
+    if not states_new_value(text, query):
+        return result
+    return replace(result, content=named_new_value(result.content))
 
 
 def _stamp(context: ToolLoopContext) -> TurnStamp:
diff --git a/brain/packages/core/src/cortex_core/memory_forget_chosen.py b/brain/packages/core/src/cortex_core/memory_forget_chosen.py
index cd53b9cfc..018048357 100644
--- a/brain/packages/core/src/cortex_core/memory_forget_chosen.py
+++ b/brain/packages/core/src/cortex_core/memory_forget_chosen.py
@@ -18,6 +18,11 @@ _NONE_FOUND = (
     "nothing was forgotten: no remembered exchange contains that text, so tell the user that "
     "nothing about it was stored, and do not ask the user for the value"
 )
+FORGET_NEW_VALUE = (
+    "nothing was forgotten: that text is the new value the user just gave, which no remembered "
+    "exchange holds, so call forget_memories again with one word from the request that names "
+    'the fact, such as "phone", and do not say that the old value was not stored'
+)
 _ALREADY_DELETED = (
     "nothing more was forgotten: no remembered exchange contains that text, and an earlier call "
     "in this turn already deleted what the user asked to forget, so tell the user it was deleted "
@@ -32,6 +37,11 @@ FORGET_NOT_KEPT_NOTE = (
 )
 
 
+def named_new_value(content: str) -> str:
+    """``content`` with its no-match sentence replaced by the one naming the new value."""
+    return content.replace(_NONE_FOUND, FORGET_NEW_VALUE, 1)
+
+
 def _text(call: ToolCall) -> str:
     """The text the call names, stripped; empty when the argument is missing or not a string."""
     value = call.arguments.get("text")
diff --git a/brain/packages/core/src/cortex_core/forget_new_value.py b/brain/packages/core/src/cortex_core/forget_new_value.py
new file mode 100644
index 000000000..e0d5dbbd6
--- /dev/null
+++ b/brain/packages/core/src/cortex_core/forget_new_value.py
@@ -0,0 +1,34 @@
+"""Read whether a forget call named the new value a message gives rather than the old one."""
+
+import re
+
+_WORD = re.compile(r"[\w']+")
+_NEW = frozenset({"now", "new"})
+# The word just before a stated value: "is now 0699000000", "new number is 0699000000".
+_LEADS = frozenset({"now", "is", "are", "to"})
+_BETWEEN = 3
+_FORGET_OLD = re.compile(
+    r"(?:^|[,;:.!?]\s*|(?<!\bI\s)(?<!\bwe\s)\b(?:and|so|but|then|also|just|please)\s+"
+    r"|\b(?:can|could|would|will)\s+you\s+)(?:please\s+)?"
+    r"(?:delete|forget|remove|erase|drop|clear|wipe)\s+(?:[\w']+\s+){0,2}?"
+    r"(?:old|previous|former|earlier|prior)\b",
+    re.IGNORECASE,
+)
+
+
+def _words(text: str) -> list[str]:
+    """The words of ``text``, lowercased, without punctuation."""
+    return [word.lower() for word in _WORD.findall(text)]
+
+
+def states_new_value(text: str, query: str) -> bool:
+    """Whether ``query`` states ``text`` as a new value and asks to forget the old one."""
+    said, value = _words(query), _words(text)
+    if not value or _FORGET_OLD.search(query) is None:
+        return False
+    return any(
+        said[at : at + len(value)] == value
+        and said[at - 1] in _LEADS
+        and not _NEW.isdisjoint(said[max(at - _BETWEEN - 1, 0) : at])
+        for at in range(1, len(said) - len(value) + 1)
+    )
```

The reader tables of `test_forget_new_value.py`, where `_N01`, `_N02`, `_V01` and `_M05` are the
rows' messages:

```python
@pytest.mark.parametrize(
    ("query", "text"),
    [
        (_N01, "0699000000"),
        (_N02, "0699000000"),
        (_M05, "0699000000"),
        ("Remember that my new locker code is 8426, and forget the old code.", "8426"),
        ("My phone number is now 0699000000. Please delete the old one.", "0699000000"),
        ("Could you remove my previous number? It is now 0699000000.", "0699000000"),
        ("My city is now changed to Graz, so drop the old one.", "Graz"),
    ],
)
def test_a_value_stated_as_new_beside_a_request_to_forget_the_old_one_is_read(
    *, query: str, text: str
) -> None:
    assert states_new_value(text, query) is True


@pytest.mark.parametrize(
    ("query", "text"),
    [
        (_V01, "0699000000"),
        ("Forget that my new passport number is 5551234.", "5551234"),
        ("My phone number is now 0699000000, and I always forget the old one.", "0699000000"),
        ("My phone number is now 0699000000; I deleted the old one.", "0699000000"),
        ("My number is now 0699000000, but I just forget the old one.", "0699000000"),
        ("Our code is now 0699000000, and we also forget the old one.", "0699000000"),
        ("Did you delete the old one? My number is now 0699000000.", "0699000000"),
        ("Forget the old list and tell me now what 0699000000 is.", "0699000000"),
        ("I got a new phone today, my number is 0699000000, so forget the old one.", "0699000000"),
        ("0699000000 is my number now, so delete the old one.", "0699000000"),
        (_N02, "phone"),
        (_N02, "phone number"),
        (_M05, "0612345678"),
        (_N01, ""),
        (_N01, "0699000001"),
    ],
)
def test_a_near_miss_is_not_read_as_a_new_value(*, query: str, text: str) -> None:
    assert states_new_value(text, query) is False
```
