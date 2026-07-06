# ADR-0020: Surface the cortex's reasoning as a live "thinking" status

- **Status:** Accepted (Slice 4 reasoning-model deferral, landed 2026-07-06)
- **Date:** 2026-07-06

## Context

The resident cortex, gemma-4-12B, is a **reasoning model**: over its OpenAI-compatible stream it
emits `choices[0].delta.reasoning_content` (its private deliberation) *before* the
`delta.content` that is the reply. This was found during the Slice 6.5 GPU validation
([ADR-0013 addendum](ADR-0013-untrusted-content.md)) and recorded as a Slice-4 deferral:
`LlamaCppBackend` reads only `content`, so a delta carrying only `reasoning_content` is silently
dropped, and, because the cortex compose (unlike the subagent tier) does **not** pass
`enable_thinking=false`. A long deliberation streams *nothing* to the overlay until it concludes.
Fine for an ordinary prompt; a latency/opacity risk under a heavy think (the overlay looks frozen).

The deferral named three options behind the unchanged `InferenceBackend`: (a) disable thinking for
the cortex (the subagent twin), (b) **surface `reasoning_content` as a "thinking" status**, or (c)
budget enough tokens. This ADR picks (b), because the whole rest of the status path is already
built but dark: the proto has `ServerEvent.StatusUpdate{state, detail}` (Slice 2), the body's
`body_rpc` adapter maps it to `TurnEvent::Status`, and the overlay reducer folds a `status` event
into the streaming message (the "thinking" affordance in [overlay-ux.md](../design/overlay-ux.md)).
The brain is the **only** side that never emits a `StatusUpdate`. Surfacing reasoning both fixes
the silent-think problem (progress is visible as it thinks) and lights up that path end to end,
where (a) would merely hide the reasoning and (c) does not address opacity. Thinking stays **on**
for the cortex. We surface it, not suppress it.

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
   than folding it into the answer. Defensive (no reasoning is expected there) but keeps the loop
   contract honest for both callers.

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
  output guardrail (ADR-0015) scrubs laundered untrusted URLs from the *reply*; it does not see the
  reasoning status. A model could in principle echo an injected URL into its reasoning trace, which
  the overlay would display transiently. Extending the guardrail over reasoning status is deferred
  below. The guardrail's streaming `feed` is built around the single reply stream, and reasoning is
  ephemeral and unpersisted, so v1 keeps it out of scope deliberately.
- **Event volume.** Each reasoning delta is one `StatusUpdate`, counted against the bounded
  `Converse` output queue (`CORTEX_SEAM_CONVERSE_BUFFER`, ADR-0014 backpressure). A verbose think
  produces many small events; the credit bound already caps memory and stalls generation if the
  consumer lags, so this needs no new limit.
- **`state` is advisory.** The overlay currently renders `detail` regardless of `state`; the
  `"thinking"` marker is informational until the overlay distinguishes status kinds (deferred).

## Deferred (behind the unchanged `InferenceBackend` / `TurnCapabilities` / tool-loop seams)

- **Output guardrail over reasoning status** redacts laundered untrusted URLs from the reasoning
  trace as well as the reply, if displaying reasoning proves an exfiltration surface.
- **`state`-aware overlay treatment** is a distinct thinking shimmer / collapsed "thoughts" section
  vs. plain detail text; today the reducer shows `detail` for any status (an overlay-gap item).
- **Disable-thinking / token-budget alternatives** stay available for the cortex behind the same
  seams if a runaway trace or latency floor argues for capping rather than only surfacing.
- **Reasoning persistence / summarization.** Keeping a turn's reasoning for later inspection is a
  separate concern from the ephemeral live status this ADR adds.
- **Injection-harness run against the ~31B brain tier** is unchanged; still opt-in and tied to the
  Slice 11 brain pick (ADR-0013 harness addendum).
