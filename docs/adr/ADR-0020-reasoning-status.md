# ADR-0020: Surface the cortex's reasoning as a live "thinking" status

- **Status:** Accepted (Slice 4 reasoning-model deferral, landed 2026-07-06)
- **Date:** 2026-07-06

## Context

The resident cortex, gemma-4-12B, is a **reasoning model**: over its OpenAI-compatible stream it
emits `choices[0].delta.reasoning_content` (its private deliberation) *before* the
`delta.content` that is the reply. This was found during the Slice 6.5 GPU validation
([ADR-0013 addendum](ADR-0013-untrusted-content.md)) and recorded as a Slice-4 deferral:
`LlamaCppBackend` reads only `content`, so a delta carrying only `reasoning_content` is silently
dropped. The cortex compose, unlike the subagent tier, does **not** pass `enable_thinking=false`,
so a long deliberation streams *nothing* to the overlay until it concludes. That is acceptable for
an ordinary prompt, but under a long deliberation the overlay appears frozen.

The deferral named three options behind the unchanged `InferenceBackend`: (a) disable thinking for
the cortex (the subagent twin), (b) **surface `reasoning_content` as a "thinking" status**, or (c)
budget enough tokens. This ADR picks (b), because the rest of the status path is already built and
never exercised: the proto has `ServerEvent.StatusUpdate{state, detail}` (Slice 2), the body's
`body_rpc` adapter maps it to `TurnEvent::Status`, and the overlay reducer folds a `status` event
into the streaming message (the "thinking" affordance in [overlay-ux.md](../design/overlay-ux.md)).
The brain is the **only** side that never emits a `StatusUpdate`. Surfacing reasoning fixes the
silent-think problem, because progress becomes visible during deliberation, and it exercises that
path end to end. Option (a) would hide the reasoning and option (c) does not address opacity.
Thinking stays **on** for the cortex, and the trace is shown rather than suppressed.

## Decision

1. **`ReasoningChunk(text)` joins the `InferenceEvent` union (`inference.py`).** The union grows
   `TextChunk | ReasoningChunk | ToolCall`; the `InferenceBackend.stream` **signature is
   unchanged** (additive, the same way ADR-0009 grew the union with `ToolCall`). `LlamaCppBackend`
   reads `delta.reasoning_content` alongside `delta.content`, validates each as string-or-absent
   with the same fail-loud stance as `content` (a non-string fails the turn, never a silent drop),
   and yields any reasoning **before** any text within a chunk (mirroring the model's own order).

2. **The shared tool loop yields `str | ReasoningDelta` (`tool_loop.py`).** Reply text stays a bare
   `str` (no caller churn on the text path); reasoning is a new loop-vocabulary sentinel
   `ReasoningDelta(text)`, translated from `ReasoningChunk` just as text is translated from
   `TextChunk`. **Reasoning is ephemeral:** it is *not* appended to the step's assistant text and
   *not* written into any `Role.ASSISTANT`/`working` message, so it never re-enters the model's
   context on a later tool-loop step and is never persisted. It can arrive on any inference step
   (including re-inference after tool results), so a multi-step turn may surface several thinking
   bursts.

3. **The engine maps reasoning to a domain `StatusUpdate` (`events.py`, `engine.py`).** A new pure
   domain event `StatusUpdate(state, detail)` mirrors the proto (general by design, since the proto
   comment lists model-swap/queue-position as future uses; Slice 11 reuses it). `TurnEvent` becomes
   `TextDelta | StatusUpdate | TurnCompleted`. The engine yields
   `StatusUpdate(state="thinking", detail=<reasoning text>)` for each `ReasoningDelta`, **bypassing
   the output guardrail and `parts`** (reasoning is not the reply): it is neither filtered as reply
   text nor accumulated into `full_text` nor recorded to memory. The per-turn event contract
   becomes: zero or more `TextDelta`/`StatusUpdate`, interleaved, then exactly one `TurnCompleted`.

4. **The orchestrator maps the domain event to the wire (`converse.py`).** `_to_server_event` gains
   a `StatusUpdate` → `ServerEvent(status=StatusUpdate{state, detail})` arm, aliased
   `DomainStatusUpdate`/`WireStatusUpdate` exactly as the existing `TextDelta` pair is. The body and
   overlay are unchanged, since they already carry and render it.

5. **Subagents drop reasoning (`runner.py`).** The subagent tier runs `enable_thinking=false`
   (ADR-0010) and has no status channel; the `SubagentRunner` ignores a `ReasoningDelta` rather
   than folding it into the answer. Defensive (no reasoning is expected there) but keeps one loop
   contract for both callers.

## Consequences

- The overlay shows the cortex thinking, token by token, during a long deliberation instead of a
  frozen panel; the pre-existing proto/body/overlay status path is now exercised end to end.
- The change is invisible to every non-reasoning path: `EchoInferenceBackend` and any backend that
  yields no `reasoning_content` produce exactly the prior events; a bare `TurnCapabilities()` turn
  is unaffected. The only new events appear when a backend actually streams reasoning.
- Alternatives (a) disable-thinking and (c) token-budget remain available behind the same unchanged
  `InferenceBackend`/`TurnCapabilities` seams. This decision does not foreclose also capping think
  tokens later if a runaway trace becomes a problem.

## Risks

- **Reasoning is model output shown transiently.** It is the same trust level as the reply (both are
  the model's own tokens, not verbatim tool content), surfaced as status and never persisted. The
  output guardrail (ADR-0015) scrubs laundered untrusted URLs from the *reply*; it does not run over
  the reasoning status. A model could in principle echo an injected URL into its reasoning trace, which
  the overlay would display transiently. Extending the guardrail over reasoning status is deferred
  below. The guardrail's streaming `feed` is built around the single reply stream, and reasoning is
  ephemeral and unpersisted, so v1 keeps it out of scope deliberately.
- **Event volume.** Each reasoning delta is one `StatusUpdate`, counted against the bounded
  `Converse` output queue (`CORTEX_SEAM_CONVERSE_BUFFER`, ADR-0014 backpressure). A verbose think
  produces many small events; the credit bound already caps memory and stalls generation if the
  consumer lags, so this needs no new limit.
- **`state` is advisory.** The overlay first rendered `detail` regardless of `state`; the
  `"thinking"` marker was informational until the overlay distinguished status kinds. It now
  does (third addendum below): the reducer keeps `state` and the chip branches on it.

## Deferred (behind the unchanged `InferenceBackend` / `TurnCapabilities` / tool-loop seams)

- **Output guardrail over reasoning status landed 2026-07-12** (second addendum below): the
  overlay's inline chips gave the thinking status a rendered surface, so the deferral's "if
  displaying reasoning proves an exfiltration surface" condition came true.
- **`state`-aware overlay treatment landed 2026-07-13** (third addendum below): a `"thinking"`
  status chip now renders differently from a generic status or tool chip, with its dot on the
  reasoning bob animation and its label tinted with the accent. **The richer collapsed "thoughts"
  section landed 2026-07-16** (fourth addendum below), over the same reducer field.
- **Disable-thinking / token-budget alternatives** stay available for the cortex behind the same
  seams if a runaway trace or latency floor argues for capping rather than only surfacing.
- **Reasoning persistence / summarization declined 2026-07-16** (fourth addendum below): keeping a
  turn's reasoning past the live status is a separate concern with no consumer yet, and reverses
  this ADR's "never persisted, never fed back". It reopens the day a reload re-display or a
  summarization consumer appears.
- **Injection-harness run against the ~31B brain tier** is unchanged; still opt-in and tied to the
  Slice 11 brain pick (ADR-0013 harness addendum).

## Addendum (2026-07-06): host-validated live against gemma-4-12B

Agent-run on the host GPU via Docker (native WSL2 `dockerd`, CDI `nvidia.com/gpu=all`; the
`server-cuda` image cached, model at `/srv/models`, [runbook](../runbooks/llamacpp-gpu.md)).
Brought up only `llama-cortex` (gemma-4-12B, `-ngl 99`, 16K ctx, ready in ~36-42 s) and drove the
**real** `LlamaCppBackend` and the full `TurnEngine` from the host against `127.0.0.1:8080` with a
reasoning-inducing prompt (the bat-and-ball trap):

- **Adapter layer.** The model streamed `reasoning_content` (its step-by-step algebra, correctly
  landing on the counter-intuitive $0.05) surfaced as `ReasoningChunk`, then the reply as
  `TextChunk`, both non-empty, thinking first. The prior silent-drop is gone.
- **End to end.** `TurnEngine.handle_turn` emitted **326 `StatusUpdate(state="thinking")`** events
  and 164 `TextDelta` events, then one `TurnCompleted`; every status state was `"thinking"`, the
  reasoning did **not** leak into the reply, and `full_text == streamed reply text` (persisted ==
  shown). The reply correctly answers $0.05.

Captured as the reproducible integration test `test_reasoning_model_emits_reasoning_before_reply`
in `packages/inference/tests/test_backend_live.py` (both live tests green: `2 passed`). Re-runnable
per the runbook. The CI half remains proven over the fakes; this confirms the live model exercises
the same path.

## Addendum (2026-07-12): the output guardrail now covers the reasoning status

When this ADR landed, the thinking status had no visible surface, so bypassing the guardrail
was deliberate v1 scope (risk 1). The overlay's inline chips (the Slice-8 design-gap closure,
ADR-0011 addendum) changed that: the reducer folds any status `detail` into the streaming
message and the chip renders it verbatim. On a tainted turn, injected content can steer the
cortex's reasoning to include a URL, which then streamed to the overlay unredacted, exactly
the display channel the `ToolActivity` event was built to never open (its fields are
registry-authored for this reason, ADR-0009 addendum). The deferral's condition ("if displaying
reasoning proves an exfiltration surface") was therefore met.

The reasoning trace now passes through the guardrail as **its own stream**. A new
`cortex_core/output_channels.py` (an engine line-cap split) holds:

- `ThinkingChannel`: wraps an optional second `OutputFilter`. `feed` maps one reasoning delta
  to the `StatusUpdate` to show now (a wholly-carried delta emits no event, never an empty
  detail, and an empty delta from the port is dropped on the unguarded path too); `release`
  drains the scrubbed carry exactly once, at end of stream, so a held tail is never dropped
  without being shown. One turn's trace is **one stream**: the carry deliberately survives tool steps
  and reply deltas between thinking bursts, mirroring the reply filter's own carry. The first
  cut flushed at every burst boundary instead ("complete by termination"), and an adversarial
  multi-agent review reproduced the consequence: a flagged URL steered to straddle a
  think→tool→think boundary was scrubbed as two fragments, neither matching the collected
  identity, so the full URL crossed the seam in consecutive statuses (unrendered today only
  because the overlay chip replaces its detail per event). Joining across bursts closes that;
  the cost is that a held fragment shows slightly later, joined to the burst that completes it.
- `open_output_channels`: opens the reply filter and the thinking channel under the **same**
  policy and user-URL allowlist (quoting the user's own link back in the trace is not
  laundering), one filter instance each, so the two carry buffers stay independent. A URL
  split across the reply/thinking boundary renders as a whole on neither surface; each stream
  is scrubbed on its own terms.

Redact and strict modes (ADR-0015 + addenda) and the whole obfuscation-resistant URL grammar
are inherited unchanged; there is no new configuration, since a deployment that guards the
reply now guards the trace under the same `CORTEX_OUTPUT_GUARDRAIL` knob. Reasoning remains
ephemeral: never part of `full_text`, never persisted, never fed back. No seam change (the
`OutputGuardrail`/`OutputFilter` protocols, `TurnCapabilities`, the proto, body, and overlay
are all untouched). CI-gated at 100% line+branch over the fakes in the engine suite (redact,
strict, split-across-deltas, the cross-burst straddle around a live dispatch, end-of-stream
release, user-allowlist, empty-delta drop, clean turn). The scrub is deterministic post-model
filtering, so no live-model validation is needed beyond the existing addendum above.

## Addendum (2026-07-13): the overlay treats a thinking status distinctly

The `state`-advisory deferral closes on the overlay side. When the inline chips landed, the
reducer folded a status event's `detail` into the streaming message but dropped its `state`, so
a `"thinking"` status rendered identically to a generic status or a tool-activity chip: the
marker the engine already emitted had no consumer. It does now, entirely in the CI-gated React
overlay tree (vitest), with no seam, proto, brain, or Rust change (the `state` field already
rode the wire since ADR-0011 and `converse.rs` already mapped it).

- **The reducer keeps `state`.** `Message` gains `statusState: string | null`, and the `status`
  event fold stores `event.state` alongside `event.detail`. It is `null` until a status lands
  and rides the same per-turn lifecycle as `status` (dropped when the turn settles).
- **The chip branches on it.** A status chip whose `statusState === "thinking"` renders with a
  `chip-think` modifier and an aria-label of "Thinking"; every other status stays the plain
  neutral pill. In CSS, `chip-think` swaps the steady tool `pulse` on the leading dot for the
  reasoning `think` bob (the same keyframe the pre-first-token bubble shimmer uses) and tints
  the label with the accent, so a thinking chip is visually distinct from an action chip. Color
  is still used only in the working states.

This is intentionally the minimal state-aware treatment; a richer collapsed "thoughts" section
remains open behind the same `statusState` field. CI-gated at 100% over the overlay suite (the
reducer folds `statusState`, the thinking chip carries `chip-think` + the label, a non-thinking
status stays plain); the pixel-level look rides the same browser/user validation as the rest of
the overlay design language.

## Addendum (2026-07-16): the collapsed thoughts section landed; reasoning persistence declined

The two remaining reasoning deferrals closed as two different outcomes, entirely without a seam
change. The richer collapsed section is now the settled counterpart of the live chip; keeping the
reasoning past the turn (persisting or summarizing it) was **declined** for want of a consumer.

- **The collapsed "thoughts" section landed** (overlay only, gated, `overlayState.ts` +
  `Message.tsx`). The reducer already folded a thinking status's latest `detail` into `status` and
  dropped it when the turn settled; it now also concatenates every `"thinking"` delta, in order,
  into a new `Message.thoughts`. While the reply streams the live `chip-think` still shows the
  latest delta; once it settles, the chip drops and a collapsed "Thoughts" disclosure
  above the bubble holds the whole trace, so "what it was thinking" survives the turn as a
  retrospective the user opens on demand. Only one reasoning affordance is shown at a time: the
  chip covers the streaming phase and the disclosure the settled one, so the section renders only when
  `!streaming && thoughts !== ""`. The `state` field already rode the wire, so the proto, body,
  brain, and Rust are all untouched. **Privacy holds by construction:** each `detail` was already
  scrubbed by the `ThinkingChannel`'s `OutputFilter` (second addendum), so the section retains and
  re-shows only guardrail-passed text the chip already rendered, opening no new laundering channel;
  it is a plain text node, never linkified. Live-validated in headless Chromium (light + dark): the
  disclosure is absent while streaming, appears collapsed once settled with the chip gone, expands
  to the full scrubbed trace, and holds zero anchors.

  **It stopped being a `<details>` on 2026-07-20**, on the user's "there is no animation when
  expanding thoughts". Neither `<details>` nor `<summary>` can animate the content it reveals, so
  the trace appeared in one frame while the panel eased for 300ms behind it. It is now a real button
  carrying `aria-expanded` over the overlay's existing rolling section (`components/Thoughts.tsx`
  over `components/Collapse.tsx`, [ADR-0035](ADR-0035-console-and-motion.md) decision 14), which
  rolls the body open and shut over 300ms and brings the panel with it. Nothing about what is rendered
  changed: still one plain text node, still no markup parsed and no URL linkified.

- **Reasoning persistence / summarization was declined for want of a consumer.** The collapsed
  section is served entirely by the in-memory `thoughts` accumulation; nothing reads a *stored*
  reasoning trace. The two candidate consumers each cost more than an unchanged port and neither
  exists yet: **re-display on session reload** would need a reasoning field on the
  `GetSessionMessages` read path (a proto change plus store plumbing, the same read path the
  open-chat title-consistency entry independently needs widened) and the store to keep the trace,
  which the observed 13,882-char single-turn deliberation makes a real storage-growth decision;
  **summarization feeding future context** would reverse this ADR's deliberate "never fed back",
  and it is another inference call with the same non-reentrant GPU-lease sequencing the session
  title generator follows (run at turn end after the lease releases, never on a read path).
  Persisting reverses decision 2's "reasoning is ephemeral, never persisted"; that is a design
  change, not a cheap follow-on, and nothing today would read the result. It moves to the backlog's
  dead-until-a-consumer list and reopens the day a reload re-display or a summarization consumer
  appears, designed with the record the reader needs (`docs/refinements/index.md#inference-model-manager`).
