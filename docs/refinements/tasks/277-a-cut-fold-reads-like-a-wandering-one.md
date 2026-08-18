# A cut fold reads like a wandering one in the log

**Status:** landed 2026-08-18
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Opened 2026-08-16 by the close that carried a finish reason across `InferenceBackend`
([R-206](206-finish-reason-not-carried.md)), which made the delegated path a consumer and declined
to make this one.

`clean_recap` rejects an account that does not end a sentence, and that check stays right whether
or not a stop reason is available: it catches a fold the server cut, a fold the model ended
mid-thought, and a fold that arrived mangled, where a stop reason catches only the first. So the
**behaviour** wants nothing here, and this entry is about the log line beside it. Today a rejected
fold logs "the model returned no usable history recap; falling back to the plain window" and the
reader cannot tell `RECAP_MAX_TOKENS` running out from a model that wrote a list, which are opposite
fixes: one raises the cap, the other rewrites the instruction. Both are silent and both self-heal
next turn, so nothing accumulates for a reader to compare either.

The cost is a signature change, and it is why this was declined rather than folded in.
`drain_text` returns a `str` and its three callers want exactly that (the session title, the
recap fold, and the rerank judge); carrying a stop out of it means
a small result value or an out parameter, and then the session title and the rerank judge either
grow a field they ignore or the helper grows a second shape. The cheapest honest version is a
`StopLedger` threaded into `drain_text` the way the delegated attempt threads one into
`stream_tool_loop`, so the caller that wants the reason passes one and the two that do not are
unchanged, and `SummarizingHistoryWindow` names the cut in its existing warning rather than
returning anything new.

## Trail

- 2026-08-16: Opened by the finish-reason close, which named the recap fold as the obvious second
  consumer and declined to make it one in the same slice.
- 2026-08-18: Landed as the entry priced it, with one addition the entry missed and one it got
  right. `drain_text` gained `stops: StopLedger | None = None`, the optional-collaborator shape
  `stream_tool_loop` already uses, so the two callers that want a bare string are byte-identical
  and the return type never changed. The warning gained `capped`, which is the only reading that
  separates a fold the token budget cut from one the model ended in the wrong shape, those being
  the two cases that produce identical text and want opposite fixes. The free half the entry
  missed: `chars`, the account's length, splits the other two rejection causes with no signature
  at all, `0` being a model that said nothing and a number past `RECAP_MAX` one that ran further
  than the store will hold. It is measured through a new `collapse_recap` that `clean_recap` now
  calls too, so the number a rejection is logged with is the number it was decided on rather than
  a second spelling that would disagree exactly at the boundary. `clean_recap` itself is
  untouched, the behaviour wanting nothing being the one claim in this entry that survived
  unchanged. The addendum argues the reversal of the earlier "worth a log line and not a signature
  change" in writing rather than contradicting it quietly, the point being that no log line
  reaches this without the signature. Opened
  [R-309](309-a-silent-judge-fallback.md), the other `drain_text` caller with a fallback logging
  nothing at all.
