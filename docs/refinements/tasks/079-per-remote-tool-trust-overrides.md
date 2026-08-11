# Per-remote-tool trust and gating overrides

**Status:** open, dead until a consumer
**Area:** untrusted-content
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)
**Trigger:** a genuinely trusted or gated remote MCP tool existing to overlay onto its spec.

Trust is fail-closed `UNTRUSTED` and `gated` is
per-`ToolSpec`; a genuinely trusted or gated *remote* MCP tool would need a composition-root
overlay onto the spec. None exists now.

## Trail

- 2026-07-19: The index recorded this as one piece of work counted twice, here and as trust
  overlays for remote tools in [email-confirmer.md](../index.md#email-confirmer), both waiting on the
  one thing, so the sum over the index table counts it twice until it lands or is declined.
