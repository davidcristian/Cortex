# Trust and confirmation overrides for a remote tool

**Status:** declined 2026-09-02
**Area:** untrusted-content
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)

Trust is fail-closed `UNTRUSTED`, and each `ToolSpec` sets its own `gated` flag. Giving one
remote MCP tool a different trust level or a different confirmation rule would need an overlay
applied to its spec at the composition root. None exists.

## History

- 2026-07-19: The index recorded this as one piece of work counted twice, here and as trust
  overlays for remote tools in [email-confirmer.md](../index.md#email-confirmer), so the sum
  over the index table counted it twice.
- 2026-09-02: Declined in ADR-0013 decision 10, reached while deciding
  [319](319-a-refusal-taints-the-turn.md). The two halves ended differently. The confirmation
  overlay has existed since ADR-0022 as `GatedToolRegistry`, which marks `send_email` at the
  composition root. The trust half is refused: a result is marked trusted again only when its
  bytes match text the brain already holds, never because of the name of the tool it came
  through, since a tool's name is the sidecar's identity and not the brain's knowledge of the
  bytes. A remote tool whose every answer should be trusted belongs in the brain's own process
  as a built-in, where every trusted tool already lives. The content-keyed overlay that does
  exist under that rule is [530](530-a-sidecars-own-text-is-re-stamped-trusted.md).
