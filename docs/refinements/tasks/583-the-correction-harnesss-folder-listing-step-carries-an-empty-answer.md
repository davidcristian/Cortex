# The correction harness's folder listing step carries an empty answer

**Status:** landed 2026-09-06
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
- 2026-09-06: landed. The session dispatches to the server it holds, which is the three lines
  `test_own_texts.py`'s session of the same name already had, and the same call now answers with
  the eight folders `_FOLDERS` names where it answered `''`. The dialect row was redrawn on the
  same twenty seeds: 19 of 20 raw against the published 10 and 9, still 0 client syntax, and the
  repeat `list_folders` the empty listing had produced fell from 10 of 20 to 1. The reading the
  published addendum took from those repeats, a model asking again with the list in front of it,
  is withdrawn in the ADR-0013 addendum of that date.
