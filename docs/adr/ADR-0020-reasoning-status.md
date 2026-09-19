# ADR-0020: Show the cortex's reasoning as a live "thinking" status

**Status:** Accepted (2026-07-20)

## Context

The resident cortex, gemma-4-12B, is a **reasoning model**, and so are the Qwen subagent picks:
over the OpenAI-compatible stream it emits `choices[0].delta.reasoning_content` (its private
deliberation) *before* the `delta.content` that is the reply. This was found during the GPU
validation of the untrusted-content framing ([ADR-0013](ADR-0013-untrusted-content.md)).
`LlamaCppBackend` read only `content`, so a delta with only `reasoning_content` was silently
dropped, and because the cortex tier, unlike the subagent tier, does not switch thinking off, a
long deliberation streamed *nothing* to the overlay until it concluded. The overlay looked frozen.

Three options sat behind the unchanged `InferenceBackend`: (a) disable thinking for the cortex (the
same choice the subagent tier makes), (b) **show `reasoning_content` as a "thinking" status**, or
(c) limit the trace. This ADR picks (b), because the rest of the status path was already built and
never exercised: the proto has `ServerEvent.StatusUpdate{state, detail}`, the body's `body_rpc`
adapter maps it to `TurnEvent::Status`, and the overlay folds a `status` event into the streaming
message (the thinking indicator in [overlay-ux.md](../design/overlay-ux.md)). The brain was the
only side that never emitted one. Option (a) hides the reasoning and option (c) does not address
the silence. Thinking stays **on** for the cortex, and the trace is shown rather than suppressed.

## Decision

### The brain

1. **`ReasoningChunk(text)` joins the `InferenceEvent` union (`inference.py`).** The union is
   `TextChunk | ReasoningChunk | ToolCall`; the `InferenceBackend.stream` signature is unchanged,
   the same additive move [ADR-0009](ADR-0009-tools-mcp.md) made with `ToolCall`.
   `LlamaCppBackend` reads `delta.reasoning_content` beside `delta.content`, validates each as
   string-or-absent as strictly as `content` (a non-string fails the turn, never a silent drop),
   and yields any reasoning before any text within a chunk, the model's own order.

2. **The shared tool loop yields reasoning as its own event, and reasoning is ephemeral.** Reply
   text stays a bare `str`; reasoning is `ReasoningDelta(text)` (`loop_events.py`), translated from
   `ReasoningChunk` as text is from `TextChunk`, beside the loop's `ToolStep`. Reasoning is *not*
   appended to the step's assistant text and *not* written into any `Role.ASSISTANT` or working
   message, so it never re-enters the model's context on a later step and is never persisted. It
   can arrive on any inference step, including re-inference after tool results, so one turn may
   show several bursts of thinking.

3. **The engine maps reasoning to a domain `StatusUpdate` (`events.py`, `engine.py`).**
   `StatusUpdate(state, detail)` mirrors the proto and is general by design (the handoff reuses
   it). The engine yields `StatusUpdate(state="thinking", detail=<reasoning text>)` for each
   `ReasoningDelta`, outside `parts`: reasoning is neither the reply, nor accumulated into
   `full_text`, nor recorded to memory. A turn's events are zero or more `TextDelta`,
   `StatusUpdate`, `ToolActivity` and `ToolOutcome`, interleaved, then exactly one `TurnCompleted`.

4. **The orchestrator maps the domain event to the wire** (`to_server_event` in
   `converse_stream.py`, the `DomainStatusUpdate` and `WireStatusUpdate` aliases). The body passes
   it through unchanged.

5. **Subagents drop reasoning** (`subagent_attempt.py`). The subagent tier runs with thinking off
   ([ADR-0049](ADR-0049-thinking-switch-and-trace-budget.md) decision 8) and has no status channel,
   so a `ReasoningDelta` is dropped rather than folded into the answer: a safe default, and one
   loop contract for both callers.

6. **The output guardrail cleans the reasoning status as its own stream** (`output_channels.py`).
   The overlay renders a status `detail`, so on a tainted turn injected content could steer the
   reasoning to write a URL the reply filter would have removed. `open_output_channels` opens the
   reply filter and a `ThinkingChannel` under the **same** policy and user-URL allowlist (quoting
   the user's own link in the trace is not laundering), one `OutputFilter` each, so the two
   held-back buffers stay independent and a URL split across the reply and the trace renders whole
   on neither. `ThinkingChannel.feed` maps a reasoning delta to the status to show now (a delta
   held back whole emits no event, never an empty detail); `release` emits the cleaned remainder
   once, at end of stream. One turn's trace is **one stream**: what is held back survives tool
   steps and reply deltas between bursts, because flushing at each burst boundary let a URL steered
   to straddle a think, tool, think boundary cross as two fragments, neither matching. The cost is
   that a held-back fragment shows slightly later. Redact and strict modes and the URL grammar are
   [ADR-0015](ADR-0015-output-guardrail.md)'s, under the same `CORTEX_OUTPUT_GUARDRAIL`.

7. **The cortex keeps thinking on, and its trace length is a server setting.** A runaway trace is
   limited by the cortex tier's `CORTEX_REASONING_BUDGET` (ADR-0049 decision 7), not by hiding the
   trace.

### The overlay

8. **A thinking status renders as its own chip.** The reducer keeps the status `state` beside its
   `detail` (`Message.statusState`, `null` until a status arrives and dropped when the turn
   settles). A chip whose `statusState` is `"thinking"` gets the `chip-think` modifier and the
   label "Thinking": its dot bobs on the reasoning `think` keyframe rather than the tool `pulse`,
   and the label takes the accent, so deliberation reads apart from an action. Every other status
   stays the neutral pill, and colour stays in the working states.

9. **The settled reply keeps its trace behind a "Thoughts" disclosure.** The reducer concatenates
   every `"thinking"` detail, in order, into `Message.thoughts`. While the reply streams the live
   chip shows the latest delta; once it settles the chip drops and a collapsed "Thoughts" control
   above the bubble holds the whole trace, rendered only when `!streaming && thoughts !== ""`, so
   one reasoning control shows at a time. It is a button with `aria-expanded` over the overlay's
   rolling section (`components/Thoughts.tsx` over `components/Collapse.tsx`,
   [ADR-0035](ADR-0035-console-and-motion.md) decision 14), because a `<details>` cannot animate
   what it reveals and the trace appeared in one frame while the panel eased behind it. The trace
   is one plain text node: no markup parsed, no URL linkified. Each detail was already cleaned by
   the thinking channel, so the section re-shows only what the chip showed.

10. **Reasoning is not persisted or summarized.** Nothing reads a stored trace: the disclosure is
    served by the in-memory `thoughts`. Re-showing it after a session reload would need a reasoning
    field on the `GetSessionMessages` read path (a proto change and store plumbing) and a decision
    about storage growth, since one observed single-turn deliberation ran to 13,882 characters.
    Summarizing the trace into future context would reverse decision 2 and cost another inference
    call sequenced around the GPU lease as the session title generator is. Either reopens when its
    consumer exists.

## Consequences

- The overlay shows the cortex thinking, token by token, instead of a frozen panel, and the proto,
  body and overlay status path is exercised end to end.
- Invisible to every non-reasoning path: a backend that yields no `reasoning_content` produces the
  previous events, and a bare `TurnCapabilities()` turn is unaffected.
- Each reasoning delta is one `StatusUpdate` counted against the limited `Converse` output queue
  (`CORTEX_SEAM_CONVERSE_BUFFER`); a verbose trace makes many small events, and the credit limit
  already caps memory and stalls generation when the consumer lags.
- Validated live on gemma-4-12B with a reasoning-inducing prompt: the adapter showed
  `reasoning_content` before the reply, and the full engine emitted the thinking statuses before
  the reply's deltas with the reply clean and what was persisted equal to what was shown.
  `test_reasoning_model_emits_reasoning_before_reply` reproduces the adapter half
  ([llamacpp-gpu.md](../runbooks/llamacpp-gpu.md)).

## Alternatives rejected

- **Disabling thinking for the cortex**, or limiting the trace instead of showing it (Context).
- **Flushing the thinking buffer at each burst boundary** (decision 6).
- **A `<details>` disclosure** (decision 9).
- **Persisting or summarizing the trace** without a consumer (decision 10).

## Related

- Module contracts: [brain-core.md](../modules/brain-core.md),
  [body-app.md](../modules/body-app.md). Runbook: [llamacpp-gpu.md](../runbooks/llamacpp-gpu.md).
- [ADR-0015](ADR-0015-output-guardrail.md) (the guardrail),
  [ADR-0049](ADR-0049-thinking-switch-and-trace-budget.md) (the thinking switch and trace budget),
  [ADR-0035](ADR-0035-console-and-motion.md) (the rolling section).
