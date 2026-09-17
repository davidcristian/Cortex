# A stalled consumer holds the GPU lease

**Status:** open, fix when it bites
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Trigger:** a production path to the `Converse` RPC other than the overlay's one chain, which runs from `body/app/src/overlay/useOverlay.ts` through the shell's `converse` command (`body/app/src-tauri/src/converse.rs`), `RetryingTransport` (`body/crates/core/src/retry.rs`) and the tonic client (`body/crates/rpc/src/converse.rs`); or that command's read loop awaiting anything between two stream items other than the next item. Grepping `.converse(` and `BrainServiceStub` outside test files decides the first: on 2026-09-17 the hits are those four links, the bridge contract's check list `bridgeContract.ts`, and the seam package's re-export of the stub. A report of one client stalling another's turn would also fire it and cannot be read from the tree. The stall needs a turn that emits more events than `CORTEX_SEAM_CONVERSE_BUFFER` (default 256, measured at 1), and it delays only work leasing the same manager, which both implementations, `SingleResidentModelManager` and the swap manager, serialize behind one lock.
**Verified:** 2026-09-17

The reply's lease is held for the adapter generator's whole lifetime, and
the credit bound ([028](028-converse-queue-backpressure.md), `CORTEX_SEAM_CONVERSE_BUFFER`) suspends generation INSIDE that lease once
the consumer stops dequeuing and the bound's credits are spent, so a stalled reader does not merely
stall itself. At the shipped bound of 256 events, a turn that emits fewer finishes and releases the lease
even when nobody reads it. Measured on the
[fold-under-load run](../../adr/ADR-0038-ranked-recall.md)
at a one-credit bound with the reader stalling 12 s: the stalled stream's reply held
the lease **16.52 s** against the 2.2 s to 3.6 s an unstalled reply holds it, and the next
stream's **fold waited 16.51 s** behind it. This predates the summary ([027](027-session-history-summarization.md)) and is not caused by it;
what the default-on fold changes is who pays, since a fold is now among the things that queue.
Neither obvious direction is free: the bound exists to cap a stalled stream's memory (the entry
that landed it is [028](028-converse-queue-backpressure.md)), and letting generation run ahead of the consumer to release the lease
sooner is the exact thing that bound prevents. A real fix is likelier to be a bound on how long a
suspended generation may hold the lease, which means the adapter abandoning a stream the
seam is no longer draining, and that is a port-shaped change rather than a knob.

## Trail

- 2026-08-08: Opened by the fold-under-load run on its way past, as the shipped backpressure
  behaving as designed with nobody having written down who pays for it.
- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket ran against the tree and fired
  nothing, recording that what remains open there is live-observation shaped, its trigger being a
  deployment doing something rather than a file saying something.
- 2026-09-11: read against the tree and not fired. The mechanism is as described and nothing bounds
  it yet: `ConverseStream` in `converse_stream.py` still takes one credit per event from an
  `asyncio.Semaphore(max_buffered_events)`, and `LlamaCppBackend.stream` still yields each event
  from inside `async with self._manager.acquire(model)` (`backend.py`), so a consumer that stops
  dequeuing suspends the generator with the lease held; the only timeout in the stream module is
  the confirm timeout. The nearest thing to the abandonment the body proposes is `abandon.py`, the
  unary-call abandonment log of 2026-08-20, whose own docstring says `Converse` announces no
  deadline and must keep announcing none, so it stops exactly short of this entry. The shipped
  stack still has one overlay as its one consumer and the tree records no report of one client
  stalling another's turn. The three references to entries `above` in the old area doc now name
  their tasks, and the run the readings came from is linked.
- 2026-09-17: not fired, and the trigger now names what decides it inside the tree. The mechanism is
  unchanged: `converse_stream.py` still builds `asyncio.Semaphore(max_buffered_events)` (line 125)
  and acquires a credit per event (line 264), and `backend.py` still streams inside
  `async with self._manager.acquire(model)` (line 141). Both manager implementations hold one
  `asyncio.Lock` for the lease (`model.py`, `residency.py`). No second consumer exists. The only
  production path to `Converse` is the overlay's, through the shell's `converse` command
  (`converse.rs` line 184); every Python `BrainServiceStub` user is under
  `brain/packages/orchestrator/tests/`. That command's loop
  awaits only `stream.next()`, because `Channel::send` in the pinned tauri 2.11.5 is a plain `fn`
  that calls the webview handler without waiting on it, so the one consumer cannot stop dequeuing
  short of the process being suspended. The scheduler is not a second lease holder either: its
  tasks run as subagents, and `subagent_builders.py` gives every roster entry a
  `SingleResidentModelManager` of its own, so their lock is not the cortex's. The shell does expect
  a newer turn to start while an older one still streams (`ConfirmRoute` clears by generation), and
  each turn's loop reads its own stream the same way. The body now says the stall starts only once the credits
  are spent: the run above measured it at a bound of one, and at the default of 256 a turn that emits
  fewer events releases the lease even when nobody reads it.
