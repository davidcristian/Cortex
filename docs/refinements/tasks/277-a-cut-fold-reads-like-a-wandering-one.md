# A cut fold reads like a wandering one in the log

**Status:** open, fix when it bites
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Trigger:** the first fold that keeps falling back to the plain window, where "the model returned no usable history recap" is not enough to say whether `RECAP_BOUNDS` is too small or the prompt is wrong.

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
