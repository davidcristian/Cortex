# Bounds and a floor for the recap fold

**Status:** landed 2026-08-06
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

**The recap pass is unbounded and unthrottled, and its trigger has fired (2026-08-06).** Every
boundary move spends a full cortex generation over the newly dropped turns, serialized ahead of
the reply, and the fold's prompt is whatever those turns say. Two knobs were consciously not
built: a minimum number of newly dropped messages before a fold is worth paying for, and a token
cap on the recap request (the reply is bounded at `RECAP_MAX` characters after the fact, not
before). The re-run put numbers on both halves. A fold costs 14.5 s to 30.8 s typically, with
outliers of 77.3 s and **224.5 s**, and the server's own counters say where it goes: that 224.5 s
fold decoded 6286 tokens against a 370-token prompt, a typical one decodes 400 to 850, and the
account actually stored is 330 to 650 characters, which is 80 to 160 tokens. So most of every
fold is reasoning `drain_text` discards, and the missing token cap is what leaves the tail
unbounded. It is the first of the four things a default move waits on
([ADR-0038](../../adr/ADR-0038-ranked-recall.md) re-measured-behind-the-fence addendum), and the
second is not here but in [inference-model-manager.md](../index.md#inference-model-manager): a fold is the
clearest case yet for the disable-thinking lever, since unlike a reply nobody ever sees the
thinking it pays for. **Closed 2026-08-06** by the cheap-fold entry below, which built both
knobs and that lever together.

**The recap pass is bounded and floored, the fold is no longer silent, and the default moved to
on, 2026-08-06 ([ADR-0038 cheap-fold addendum](../../adr/ADR-0038-ranked-recall.md)).** The two
entries above named four things a default move waited on and all four landed together. **The
diagnosis held on every point** it was checked against the tree: `drain_text` called
`backend.stream(model, messages, schema=schema)` and `_build_payload` put nothing else on the
wire, so the request carried no `max_tokens` and no `chat_template_kwargs`; `RECAP_MAX` was
applied by `clean_recap` to text the model had already finished; and `drain_text` keeps only
`TextChunk`, so the whole `ReasoningChunk` stream was decoded, paid for and dropped unread.
**Thinking is now off per request**, through a new `GenerationBounds` on
`InferenceBackend.stream` that the llama.cpp adapter renders as
`chat_template_kwargs: {"enable_thinking": false}`, verified against the shipped build before
anything was written; per request rather than per server because one resident cortex both
answers the user, where the compose file deliberately leaves deliberation on, and folds a recap,
where it is thrown away. **The request is capped** at 512 tokens, which is `RECAP_MAX` said in
the request's own unit and roughly six times the account the prompt produces, and the cap and
the switch ship together because a cap alone fails in a way this repo measured: the identical prompt
at `max_tokens` 160 and 256 with thinking on came back `finish_reason: "length"` with 624 and
988 characters of reasoning and an EMPTY reply, and even at 512 it goes either way. **Hitting a
bound degrades to the plain window rather than to half a sentence:** `clean_recap` rejects a
reply that does not end a sentence and one longer than `RECAP_MAX`, because storing a truncated
account would advance `covers` past turns the missing tail never reached and the next fold reads
from `covers` forward, so those turns would be lost for good rather than for a turn. **A fold
floor** (`CORTEX_HISTORY_RECAP_MIN_CHARS`, default 2000, clamped to the character budget at the
composition root) stops a small boundary move from spending a pass; deferring is not skipping,
since the next fold reads from the unmoved `covers` and picks up everything deferred, and what
it costs meanwhile is a gap smaller than the floor sitting in neither the window nor the account.
**Measured against the request that shipped**, on the identical prompt through the real adapter:
378, 531 and 602 decoded tokens at 13.6 s, 18.9 s and 21.5 s became 88, 87 and 88 at 3.9 s, 3.8 s
and 3.9 s, and the account got slightly LONGER (369 to 382 characters against 345 to 367). Across
the staged five-fold arm a fold decodes 61 to 163 tokens for 2.9 s to 6.2 s with no tail at all.
Remaining from this deferral: nothing of its own.

## Trail

- 2026-08-06: Opened with its trigger already fired, on the re-run that priced a fold at 14.5 s to
  30.8 s typically with outliers of 77.3 s and 224.5 s, and named it the first of the four things
  a default move waits on.
- 2026-08-06: Closed the same day by the cheap-fold change, which built the token cap, the fold
  floor and the disable-thinking lever together. The cap and the switch ship together because a
  cap alone has a measured failure mode: the same prompt at 160 and 256 tokens with thinking on
  returned `finish_reason: "length"`, hundreds of characters of reasoning, and an empty reply.
- 2026-08-06: That the diagnosis held on every point was recorded as worth saying in an area whose
  own entries had twice been wrong about themselves.
