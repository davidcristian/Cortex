# A cut summary looks like a wandering one in the log

**Status:** done 2026-08-18
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Opened 2026-08-16 by the close that passed a finish reason through `InferenceBackend`
([R-206](206-finish-reason-not-carried.md)), which made the delegated path a consumer and declined
to make this one.

`clean_recap` rejects a summary that does not end a sentence, and that check is right whether or
not a stop reason is available: it catches a summary the server cut, one the model ended
mid-thought, and one that arrived mangled, where a stop reason catches only the first. So the
behaviour needs nothing, and this entry is about the log line beside it. A rejected summary logged
"the model returned no usable history recap; falling back to the plain window", and the reader
could not tell `RECAP_MAX_TOKENS` running out from a model that wrote a list, which need opposite
fixes: one raises the cap, the other rewrites the instruction.

## History

- 2026-08-16: Opened by the finish-reason close, which named the history summary as the obvious
  second consumer and declined to make it one in the same slice.
- 2026-08-18: Done as the entry estimated, with one addition it missed. `drain_text` gained `stops:
  StopLedger | None = None`, the optional-collaborator shape `stream_tool_loop` already uses, so
  the two callers that want a bare string are unchanged and the return type never changed. The
  warning gained `capped`, which is the only reading that separates a summary the token budget cut
  from one the model ended in the wrong shape. The free half the entry missed is `chars`, the
  summary's length, which separates the other two rejection causes with no signature change at all:
  `0` is a model that said nothing, and a number past `RECAP_MAX` is one that ran further than the
  store will hold. It is measured through a new `collapse_recap` that `clean_recap` also calls, so
  the number a rejection is logged with is the number it was decided on. `clean_recap` itself is
  untouched. Opened [R-309](309-a-silent-judge-fallback.md), the other `drain_text` caller, whose
  fallback logs nothing at all.
