# The cortex reasoning trace as a thinking status

**Status:** landed 2026-07-06
**Area:** inference-model-manager
**Origin:** [ADR-0020](../../adr/ADR-0020-reasoning-status.md)

The cortex (gemma-4-12B) emits
`reasoning_content` before `content` (found during the Slice 6.5 GPU validation), and thinking
stays on for it; `LlamaCppBackend` used to read only `content`, so a long deliberation streamed
nothing until it concluded. The chosen option (of disable-thinking / surface / token-budget) is
**surface**: `ReasoningChunk` joins the `InferenceEvent` union, the shared `stream_tool_loop`
yields `str | ReasoningDelta` (reasoning ephemeral, never persisted or fed back), and the engine
maps it to a domain `StatusUpdate(state="thinking", …)` → the wire `ServerEvent.status` the
proto/body/overlay already carried but the brain never emitted. CI-gated end to end over the
fakes; **host-validated via Docker (agent, 2026-07-06, [ADR-0020 addendum](../../adr/ADR-0020-reasoning-status.md)):**
live gemma-4-12B streamed a real reasoning trace surfaced as 326 `StatusUpdate(state="thinking")`
events, reply clean and persisted==shown (integration test `test_reasoning_model_emits_reasoning_before_reply`).
**The output guardrail over reasoning status landed 2026-07-12
([ADR-0020 addendum](../../adr/ADR-0020-reasoning-status.md)):** the inline chips (see [body-overlay.md](../index.md#body-overlay)) gave the
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
capping) and **reasoning persistence/summarization**. The vision slice asked whether an image turn
is the case that finally needs the disable-thinking half, and the answer measured 2026-08-03 is
no, with a number attached ([vision.md](../index.md#vision), [ADR-0029 agent-validation
addendum](../../adr/ADR-0029-vision-screen-capture.md)): a picture makes a think near-certain on an
open-ended ask, 10 of 10 runs against 2 of 5 pixel-less, but nothing truncates, since the shipped
request sends no `max_tokens` against a server at `n_predict: -1`. What it buys is latency,
roughly 6 s before the first word on a simple screen and 15 s on a dense one against 1.2 s with
thinking off, so this
lever stays fix-when-it-bites and its trigger is a user who minds the wait rather than a truncated
reply. **It bit hardest on 2026-08-06, on the history recap's fold**
([session-history.md](../index.md#session-history), [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
re-measured-behind-the-fence addendum), which is the clearest case for the lever yet and a
different one from vision: a fold's thinking is not merely unwatched, it is thrown away by
construction, since `drain_text` keeps `TextChunk` and drops `ReasoningChunk` before the caller
ever sees it. Measured over three staged sessions, a fold decoded 400 to 850 tokens typically and
once 6286, for an account of 330 to 650 characters, so the wait is 14.5 s to 30.8 s typically and
reached 224.5 s, nearly all of it spent generating text nothing reads. The token-budget half is
wanted here too and for the same reason (`RECAP_MAX` cuts the stored text after the model has
spoken, so nothing bounds the request), and both together are what a move of
`CORTEX_HISTORY_SUMMARY` off its default waits on. **Both halves landed the same day
([ADR-0038](../../adr/ADR-0038-ranked-recall.md) cheap-fold addendum), and the port is what carries
them.** `InferenceBackend.stream` gained `bounds: GenerationBounds | None`, one frozen value
holding `max_tokens` and `thinking`, which the llama.cpp adapter renders as a `max_tokens` key
and `chat_template_kwargs: {"enable_thinking": false}`; `None` is the default and emits neither,
so every user-facing reply sends the byte-identical request it always did. It is per REQUEST
rather than per server because one resident cortex both answers the user, where the compose file
deliberately leaves deliberation on, and folds a recap, where it is discarded unread. **The two
ship as a pair because either alone is worse than neither**, which was measured rather than
argued: the identical fold prompt at `max_tokens` 160 and 256 with thinking left on came back
`finish_reason: "length"` carrying 624 and 988 characters of `reasoning_content` and an EMPTY
reply, and even at the shipped 512 it is a coin flip (one run decoded the whole cap for 92
unusable characters, another finished thinking in 404 and answered). Paired, the same prompt
decodes 88 tokens in 3.9 s where the unbounded request decoded 378 to 602 in 13.6 s to 21.5 s,
for a slightly LONGER account. `--reasoning-budget 0` is still not working on this build, so the
per-request `chat_template_kwargs` remains the only lever that does. **The two callers that were
left open took it the same day ([ADR-0038](../../adr/ADR-0038-ranked-recall.md)
bounded-side-calls addendum), so every pass whose thinking `drain_text` discards now says so in
its request.** `generate_title` sends `TITLE_BOUNDS` (`max_tokens=32, thinking=False`, 32 being
`TITLE_MAX` in the request's own unit) and `JudgeRecallPolicy.select` sends `rank_bounds(k)`
(`24 + 8k`, computed rather than fixed because a schema-constrained order's length is known
before it is asked for). Measured on the shipped cortex: a title went from 235 to 303 decoded
tokens at 7.9 s to 10.4 s to **4 tokens at 0.2 s to 0.3 s for the same titles**, and a recall
rank from 448 to 613 tokens at 18.4 s to **12 to 22 tokens at 0.9 s**, its ranking unchanged
(mean reciprocal rank 1.000 either way, the right note first 6 of 6). Two findings the residue
did not predict: a JSON schema does **not** protect a constrained reply from a cap (a truncated
one is not JSON, so it falls back exactly as an unreachable model does), and the trap of a cap
with thinking left on, a coin flip on the fold, is a certainty on these two, empty three times
in three at each of 16, 32 and 64 tokens, because their answers are a few tokens and the
deliberation before them is hundreds. A user-facing reply still keeps its thinking deliberately, which is
what per-request bounds are for. What the rank's number reopens is its own default, recorded in
[memory.md](../index.md#memory). **`state`-aware overlay treatment landed
2026-07-13 ([ADR-0020 third addendum](../../adr/ADR-0020-reasoning-status.md)):** the reducer now
keeps the status event's `state` (a new `Message.statusState`) and a `"thinking"` chip renders
distinctly (a `chip-think` modifier: the reasoning bob on its dot, an accent label, an aria
label) from a generic status or tool chip, entirely in the CI-gated overlay tree with no seam
change (the `state` field already rode the wire). A richer collapsed "thoughts" section stays
open behind the same field. **The collapsed "thoughts" section landed and reasoning
persistence/summarization was declined on 2026-07-16, both without a seam change ([ADR-0020
fourth addendum](../../adr/ADR-0020-reasoning-status.md)):** the reducer now also concatenates every
scrubbed thinking delta into a new `Message.thoughts`, and the settled reply renders it as a
collapsed disclosure above the bubble, the chip's retrospective counterpart (`overlayState.ts` +
`Thoughts.tsx`, gated + browser-validated in both themes; a `<details>` at first, rebuilt on
2026-07-20 as a button over `Collapse` so the trace rolls open instead of snapping). Persisting or
summarizing the trace stays **declined for want of a consumer**: nothing reads a stored trace,
re-display on reload needs a `GetSessionMessages` reasoning field (the read path the open-chat
title-consistency entry independently needs widened) and the store to grow by the observed
~13,882-char single-turn scale, and summarization reverses this ADR's "never fed back" while
re-raising the non-reentrant GPU-lease sequencing the title generator navigates. It moves to
this backlog's dead-until-a-consumer list and reopens the day either consumer appears.

## Trail

- 2026-07-06: Landed, the behaviour having been found during the Slice 6.5 GPU validation, and
  host-validated via Docker by the agent the same day: live gemma-4-12B streamed a real reasoning
  trace surfaced as 326 `StatusUpdate(state="thinking")` events, the reply clean and persisted equal
  to shown.
- 2026-07-12: The output guardrail over reasoning status landed, once the inline chips gave the
  thinking status a rendered surface and so a display channel the reply-side guardrail never
  inspected.
- 2026-07-13: The `state`-aware overlay treatment landed, entirely in the CI-gated overlay tree with
  no seam change.
- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section into this area doc,
  verbatim.
- 2026-07-16: The collapsed "thoughts" section landed and reasoning persistence and summarization
  was declined for want of a consumer, both without a seam change; the area went 5 to 3 as this
  actionable reasoning pair closed as two outcomes, and the declined half moved to the index's
  dead-until-a-consumer list.
- 2026-07-16: The decline was recorded with its cost beside its want of a consumer: persisting
  reverses a deliberate ephemeral decision, so it is a design change and not a cheap follow-on, and
  it reopens the day a reload re-display or a summarization consumer appears, designed then with
  the record that reader needs.
- 2026-07-20: The disclosure was rebuilt as a button over `Collapse`, so the trace rolls open
  instead of snapping.
