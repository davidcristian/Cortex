# Sidecar-declared sender

**Status:** done 2026-07-16
**Area:** untrusted-content
**Origin:** [ADR-0027](../../adr/ADR-0027-turn-provenance.md)

An MCP sidecar can now declare who sent the content it returns, recorded as
[ADR-0027 decisions 9 and 10](../../adr/ADR-0027-turn-provenance.md).

The email `read_email` tool returns a `CallToolResult` whose single text block is the readable
message and whose `_meta["cortex/source"]` holds `{"kind": "sender", "value": <From>}`.
`McpToolRegistry.invoke` reads that key into `ToolResult.source`, and `TaintLedger.observe`
notes it beside the attested `TOOL` source. `_meta` is the wire contract between the two sides,
because the email sidecar cannot import the core.

A declaration is written by the attacker's own content, since a `From` header is the sender's to
set. So `claimed_source` in the pure core accepts only a claimed `SourceKind` (`SENDER` or
`URI`) and drops any attested kind a hostile sidecar might name, and it sanitizes and bounds the
value through `Provenance`. `observe` marks taint from `result.trust` before it notes any
source, so a declared source can only annotate a turn and never reduce its taint. Tested live
against the real email sidecar in Docker over ProtonMail Bridge.

The entry had said a result's `_meta` was unreachable. That was wrong: with the shipped MCP SDK
(1.28.1), `CallToolResult.meta` is readable through `mcp.ClientSession.call_tool`, and a FastMCP
tool can set it by returning a `CallToolResult`. Only the ADR's preferred channel,
`structuredContent`, has the problem the entry described, because it replaces the readable text.

Nothing reads `SENDER` or `URI` provenance yet. The `URI` kind uses the same channel, and its
producer arrives with a fetch tool, which does not exist.

## History

- 2026-07-16: Opened as one of the two halves the `TurnStamp` provenance change could not
  cover, and closed the same day.
