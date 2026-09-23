# Trust overlays for remote tools

**Status:** satisfied 2026-09-09
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

A way to mark a remote tool's output as trusted, waiting on a remote tool that needed to be trusted
rather than merely confirmed. One arrived and the overlay was built.

## History

- 2026-07-15: Extracted from the roadmap's deferred-refinements section.
- 2026-07-19: Recorded as one piece of work counted twice, this entry and the untrusted-content
  area's per-remote-tool trust and confirmation overrides both waiting on the same thing, that no
  trusted remote tool exists. [untrusted-content.md](../index.md#untrusted-content) has the same
  note.
- 2026-09-09: Satisfied. The consumer arrived on 2026-09-02: four answers the email sidecar composes
  without reading a message needed to reach the model untainted, and
  [530](530-a-sidecars-own-text-is-re-stamped-trusted.md) built the overlay that does it.
  `OwnTextToolRegistry` in `brain/packages/core/src/cortex_core/own_text.py` is the composition-root
  trust overlay for remote tools, beside `ConfirmRequiredToolRegistry` and wired once over the shared root in
  `build_tool_registry` (`brain/packages/orchestrator/src/cortex_orchestrator/builders.py`) over the
  five declarations in `own_texts.py`. The twin entry
  [079](079-per-remote-tool-trust-overrides.md) closed the same week and settles the shape: the
  confirmation half had existed since `ConfirmRequiredToolRegistry`, and the trust half is keyed by the bytes
  the brain holds rather than by the name of the tool that returned them, since a tool's name is the
  sidecar's identity and not the brain's knowledge of its content. So the per-tool form is refused
  rather than pending.
