# A stalled consumer holds the GPU lease

**Status:** open, waiting for its trigger
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Trigger:** a production caller of the `Converse` RPC beyond the overlay's one chain, or a wait in
that chain's read loop. Two readings of the tree decide it. Outside tests, generated stubs and
builds, `grep -rn '\.converse(\|BrainServiceStub' body brain` finds on 2026-10-05 seven files: the
chain's four links (`body/app/src/overlay/useOverlay.ts`, the shell's `converse` command in
`body/app/src-tauri/src/converse.rs`, `RetryingTransport` in `body/crates/core/src/retry.rs` and the
tonic client in `body/crates/rpc/src/converse.rs`), two check lists that drive a transport under
test, the bridge contract's `bridgeContract.ts` and the brain transport's
`body/crates/contract/src/transport/turns.rs`, and the `seam` package's re-export of the stub. Any
other file fires it. The shell command's `while let` loop awaits only `stream.next()`; any other
await between two items fires it.
**Verified:** 2026-10-06

The reply's lease is held for the adapter generator's whole lifetime, and the credit bound
([R-028](028-converse-queue-backpressure.md), `CORTEX_SEAM_CONVERSE_BUFFER`) suspends generation
inside that lease once the consumer stops dequeuing and the credits are spent, so a stalled reader
does not only stall itself. At the shipped bound of 256 events (`DEFAULT_MAX_BUFFERED_EVENTS` in
`converse_stream.py`), a turn that emits fewer finishes and releases the lease even when nobody
reads it. The stall delays only work leasing the same manager, and both implementations,
`SingleResidentModelManager` and `SwappingModelManager`, serialize the lease behind one
`asyncio.Lock`. Measured on the
[fold-under-load run](../../readings/history-recap.md#folds-under-concurrent-streams) at a
one-credit bound with the reader stalling 12 s, the stalled stream's reply held the lease four to
seven times as long as an unstalled reply holds it, and the next stream's fold waited for the whole
of that hold.

This predates the summary ([R-027](027-session-history-summarization.md)) and is not caused by it;
what the default-on fold changes is who pays, since a fold is now among the things that queue.
Neither obvious direction is free: the bound exists to cap a stalled stream's memory, and letting
generation run ahead of the consumer to release the lease sooner is the exact thing that bound
prevents. A fix is a limit on how long a suspended generation may hold the lease, and it needs no
port change. `ConverseStream` already cancels a turn on a client's `cancel` (`_cancel_turn`), and
cancelling unwinds `_run_turn`, whose `finally` closes the engine's event stream; the tool loop
closes the backend's stream in turn (`deltas.aclose()` in `tool_loop.py`), which leaves the
backend's `async with self._manager.acquire(model)` and frees the lease. What is missing is a time
limit on the credit wait in `_run_turn` that takes that path, a setting for the limit, and a
decision about what the stream sends the client when it fires.

## History

- 2026-08-08: Opened by the fold-under-load run, as the shipped backpressure behaving as designed
  with nobody having written down who pays for it.
- 2026-08-09: A review of deferred triggers ran against the tree and none fired, recording that
  what remains open there needs live observation, its trigger being a deployment doing something
  rather than a file saying something.
- 2026-09-11: Read against the tree and not fired. Nothing bounds it yet: `ConverseStream` in
  `converse_stream.py` still takes one credit per event from an
  `asyncio.Semaphore(max_buffered_events)`, and `LlamaCppBackend.stream` still yields each event
  from inside `async with self._manager.acquire(model)` (`backend.py`), so a consumer that stops
  dequeuing suspends the generator with the lease held; the only timeout in the stream module is
  the confirm timeout. The nearest thing to the abandonment proposed above is `abandon.py`, the
  unary-call abandonment log of 2026-08-20, whose own docstring says `Converse` announces no
  deadline and must keep announcing none. The shipped stack still has one overlay as its one
  consumer and the tree records no report of one client stalling another's turn.
- 2026-09-17: Not fired, and the trigger now names what decides it inside the tree. The mechanism
  is unchanged: `converse_stream.py` still builds `asyncio.Semaphore(max_buffered_events)` (line
  125) and acquires a credit per event (line 264), and `backend.py` still streams inside
  `async with self._manager.acquire(model)` (line 141). Both manager implementations hold one
  `asyncio.Lock` for the lease (`model.py`, `residency.py`). No second consumer exists. The only
  production path to `Converse` is the overlay's, through the shell's `converse` command
  (`converse.rs` line 184); every Python `BrainServiceStub` user is under
  `brain/packages/orchestrator/tests/`. That command's loop awaits only `stream.next()`, because
  `Channel::send` in the fixed tauri 2.11.5 is a plain `fn` that calls the webview handler without
  waiting on it, so the one consumer cannot stop dequeuing short of the process being suspended.
  The scheduler is not a second lease holder either: its tasks run as subagents, and
  `subagent_builders.py` gives every roster entry a `SingleResidentModelManager` of its own. The
  shell does expect a newer turn to start while an older one still streams (`ConfirmRoute` clears
  by generation), and each turn's loop reads its own stream the same way.
- 2026-09-24: Not fired. The search outside test files finds the same six hits, and the shell's
  loop still awaits only `stream.next()` (`converse.rs` line 200) and sends each item with
  `channel.send`, which does not wait. The brain side is unchanged in substance, at new lines:
  `converse_stream.py` builds the semaphore at line 83 and takes a credit per turn event at line
  210, and `backend.py` streams inside `async with self._manager.acquire(model)` at line 117. The
  turn heartbeat added on 2026-09-22 goes out only while the output queue is empty, so it never
  joins a stalled reader's backlog, and the body's two-minute silence bound ends a stream the brain
  stopped sending on, not one the body stopped reading. Neither bounds this lease.
- 2026-10-03: Not fired. Outside test files the search finds the same six files, and the shell's
  loop still awaits only `stream.next()` (`converse.rs` line 243) and sends each item with
  `channel.send`, which does not wait. The brain side is unchanged at new lines:
  `converse_stream.py` builds the semaphore at line 87 and takes a credit per turn event at line
  226, and `backend.py` streams inside the lease at line 142. Three corrections. The trigger's
  clause about a report of one client stalling another could not be decided from the tree and is
  removed, and the stall's preconditions moved into the text. The measured hold is written as a
  ratio of the unstalled one. And the remedy needs no port change: a turn's cancellation already
  closes the engine's stream and frees the lease, so a bound adds a time limit on the credit wait, a
  setting and what the client is sent.
- 2026-10-05: Not fired, and the trigger's file list corrected. The search now finds a seventh
  file, `turns.rs` in the body's contract crate, added on 2026-10-04 as the turn checks of the
  `BrainTransport` check list. It calls `converse` on the transport a contract test hands it, and the
  crate is a dev-dependency of `body-core` and `body-rpc` only, so it is not a production caller.
  The shell's loop is unchanged since the last check.
