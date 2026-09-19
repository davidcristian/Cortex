# Multi-turn within one stream plus proto `Cancel`

**Status:** open, waiting for its trigger
**Area:** body-overlay
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Trigger:** a record in the tree, a host task or a runbook reading, of a turn the person stopped
whose generation went on holding the model lease against their next submit or a model swap. Until
that is written down, muting the sink is adequate. CI cannot produce the reading, because the Tauri
command that streams a stopped turn to its end runs only on the host.
**Verified:** 2026-09-17

The body sends one turn per `Converse` call and never sends `Cancel`; dropping the stream is how
v1 cancels (ADR-0011 decision 1 and risks). Slice 8.8 (ADR-0022) took the interleaving half, so
the body's client stream stays open past the first `UserTurn` to answer `ConfirmRequest`s
mid-turn.

**The proto and the whole brain half are already built.** `proto/body.proto:97` has
`Cancel cancel = 3`, round-tripped by `test_client_event_oneof_carries_a_cancel`. The server
supports multiple turns per stream and handles `Cancel` end to end: a `UserTurn` arriving mid-turn
is queued and starts when the running turn finishes (`_enqueue_turn`, `_start_next_turn`,
`_drain_turns` in `converse_stream.py`), and a `Cancel` stops the in-flight turn and drops the
queue while the stream stays open (`_cancel_turn`). Two tests assert it:
`test_cancel_behind_a_queued_turn_stops_current_and_drops_queued` and
`test_cancel_mid_confirm_drops_the_turn_and_the_stream_stays_open`.

The GPU lease releases cleanly on a mid-inference cancel. It is a non-reentrant `asyncio.Lock`
held across the whole streaming block (`SingleResidentModelManager._lock`, taken in
`LlamaCppBackend.stream`), and a `CancelledError` propagates out through that `async with` and
frees it before the next turn leases it.
`test_cancelling_mid_stream_frees_the_model_lease` suspends a turn mid-stream with the lease held,
cancels it, and asserts a fresh acquire returns at once; it was proved able to fail by releasing
the lock outside a `finally`, which deadlocks the re-acquire. No partial reply is persisted, since
`TurnEngine.handle_turn`'s `finally: await loop.aclose()` drops the in-flight generation.

**What is deferred is body-side, and its two parts are coupled.** `BrainTransport::converse` is
one turn per call (`turn_request` sends exactly one `UserTurn`,
`body/crates/rpc/src/converse.rs`), and the overlay opens a fresh `Converse` per submit
(`useOverlay.ts`). A client-sent `Cancel` cannot come first on its own: with one turn per call, a
`Cancel` then a half-close ends the body stream with no terminal event, since the server emits
none for a cancelled turn, and `converse_turn` maps that to
`TransportError::Protocol("converse stream ended before the turn completed")`. So client `Cancel`
needs either multiple turns in one stream, which is also what makes it worth having, or a new
terminal cancelled acknowledgement, which is a server-semantics change. Multiple turns per stream
then needs per-turn keying for Slice 8.8's single-slot `ConfirmRoute` and the `SeamConfirmer`'s
one-confirm-per-stream assumption: a map rather than one slot, contained in a route that is
already generation-tagged.

**Today's Stop is UI-only.** The overlay's Stop denies a pending confirm and mutes the JS sink
(`tauriBridge.ts` sets `live = false`) but does not half-close or abort the RPC, so the Rust
`converse` command streams the turn to completion: the brain finishes generating, persists the
full reply, and holds the lease until the turn ends. Stop therefore means "stop showing me this
turn" rather than "abort the compute", and the overlay can show a truncated reply while the store
keeps the whole one. That is adequate at loopback personal scale. A real abort is worth building
when mid-turn compute becomes expensive and evictable. The simple fix for one turn per call is to
make the Tauri command abort its RPC on Stop, a body-local signal with no proto change, which the
brain already tears down cleanly through `events()`'s `finally`. Both that and the
multi-turn-plus-`Cancel` build live entirely in the Tauri shell and overlay glue.

## History

- 2026-07-16: Read against the code and sharpened rather than built. The area count did not move.
- 2026-08-09: A trigger review found it half fired and deliberately not picked. The brain-side
  swap it named as its trigger had shipped and the body glue was confirmed absent,
  `body/crates/rpc/src/converse.rs` having no `Cancel` at all, while the cost half of the trigger
  still wants a live deployment.
- 2026-09-11: Read against the tree; still not fired. The brain's handlers moved to
  `converse_stream.py` when the module split, and every test named here still exists. The Tauri
  `converse` command still streams the turn to completion: its loop leaves early only when
  `channel.send` fails, which is the webview going away rather than Stop. The two sibling entries
  this trigger used to name have moved on their own, so the trigger line now says what remains
  here.
- 2026-09-17: Read against the tree; not fired. No task under `docs/host/tasks/` and no runbook
  records a stopped turn holding the lease, and the trigger now names that record instead of a
  report. Every claim above holds: `proto/body.proto:97`, the one `UserTurn` from `turn_request`
  and the `Protocol` error at line 145, the four brain handlers in `converse_stream.py`, the five
  tests where the body places them, and
  `body/app/src-tauri/src/converse.rs:184` still leaving its loop only when `channel.send` fails.
  The comment beside `TauriBridge.converse`'s cancellation said that dropping the channel
  half-closes the RPC, which contradicted `useOverlay.ts`, and it now says the command runs on.
