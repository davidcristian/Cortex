# The correction harness's folder listing step returns an empty answer

**Status:** done 2026-09-06
**Area:** orchestrator
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)

`_ServerSession.call_tool` in `brain/packages/orchestrator/tests/test_unfenced_correction_live.py`
discarded the call and answered an empty text block:

    async def call_tool(self, name, arguments=None):
        del name, arguments
        return CallToolResult(content=[TextContent(type="text", text="")])

`sidecar_answer` invokes through that session, so it returned `""` for every call. The dialect row's
one step is `list_folders` answered by `sidecar_answer`, and its docstring says the answer is the
sidecar's own, read back through the real adapter and fenced as untrusted mailbox content. Running
that function against the module as it stood returned the empty string. So the row that measures
which dialect the cortex writes its first query in handed the model a folder listing with no folders
on it, where the comment above `_FOLDERS` explains at length why a real account's eight are offered,
so that the choice of INBOX is not something the context already settled. The two other rows are
unaffected, since they build their answers from `SEARCH_REFUSED` and `FOLDER_UNKNOWN` directly.

## History

- 2026-09-06: opened by the close of
  [571](571-the-cortexs-reading-of-the-uid-description-is-unmeasured.md), which found the stub while
  reading that file for the shape of its own harness.
- 2026-09-06: done. The session now dispatches to the server it holds, which is the three lines
  `test_own_texts.py`'s session of the same name already had, and the same call answers with the
  eight folders `_FOLDERS` names. The dialect row was drawn again on the same twenty seeds: 19 of 20
  raw against the published 10 and 9, still 0 client syntax, and the repeat `list_folders` the empty
  listing had produced fell from 10 of 20 to 1. The conclusion the published reading drew from those
  repeats, a model asking again with the list in front of it, is withdrawn
  ([untrusted-framing](../../readings/untrusted-framing.md)).
