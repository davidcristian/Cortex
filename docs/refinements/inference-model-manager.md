# Inference & Model Manager

Deferrals from the Slice 4 inference work, whose origin decision is
[ADR-0007](../adr/ADR-0007-model-manager-inference.md); the reasoning-status entry carries its own
decision record in [ADR-0020](../adr/ADR-0020-reasoning-status.md). Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the
historical record of what each deferral became, and the index at [index.md](index.md) carries the
recommended pickup order.

**Open items:** model-manager process lifecycle, co-residency, and real swap; MTP model variants, disable-thinking / token-budget capping

**Inference / Model Manager in Slice 4 ([ADR-0007](../adr/ADR-0007-model-manager-inference.md)):**
- **`cortex_model_manager` process lifecycle, co-residency, real swap.** The pure
  single-resident manager exists now; process I/O and swap land in **Slice 11** behind the
  unchanged `ModelManager` port (consequences).
- **MTP (multi-token-prediction) model variants.** Deferred until they earn their keep, per
  [ADR-0004](../adr/ADR-0004-model-lineup.md).
- **The cortex reasoning trace is surfaced as a thinking status. This landed 2026-07-06
  ([ADR-0020](../adr/ADR-0020-reasoning-status.md)).** The cortex (gemma-4-12B) emits
  `reasoning_content` before `content` (found during the Slice 6.5 GPU validation), and thinking
  stays on for it; `LlamaCppBackend` used to read only `content`, so a long deliberation streamed
  nothing until it concluded. The chosen option (of disable-thinking / surface / token-budget) is
  **surface**: `ReasoningChunk` joins the `InferenceEvent` union, the shared `stream_tool_loop`
  yields `str | ReasoningDelta` (reasoning ephemeral, never persisted or fed back), and the engine
  maps it to a domain `StatusUpdate(state="thinking", …)` → the wire `ServerEvent.status` the
  proto/body/overlay already carried but the brain never emitted. CI-gated end to end over the
  fakes; **host-validated via Docker (agent, 2026-07-06, [ADR-0020 addendum](../adr/ADR-0020-reasoning-status.md)):**
  live gemma-4-12B streamed a real reasoning trace surfaced as 326 `StatusUpdate(state="thinking")`
  events, reply clean and persisted==shown (integration test `test_reasoning_model_emits_reasoning_before_reply`).
  **The output guardrail over reasoning status landed 2026-07-12
  ([ADR-0020 addendum](../adr/ADR-0020-reasoning-status.md)):** the inline chips (see [body-overlay.md](body-overlay.md)) gave the
  thinking status a rendered surface, so a laundered URL in the reasoning trace had a display
  channel the reply-side guardrail never inspected. The trace now streams through its own second
  `OutputFilter` under the same policy and user-URL allowlist (`output_channels.py`, an engine
  line-cap split): a `ThinkingChannel` scrubs each delta (a wholly-carried one emits no status),
  its carry surviving tool steps between thinking bursts so a URL split around a dispatch is
  joined before matching (an adversarial multi-agent review caught the per-burst-flush variant
  letting a fragmented URL cross the seam), released once at end of stream. Redact +
  strict modes and the obfuscation-resistant grammar are inherited; no new config, no seam
  change; reasoning stays ephemeral. Remaining behind the same
  `InferenceBackend`/`TurnCapabilities` seams (ADR-0020 deferred):
  the **disable-thinking / token-budget** alternatives (still available if a runaway trace needs
  capping) and **reasoning persistence/summarization**. **`state`-aware overlay treatment landed
  2026-07-13 ([ADR-0020 third addendum](../adr/ADR-0020-reasoning-status.md)):** the reducer now
  keeps the status event's `state` (a new `Message.statusState`) and a `"thinking"` chip renders
  distinctly (a `chip-think` modifier: the reasoning bob on its dot, an accent label, an aria
  label) from a generic status or tool chip, entirely in the CI-gated overlay tree with no seam
  change (the `state` field already rode the wire). A richer collapsed "thoughts" section stays
  open behind the same field. **The collapsed "thoughts" section landed and reasoning
  persistence/summarization was declined on 2026-07-16, both without a seam change ([ADR-0020
  fourth addendum](../adr/ADR-0020-reasoning-status.md)):** the reducer now also concatenates every
  scrubbed thinking delta into a new `Message.thoughts`, and the settled reply renders it as a
  collapsed `<details>` disclosure above the bubble, the chip's retrospective counterpart
  (`overlayState.ts` + `Message.tsx`, gated + browser-validated in both themes). Persisting or
  summarizing the trace stays **declined for want of a consumer**: nothing reads a stored trace,
  re-display on reload needs a `GetSessionMessages` reasoning field (the read path the open-chat
  title-consistency entry independently needs widened) and the store to grow by the observed
  ~13,882-char single-turn scale, and summarization reverses this ADR's "never fed back" while
  re-raising the non-reentrant GPU-lease sequencing the title generator navigates. It moves to
  this backlog's dead-until-a-consumer list and reopens the day either consumer appears.
