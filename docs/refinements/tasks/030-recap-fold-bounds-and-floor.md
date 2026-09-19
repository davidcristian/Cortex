# Bounds and a floor for the recap fold

**Status:** done 2026-08-06
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Every boundary move spent a full cortex generation over the newly dropped turns, serialized ahead
of the reply, with the fold's prompt being whatever those turns said. Two settings were
deliberately not built: a minimum number of newly dropped messages before a fold is worth paying
for, and a token cap on the recap request, the reply being bounded at `RECAP_MAX` characters after
the fact rather than before.

The numbers made it urgent. A fold cost 14.5 s to 30.8 s typically, with outliers of 77.3 s and
224.5 s, and the server's own counters say where the time went: that 224.5 s fold decoded 6286
tokens against a 370-token prompt, a typical one decodes 400 to 850, and the account actually
stored is 330 to 650 characters, which is 80 to 160 tokens. So most of every fold was reasoning
that `drain_text` discards, and the missing token cap is what left the tail unbounded.

Closed the same day, together with the disable-thinking setting. The diagnosis held on every point
it was checked against: `drain_text` called `backend.stream(model, messages, schema=schema)` and
`_build_payload` put nothing else on the wire, so the request had no `max_tokens` and no
`chat_template_kwargs`; `RECAP_MAX` was applied by `clean_recap` to text the model had already
finished; and `drain_text` keeps only `TextChunk`, so the whole `ReasoningChunk` stream was
decoded, paid for and dropped unread.

What shipped:

- Thinking off per request, through a new `GenerationBounds` on `InferenceBackend.stream` that the
  llama.cpp adapter renders as `chat_template_kwargs: {"enable_thinking": false}`, verified
  against the shipped build first. Per request rather than per server, because one resident cortex
  both answers the user, where the compose file deliberately leaves deliberation on, and folds a
  recap, where it is thrown away.
- A 512-token cap on the request, which is `RECAP_MAX` said in the request's own unit and about
  six times the account the prompt produces. The cap and the switch ship together because a cap
  alone has a measured failure mode: the identical prompt at `max_tokens` 160 and 256 with
  thinking on came back `finish_reason: "length"` with 624 and 988 characters of reasoning and an
  empty reply, and even at 512 it can go either way.
- Degrading to the plain window rather than to half a sentence. `clean_recap` rejects a reply that
  does not end a sentence and one longer than `RECAP_MAX`, because storing a truncated account
  would advance `covers` past turns the missing tail never reached, and the next fold reads from
  `covers` forward, so those turns would be lost for good rather than for one turn.
- A fold floor, `CORTEX_HISTORY_RECAP_MIN_CHARS`, default 2000, clamped to the character budget at
  the composition root, so a small boundary move does not spend a pass. Deferring is not skipping:
  the next fold reads from the unmoved `covers` and picks up everything deferred. What it costs
  meanwhile is a gap smaller than the floor that is in neither the window nor the account.

Measured on the identical prompt through the real adapter: 378, 531 and 602 decoded tokens at
13.6 s, 18.9 s and 21.5 s became 88, 87 and 88 at 3.9 s, 3.8 s and 3.9 s, and the account got
slightly longer, 369 to 382 characters against 345 to 367. Across the staged five-fold run a fold
decodes 61 to 163 tokens in 2.9 s to 6.2 s with no tail at all.

## History

- 2026-08-06: Opened with its trigger already fired, on the run that priced a fold at 14.5 s to
  30.8 s typically with outliers of 77.3 s and 224.5 s, and named it the first of the four things
  a default move waited on.
- 2026-08-06: Closed the same day, together with the token cap, the fold floor and the
  disable-thinking setting. The cap and the switch ship together because a cap alone returned
  `finish_reason: "length"`, hundreds of characters of reasoning, and an empty reply.
