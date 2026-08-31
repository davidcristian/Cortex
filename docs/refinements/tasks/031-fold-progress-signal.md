# A signal that a turn is folding

**Status:** landed 2026-08-06
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

**Nothing tells the user a turn is folding (opened 2026-08-06).** The fold is serialized ahead of
the reply, so on the turn where the boundary moves the user waits the fold plus the reply with
nothing on screen that distinguishes it from a slow model: the overlay's whisper starts breathing
its accent mist the moment they press enter, and the chip that would say otherwise renders only
when a `StatusUpdate` or `ToolActivity` has landed. None does. The seam is not the obstacle:
`SeamProgressSink` is per Converse stream and emits onto that stream's own queue rather than
through the turn generator, and `build_history_window` is already called inside the per-stream
`capabilities` closure that holds one, so an event emitted during selection would surface while
`assemble_inference_messages` is still running. What is missing is the port: `HistoryWindow.select`
takes a history and a session id and no sink, so the window has nothing to emit onto. Deliberately
not built here, on a knob that is staying off. **Closed 2026-08-06** by the cheap-fold entry
below, which widened exactly that port and found this reading of the obstacle correct.

**Nothing telling the user a turn is folding closed 2026-08-06 ([ADR-0038 cheap-fold
addendum](../../adr/ADR-0038-ranked-recall.md)).** The entry's reading of the obstacle held exactly:
the seam was never the problem and the port was. `HistoryWindow.select` now takes
`progress: ProgressSink | None`, handed per CALL rather than held on the window, matching the
dispatch stamp's discipline (a sink belongs to one `Converse` stream while a window is a policy,
so passing it in keeps a shared window correct for every stream rather than relying on one being
built per stream). `CharBudgetHistoryWindow` ignores it; the summarizing window emits one
`StatusUpdate(state="folding", detail="summarizing the earlier part of this conversation")`
before the pass and only when a pass is really about to happen, so a cache hit and a deferred
fold emit nothing rather than putting a chip on screen for work that is not happening.
`assemble_inference_messages` passes `caps.progress`, and because the sink writes onto the
stream's own queue rather than through the suspended turn generator, the chip lands before the
reply's first token, which a converse-level test asserts by event order. **No overlay change was
needed**, a generic status already rendering as a chip, which the overlay's own suite pins.
Remaining from this deferral: nothing.

## Trail

- 2026-08-06: Opened alongside the run that held the default off, the overlay's mist breathing
  identically for a slow model and a 224-second one, with the reason named as the port rather
  than the seam.
- 2026-08-06: Closed the same day by the cheap-fold change, which widened `HistoryWindow.select`
  to take a `ProgressSink` per call. The overlay needed no change.
