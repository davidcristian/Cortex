# Per-remote-tool trust and gating overrides

**Status:** declined 2026-09-02
**Area:** untrusted-content
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)

Trust is fail-closed `UNTRUSTED` and `gated` is
per-`ToolSpec`; a genuinely trusted or gated *remote* MCP tool would need a composition-root
overlay onto the spec. None exists now.

## Trail

- 2026-07-19: The index recorded this as one piece of work counted twice, here and as trust
  overlays for remote tools in [email-confirmer.md](../index.md#email-confirmer), both waiting on the
  one thing, so the sum over the index table counts it twice until it lands or is declined.
- 2026-09-02: Declined, in the ADR-0013 own-text addendum, which reached this entry while
  deciding [319](319-a-refusal-taints-the-turn.md). It had waited on a genuinely trusted or
  gated remote MCP tool existing to overlay onto its spec, and the two halves ended differently. The gating
  overlay has existed since ADR-0022 as `GatedToolRegistry`, stamping `send_email` gated at the
  composition root, so that half was satisfied long before this was read. The trust half is
  refused by the rule recorded there: a result is re-stamped trusted only on byte equality with
  text the brain holds, never on the name of the tool it came through, because a tool's name is
  the sidecar's identity and not the brain's knowledge of the bytes. A remote tool whose every
  answer should be trusted belongs in the brain's own process as a built-in, where every trusted
  tool already lives. The content-keyed overlay that does exist under the rule is
  [530](530-a-sidecars-own-text-is-re-stamped-trusted.md).
