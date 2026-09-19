# The cortex reasoning trace as a thinking status

**Status:** done 2026-07-06
**Area:** inference-model-manager
**Origin:** [ADR-0020](../../adr/ADR-0020-reasoning-status.md)

The cortex (gemma-4-12B) emits `reasoning_content` before `content`, found during the Slice 6.5
GPU validation, and thinking stays on for it. `LlamaCppBackend` read only `content`, so a long
deliberation streamed nothing until it concluded.

Of the three options (disable thinking, cap the token budget, show the trace), showing it was
chosen. `ReasoningChunk` joined the `InferenceEvent` union, the shared `stream_tool_loop` yields
`str | ReasoningDelta` with the reasoning never persisted or fed back, and the engine maps it to a
domain `StatusUpdate(state="thinking", ...)` and so to the wire `ServerEvent.status` the proto,
body and overlay already had but the brain had never emitted. Covered end to end in CI over the
fakes, and tested in Docker on 2026-07-06: live gemma-4-12B streamed a real reasoning trace shown
as 326 `StatusUpdate(state="thinking")` events, the reply clean and what was persisted equal to
what was shown (`test_reasoning_model_emits_reasoning_before_reply`).

**The output guardrail over the trace shipped 2026-07-12**
([ADR-0020 decision 6](../../adr/ADR-0020-reasoning-status.md)). The inline chips gave the
thinking status a rendered surface, so a laundered URL in the trace had a display channel the
reply-side guardrail never inspected. The trace now streams through its own second `OutputFilter`
under the same policy and user-URL allowlist (`output_channels.py`): a `ThinkingChannel` scrubs
each delta, emits no status for a delta held whole, keeps its held text across tool steps so a URL
split around a dispatch is joined before matching, and releases once at end of stream. An
adversarial review had caught the per-burst-flush variant letting a fragmented URL through.
Redact and strict modes and the obfuscation-resistant grammar are inherited, with no new config
and no wire change.

**The overlay treatment shipped 2026-07-13**
([ADR-0020 decision 8](../../adr/ADR-0020-reasoning-status.md)): the reducer keeps the status
event's `state` as `Message.statusState`, and a `"thinking"` chip renders distinctly through a
`chip-think` modifier (the reasoning bob on its dot, an accent label, an aria label). The `state`
field was already on the wire.

**The collapsed thoughts section shipped 2026-07-16 and reasoning persistence was declined the
same day** ([ADR-0020 decisions 9 and 10](../../adr/ADR-0020-reasoning-status.md)). The reducer
also concatenates every scrubbed thinking delta into `Message.thoughts`, and the settled reply
renders it as a collapsed disclosure above the bubble (`overlayState.ts` and `Thoughts.tsx`,
covered in CI and checked in a browser in both themes). Persisting or summarizing the trace is
declined for want of a consumer: nothing reads a stored trace, re-display on reload would need a
`GetSessionMessages` reasoning field and the store would grow by the observed ~13,882 characters
per turn, and summarization reverses this ADR's decision that the trace is never fed back while
re-raising the non-reentrant GPU-lease sequencing the title generator works around.

The disable-thinking and token-budget alternatives stayed available behind the same
`InferenceBackend` and `TurnCapabilities` ports, and are [R-119](119-disable-thinking-token-budget.md).

## History

- 2026-07-06: Shipped, and tested in Docker by the agent the same day: 326
  `StatusUpdate(state="thinking")` events, the reply clean and what was persisted equal to what
  was shown.
- 2026-07-12: The output guardrail over the trace shipped, once the inline chips gave the thinking
  status a display channel the reply-side guardrail never inspected.
- 2026-07-13: The `state`-aware overlay treatment shipped, entirely in the overlay tree with no
  wire change.
- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section into this area.
- 2026-07-16: The collapsed thoughts section shipped and reasoning persistence and summarization
  was declined for want of a consumer; the area went 5 to 3, and the declined half moved to the
  index's waiting-for-a-consumer list.
- 2026-07-16: The decline was recorded with its cost: persisting reverses a deliberate decision to
  keep the trace ephemeral, so it is a design change rather than a cheap follow-on, and it reopens
  the day a reload re-display or a summarization consumer appears.
- 2026-07-20: The disclosure was rebuilt as a button over `Collapse`, so the trace rolls open
  instead of snapping.
