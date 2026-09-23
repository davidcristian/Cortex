# A signal that a turn is folding

**Status:** done 2026-08-06
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

The fold runs before the reply, so on the turn where the boundary moves the user waits for the
fold plus the reply with nothing on screen to distinguish it from a slow model: the overlay's
whisper starts the moment they press enter, and the chip that would say otherwise renders only
once a `StatusUpdate` or `ToolActivity` has arrived, and none did.

The obstacle was the port, not the transport. `RpcProgressSink` is per Converse stream and emits
onto that stream's own queue rather than through the turn generator, and `build_history_window` is
already called inside the per-stream `capabilities` closure that holds one, so an event emitted
during selection would appear while `assemble_inference_messages` is still running.
`HistoryWindow.select` took a history and a session id and no sink, so the window had nothing to
emit onto.

Closed 2026-08-06, and that reading was right. `HistoryWindow.select` now takes
`progress: ProgressSink | None`, passed per call rather than held on the window, because a sink
belongs to one `Converse` stream while a window is a policy, so passing it in keeps a shared
window correct for every stream. `CharBudgetHistoryWindow` ignores it. The summarizing window
emits one `StatusUpdate(state="folding", detail="summarizing the earlier part of this
conversation")` before the pass, and only when a pass is really about to happen, so a cache hit
and a deferred fold emit nothing rather than showing a chip for work that is not happening.
`assemble_inference_messages` passes `caps.progress`, and because the sink writes onto the
stream's own queue rather than through the suspended turn generator, the chip appears before the
reply's first token, which a converse-level test asserts by event order. No overlay change was
needed, a generic status already rendering as a chip.

## History

- 2026-08-06: Opened alongside the run that held the default off, the overlay looking identical
  for a slow model and for a 224-second fold, with the port named as the reason rather than the
  transport.
- 2026-08-06: Closed the same day by widening `HistoryWindow.select` to take a `ProgressSink` per
  call. The overlay needed no change.
