# Trust overlays for remote tools

**Status:** satisfied 2026-09-09
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Trust overlays for remote tools were the other half of the ADR-0013 deferral, waiting on a remote
tool that needed to be TRUSTED rather than merely gated. One arrived and the overlay was built.

## Trail

- 2026-07-15: extracted from the ROADMAP's deferred-refinements section with the entry kept
  verbatim.
- 2026-07-19: the index recorded that this thread and the untrusted-content area's
  per-remote-tool trust and gating overrides are one piece of work counted twice, both waiting on
  the same one thing, that no trusted remote tool exists. It was noted rather than decremented,
  the same treatment the two earlier cross-area threads got, so until it lands or is declined the
  sum over the index table counts it twice, and the pickup-order bullet points at both docs.
  [untrusted-content.md](../index.md#untrusted-content) carries the same thread.
- 2026-09-09: satisfied. The consumer this waited on arrived on 2026-09-02: four answers the email
  sidecar composes without reading a message needed to reach the model unfenced, and
  [530](530-a-sidecars-own-text-is-re-stamped-trusted.md) landed the overlay that does it.
  `OwnTextToolRegistry` in `brain/packages/core/src/cortex_core/own_text.py` is the
  composition-root trust overlay for remote tools, sitting beside `GatedToolRegistry` and wired
  once over the shared root in `build_tool_registry`
  (`brain/packages/orchestrator/src/cortex_orchestrator/builders.py`) over the five declarations in
  `own_texts.py`. The twin entry
  [079](079-per-remote-tool-trust-overrides.md) was closed the same week and settles the shape this
  one is satisfied in: the gating half had existed since `GatedToolRegistry`, and the trust half is
  keyed by the bytes the brain holds rather than by the name of the tool that returned them, a
  tool's name being the sidecar's identity and not the brain's knowledge of its content. So the
  overlay this asked for exists, and the per-tool form of it is refused rather than pending.
  Recorded in the ADR-0022 addendum of the same day.
