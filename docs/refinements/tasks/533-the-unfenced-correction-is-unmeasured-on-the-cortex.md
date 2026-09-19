# The unfenced correction is unmeasured on the cortex, and the own texts are unrun against a Bridge

**Status:** done 2026-09-04
**Area:** untrusted-content
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)

The own-text overlay built by [530](530-a-sidecars-own-text-is-re-stamped-trusted.md) lets two email
refusals reach the model outside the fenced region the preamble tells it never to obey. Both
refusals are instructions: rewrite the query from the field description, and call `list_folders`
before naming a folder. Whether the shipped cortex follows them was never measured, inside the fence
or outside it.

The second half was the live path. The end-to-end test drives the real `cortex_email` server through
`FastMCP.call_tool` into the real `McpToolRegistry`, so the refusal is recognized in one process. It
had never run against the ProtonMail Bridge, where the search refusal starts as an IMAP `BAD` and
the folder refusal as a `NO`.

## History

- 2026-09-02: opened by the close of [530](530-a-sidecars-own-text-is-re-stamped-trusted.md).
- 2026-09-04: both measurements taken and recorded in
  [untrusted-framing](../../readings/untrusted-framing.md). On `gemma-4-12B` the unfenced correction
  is followed on 13 of 20 draws and the fenced one on 3 of 20, the same 3 of 20 a bare
  `MCP tool ... failed` message gets, so inside the fence the sentence changed nothing measurable.
  The test is `brain/packages/orchestrator/tests/test_unfenced_correction_live.py`: three variants
  including the bare-failure baseline, twenty draws each on the same seeds. Two of the entry's
  premises were wrong. The folder correction reads 20 of 20 in every variant, baseline included,
  because this model calls `list_folders` after any folder failure, so that row says nothing about
  framing. And the cortex never wrote a query in a mail client's syntax: over two runs of twenty it
  wrote raw IMAP criteria 10 and 9 times and client syntax 0 times, so the correction saves fewer
  retries than assumed. Against a live Bridge all five own answers come back trusted through
  `build_tool_registry`, the audit line reads `ok=False` beside `trust=trusted`, the taint ledger
  stays clean and a following `send_email` reaches the confirmation card
  (`test_own_texts_bridge_live.py`). One answer is unreachable on that server: a `read_email` in a
  folder with no mail raises instead of answering not-found, filed as
  [548](548-an-empty-folder-read-raises-instead-of-answering-not-found.md).
