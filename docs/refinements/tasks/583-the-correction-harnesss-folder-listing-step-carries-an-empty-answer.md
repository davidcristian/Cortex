# The correction harness's folder listing step carries an empty answer

**Status:** open, actionable
**Area:** orchestrator
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)

Opened 2026-09-06 by the close of
[571](571-the-cortexs-reading-of-the-uid-description-is-unmeasured.md), whose harness was written
in the shape of `test_unfenced_correction_live.py` and could not reuse that file's session.

`_ServerSession.call_tool` in `brain/packages/orchestrator/tests/test_unfenced_correction_live.py`
discards the call and answers an empty text block:

    async def call_tool(self, name, arguments=None):
        del name, arguments
        return CallToolResult(content=[TextContent(type="text", text="")])

`sidecar_answer` invokes through that session, so it returns `""` for every call. The dialect
row's one step is `list_folders` answered by `sidecar_answer`, and its docstring says the answer
is "the sidecar's own, read back through the real adapter and fenced as the untrusted mailbox
content it is". Confirmed by running that function against the module as it stands: the answer is
the empty string. So the row that measures which dialect the cortex writes its first query in
hands the model a folder listing with no folders on it, where the module comment above `_FOLDERS`
argues at length for offering a real account's eight so that the choice of INBOX is not something
the context already settled.

The two other rows are unaffected: they compose their answers from `SEARCH_REFUSED` and
`FOLDER_UNKNOWN` directly and never call `sidecar_answer`.

**What would close it.** The session dispatching to the server it holds, which is three lines and
is what `test_own_texts.py`'s session of the same name already does, plus a redraw of the dialect
row, since its published count was measured with an empty listing in the turn. Whether the count
moves is the question: a model that named INBOX because it is the obvious folder will name it
again, and a model that named it because it was the only one on a list it could not see may not.

## Trail

- 2026-09-06: opened by the close of
  [571](571-the-cortexs-reading-of-the-uid-description-is-unmeasured.md), which found the stub
  while reading that file for the shape of its own harness.
