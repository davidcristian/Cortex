# Disable-thinking and token-budget capping

**Status:** landed 2026-08-16
**Area:** inference-model-manager
**Origin:** [ADR-0020](../../adr/ADR-0020-reasoning-status.md)

This item has no top-level bullet of its own: it was recorded inside the reasoning-status entry,
whose landing chose to surface the trace rather than disable thinking or cap the token budget, and
the area doc carries a further paragraph of its own about the narrowing.

Remaining behind the same
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
reply, and even at the shipped 512 it goes either way (one run decoded the whole cap for 92
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
with thinking left on, which went either way on the fold, is a certainty on these two, empty three times
in three at each of 16, 32 and 64 tokens, because their answers are a few tokens and the
deliberation before them is hundreds. A user-facing reply still keeps its thinking deliberately, which is
what per-request bounds are for. What the rank's number reopens is its own default, recorded in
[memory.md](../index.md#memory).

On the narrowing of the capping entry, which is the one the count deliberately did not move
for: the lever shipped on 2026-08-06 as `GenerationBounds` on `InferenceBackend.stream`, and
all three passes whose deliberation `drain_text` throws away unread now take it: the history
recap's fold, the session title, and the model-based recall rank. What the entry still covers is
the case it was written for and the only one left, a user-facing reply, which sends no bounds
deliberately, so a runaway trace on a real answer is uncapped exactly as it always was and the
original trigger, a user who minds the wait, still stands for that case alone. **The count does
not move for this entry.** A count moved for a half-closed entry loses an open item exactly as
one that fails to move for a newly opened deferral does, which this backlog learned in the other
direction; what moves instead is this sentence and the entry's line in the index's
fix-when-it-bites bucket, so nobody picks it up expecting to build a lever that already exists.

## Trail

- 2026-07-06: Deferred when the reasoning-status entry chose surfacing over the other two options,
  the disable-thinking and token-budget alternatives staying available behind the same
  `InferenceBackend` and `TurnCapabilities` seams.
- 2026-08-03: The vision slice asked whether an image turn is the case that finally needs the
  disable-thinking half and the answer measured that day is no, with a number attached: a picture
  makes a think near-certain on an open-ended ask, 10 of 10 runs against 2 of 5 pixel-less, but
  nothing truncates, so what it buys is latency rather than a truncated reply.
- 2026-08-03: The index carried that latency as ranges where this entry rounds it, 5.09 to 6.89 s
  before the first word on a simple screen and 13.80 to 17.70 s on a dense one, and the two sources
  name different control arms, so both readings are kept: this entry compares against 1.2 s with
  thinking off, while the index compares against a median 0.41 s on the same scaffold with the
  picture removed.
- 2026-08-06: It bit hardest on the history recap's fold, whose thinking is thrown away by
  construction, and the lever shipped the same day as `GenerationBounds` on
  `InferenceBackend.stream`, taken by all three passes that discard their own deliberation (the
  fold, the session title, the model-based recall rank). The entry was narrowed rather than closed,
  the user-facing reply being the whole of what stays deferred since it sends no bounds by design,
  and the area count deliberately did not move for the narrowing.
- 2026-08-06: The fold's landing left this entry open on the other two passes' account, the session
  title and the model-based recall rank still spending the same discarded thinking at that moment,
  and both took the bounds later the same day.
- 2026-08-16: Closed. Both halves of the trigger fired with numbers: measured on the shipped
  cortex, an ordinary open question spends 11.8 to 18.1 s before its first word and every second
  of it is a trace of 2545 to 3064 characters, against 0.4 s with thinking off for an answer of
  the same size; and the lineup's own table has two deep candidates consuming a whole context and
  returning nothing. What landed is the honesty first: `TurnEngine` and `BrainPhase` now pass a
  `StopLedger` always and a reply a token limit cut ends with `REPLY_CAPPED_NOTE` in the stream
  and in the store, which fixes a loss older than any cap, since the context window truncates
  replies today and a cut reply is read as a finished short one. Both levers ship as one env value
  (`CORTEX_REPLY_THINKING`, `CORTEX_REPLY_MAX_TOKENS`) defaulting to today's request byte for byte,
  and they are documented as a pair because a cap with thinking left on was measured on this same
  cortex to return an EMPTY reply 3 of 3 rather than a shorter one
  ([ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) capped-reply addendum). What the close opens
  is that the trace cannot be bounded on its own: `--reasoning-budget` is a per-server switch that
  does not work on this build and no request field budgets `reasoning_content` by a count, so the
  only lever over deliberation is all or nothing
  ([289-reasoning-budget-is-all-or-nothing.md](289-reasoning-budget-is-all-or-nothing.md)).
