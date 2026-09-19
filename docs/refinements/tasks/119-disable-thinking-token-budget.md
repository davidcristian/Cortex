# Disable-thinking and token-budget capping

**Status:** done 2026-08-16
**Area:** inference-model-manager
**Origin:** [ADR-0020](../../adr/ADR-0020-reasoning-status.md)

The two options the reasoning-status entry ([R-118](118-reasoning-thinking-status.md)) did not
take: turning the model's deliberation off, and capping how many tokens a request may decode.
Both stayed available behind the `InferenceBackend` and `TurnCapabilities` ports.

**The mechanism shipped 2026-08-06**
([ADR-0038](../../adr/ADR-0038-ranked-recall.md) decision 20). `InferenceBackend.stream` gained
`bounds: GenerationBounds | None`, one frozen value holding `max_tokens` and `thinking`, which
the llama.cpp adapter renders as a `max_tokens` key and
`chat_template_kwargs: {"enable_thinking": false}`. `None` is the default and emits neither, so
every user-facing reply sends the request it always did. It is per request rather than per server,
because one resident cortex both answers the user, where deliberation is deliberately left on, and
folds a recap, where the deliberation is discarded unread.

The two ship as a pair because either alone is worse than neither, which was measured. The same
fold prompt at `max_tokens` 160 and 256 with thinking left on came back `finish_reason: "length"`
with 624 and 988 characters of `reasoning_content` and an empty reply, and even at 512 it went
either way: one run decoded the whole cap for 92 unusable characters, another finished thinking
in 404 tokens and answered. Paired, the same prompt decodes 88 tokens in 3.9 s where the unbounded
request decoded 378 to 602 in 13.6 s to 21.5 s, for a slightly longer account.
`--reasoning-budget 0` does not work on this build, so the per-request `chat_template_kwargs` is
the only control that does.

All three passes whose deliberation `drain_text` throws away unread now send bounds: the history
recap's fold, `generate_title` (`TITLE_BOUNDS`, `max_tokens=32, thinking=False`, 32 being
`TITLE_MAX` in the request's own unit) and `JudgeRecallPolicy.select` (`rank_bounds(k)`, `24 + 8k`,
computed rather than fixed because a schema-constrained order's length is known before it is
asked for). On the shipped cortex, a title went from 235 to 303 decoded tokens at 7.9 s to 10.4 s
to 4 tokens at 0.2 s to 0.3 s for the same titles, and a recall rank from 448 to 613 tokens at
18.4 s to 12 to 22 tokens at 0.9 s, its ranking unchanged (mean reciprocal rank 1.000 either way,
the right note first 6 of 6). Two things the entry had not predicted: a JSON schema does not
protect a constrained reply from a cap, since a truncated reply is not JSON and the caller falls
back exactly as it does for an unreachable model; and a cap with thinking left on, which went
either way on the fold, is a certainty on these two, empty three times in three at each of 16, 32
and 64 tokens, because their answers are a few tokens and the deliberation before them is
hundreds.

**Closed 2026-08-16** for the user-facing reply, the one case left. Both halves of its trigger
fired with numbers: on the shipped cortex an ordinary open question spends 11.8 to 18.1 s before
its first word, every second of it a trace of 2545 to 3064 characters, against 0.4 s with thinking
off for an answer of the same size; and the lineup's own table has two deep candidates consuming a
whole context and returning nothing.

`TurnEngine` and `BrainPhase` now always pass a `StopLedger`, and a reply a token limit cut ends
with `REPLY_CAPPED_NOTE` in the stream and in the store. That fixes a loss older than any cap,
since the context window already truncates replies and a cut reply reads as a finished short one.
Both controls ship as one env value each, `CORTEX_REPLY_THINKING` and
`CORTEX_REPLY_MAX_TOKENS`, defaulting to today's request exactly, and they are documented as a
pair because a cap with thinking left on returned an empty reply 3 of 3 on this same cortex
([ADR-0048](../../adr/ADR-0048-generation-bounds.md)).

The close opens [R-289](289-reasoning-budget-is-all-or-nothing.md): the trace cannot be bounded on
its own, since `--reasoning-budget` is a per-server switch that does not work on this build and no
request field limits `reasoning_content` by a count.

## History

- 2026-07-06: Deferred when the reasoning-status entry chose to show the trace instead.
- 2026-08-03: The vision slice asked whether an image turn is the case that needs the
  disable-thinking half, and the answer is no: a picture makes a think near-certain on an
  open-ended ask, 10 of 10 runs against 2 of 5 without pixels, but nothing truncates, since the
  shipped request sends no `max_tokens` against a server at `n_predict: -1`. What it costs is
  latency, roughly 6 s before the first word on a simple screen and 15 s on a dense one against
  1.2 s with thinking off ([vision-capture](../../readings/vision-capture.md)).
- 2026-08-03: The index recorded that latency as ranges where this entry rounds it, 5.09 to 6.89 s
  on a simple screen and 13.80 to 17.70 s on a dense one, and the two sources compare against
  different controls, so both readings are kept: this entry compares against 1.2 s with thinking
  off, the index against a median 0.41 s on the same scaffold with the picture removed.
- 2026-08-06: The clearest case was the history recap's fold, whose thinking is thrown away by
  construction, since `drain_text` keeps `TextChunk` and drops `ReasoningChunk` before the caller
  sees it. Over three staged sessions a fold decoded 400 to 850 tokens typically and once 6286,
  for an account of 330 to 650 characters, so the wait was 14.5 s to 30.8 s typically and reached
  224.5 s. The mechanism shipped the same day and the entry was narrowed rather than closed, the
  user-facing reply being all that stayed deferred. The area count deliberately did not move for
  the narrowing, because a count moved for a half-closed entry loses an open item.
- 2026-08-06: The fold's change left this entry open on the session title and the model-based
  recall rank, and both took the bounds later the same day.
- 2026-08-16: Closed.
