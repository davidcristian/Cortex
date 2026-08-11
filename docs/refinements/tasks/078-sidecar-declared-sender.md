# Sidecar-declared sender

**Status:** landed 2026-07-16
**Area:** untrusted-content
**Origin:** [ADR-0027](../../adr/ADR-0027-turn-provenance.md)

A sidecar-declared sender, recorded as the [ADR-0027 sidecar
addendum](../../adr/ADR-0027-turn-provenance.md), gave the claimed provenance kinds their first
producer and refuted the reachability blocker the entry above named.
**The blocker was false.** Read against the shipped MCP SDK (1.28.1): a result's
`_meta` IS reachable through the very client the registry uses (`CallToolResult.meta` on
`mcp.ClientSession.call_tool`), and a FastMCP tool CAN set it by returning a `CallToolResult`
(the low-level `call_tool` handler passes a returned `CallToolResult` straight through, and FastMCP
types a `-> CallToolResult` tool as "return without output-schema validation"), which was proven by
an in-memory client/server round trip: result-level `_meta` survives to the client with the readable
string untouched in the content blocks. So the only true constraint was the ADR's own preferred
channel, `structuredContent` (which does replace the readable text); `_meta` was there the whole time.
**The transport half:** the email `read_email` tool returns a `CallToolResult` whose single text block
is the same readable message and whose `_meta["cortex/source"]` declares `{"kind": "sender", "value":
<From>}`; the registry (`McpToolRegistry.invoke`) reads that key into a new `ToolResult.source`
(`_declared_source`), and the loop's `TaintLedger.observe` notes it beside the attested `TOOL` source.
The `_meta` key is a cross-deployable wire contract, since the email sidecar deliberately cannot import
the core. **The trust half:** a declaration is attacker-influenceable (a `From` header is the sender's
to write), so the pure-core `claimed_source` is the gate: it admits only a **claimed** `SourceKind`
(`SENDER`/`URI`), dropping any attested kind a hostile sidecar might name to forge a trusted-looking
label, and sanitizes/bounds the value through `Provenance` exactly like any other source; `observe`
marks taint from `result.trust` before noting any source, so a declared source only ever annotates and
can never downgrade the turn (mutation-proven: reverting the claimed-only gate lets a forged attested
kind through, reverting `observe`'s note drops the sender). Validated live end to end against the real
email sidecar in Docker over ProtonMail Bridge. **The consumer is still thin, honestly:** nothing reads
`SENDER`/`URI` provenance today (confirm-with-provenance stays declined, since a producer alone does not
reverse the fail-closed decision; per-provenance eviction wants `MemoryRecord` provenance first), but
the provenance *fields* were built ahead of their consumers on the same logic, and this completes them
symmetrically for the claimed kinds and unblocks that future work. The `URI` kind rides the identical
channel; its producer arrives with a fetch tool, which does not exist yet (feature breadth, not a
separate deferral). *Original deferred entry, kept verbatim as the historical record:* "**A
sidecar-declared sender/URI.** Needs the `ToolResult` widening plus a declaration channel that does not
disturb the model-facing text, per the paragraph above."

## Trail

- 2026-07-16: Opened as one of the two halves the `TurnStamp` provenance landing could not
  capture, then landed the same day, taking the area's count from 15 to 14 and refuting the
  blocker the entry had named for itself.
