# A sidecar's own text is re-stamped trusted by the brain, on bytes this repo contains

**Status:** done 2026-09-02
**Area:** untrusted-content
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)

An untrusted-by-default tool result is re-stamped `Trust.TRUSTED` only by the brain, in a
composition-root overlay, and only when its whole content is byte-equal to text this repo has in
code under review, rendered with the argument the brain itself put on the call. Nothing from the
wire takes part: `isError` is not read, `_meta` is not read, and a result with an image or one byte
beyond the expected text stays untrusted. ADR-0013 decision 10 has the threat model and the reasons
the two wire-based alternatives were rejected.

What it changes for a user: a `search_emails` the sidecar refused (a malformed query, a folder no
mailbox has), an empty search, and a `read_email` of a uid that is not there each stop tainting the
turn, so a `send_email` after one of them reaches the confirmation card instead of `DENIED_MSG`, and
the correction reaches the model unfenced.

The pieces: a core overlay beside `GatedToolRegistry`, `OwnTextToolRegistry(inner, own=...)`, whose
`describe_tools` delegates untouched and whose `invoke` re-stamps a result whose content equals the
string one `OwnText` renders from the call's `arguments`; wiring once over the root in
`build_tool_registry` (`cortex_orchestrator/builders.py`), keyed by tool name; the four expected
texts declared in the orchestrator, restating `SEARCH_REFUSED` and `FOLDER_UNKNOWN` from
`cortex_email/values.py` and the two literal answers in `cortex_email/server.py`, with a
`crosscheck.py` entry comparing each restatement with its declaration; a contract test over the fake
and the real `McpToolRegistry`; and updates to `docs/modules/brain-core.md`,
`brain-orchestrator.md`, `brain-tools.md` and the tools runbook.

## History

- 2026-09-02: opened by the close of [319](319-a-refusal-taints-the-turn.md), which recorded the
  decision at ADR-0013 and stopped short of the build.
- 2026-09-02: closed, as ADR-0013 decision 10 states. `OwnTextToolRegistry` and `OwnText` in
  `cortex_core/own_text.py`, wired outermost over the shared root in `build_tool_registry` over
  `EMAIL_OWN_TEXTS` (`cortex_orchestrator/own_texts.py`), which declares all four answers in the
  first version. The contract runs over the fake and the real `McpToolRegistry`, and the end-to-end
  test drives the real sidecar through `FastMCP.call_tool` into the real adapter. Two of the entry's
  premises did not hold: `crosscheck.py` could not read either refusal sentence, which is a
  parenthesized run of literals, so the reducer gained that form (ADR-0042), and its suite's rule
  that every entry span two languages had to learn that two brain packages which cannot import each
  other are a boundary too. Through the real adapter an image block is dropped before the overlay
  sees the result, filed as [532](532-an-mcp-image-block-is-dropped-by-the-adapter-rather-than-passed.md); whether
  the shipped cortex follows the now-unfenced correction, and the same path against a real Bridge,
  are filed as [533](533-the-unfenced-correction-is-unmeasured-on-the-cortex.md).
