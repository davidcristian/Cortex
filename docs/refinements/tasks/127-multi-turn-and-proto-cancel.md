# Multi-turn within one stream plus proto `Cancel`

**Status:** open, fix when it bites
**Area:** body-overlay
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Trigger:** The same real model swap the reconnect and streamed-status entries wait on, which is what makes mid-turn compute expensive enough for a real abort to earn its keep.

One turn per `Converse`
call; drop-to-cancel covers v1 (ADR-0011 decision 1 / risks). The interleaving half was
taken by **Slice 8.8** (ADR-0022): the body's client stream now stays open past the first
`UserTurn` to answer `ConfirmRequest`s mid-turn. Still deferred: multiple turns per call
body-side and the client actually sending `Cancel` (drop-to-cancel remains the mechanism).
When multiple turns per call land, Slice 8.8's single-slot `ConfirmRoute` (Tauri) and the
`SeamConfirmer`'s "at most one confirm outstanding per stream" assumption need per-turn keying
(a map, not one slot); the route is already generation-tagged, so the change is contained there.
- **Read against the code 2026-07-16: the proto and the whole server half are already built and
  proven; what remains is body-side only, and its two parts are coupled so the smaller cannot
  cleanly precede the larger. Sharpened to fix-when-it-bites with the same Slice 11 trigger as
  the reconnect and streamed-status entries.** Both halves the entry names are satisfied on the
  proto and the brain:
  - **The proto `Cancel` exists** (`proto/body.proto` `Cancel cancel = 3`, in the seam since the
    first proto commit), round-tripped by `test_client_event_oneof_carries_a_cancel`
    (`brain/packages/seam/tests/test_facade.py`).
  - **The server carries multiple turns per stream and handles `Cancel` end to end.** A
    `UserTurn` arriving mid-turn is queued and starts when the running turn finishes
    (`_enqueue_turn`/`_start_next_turn`/`_drain_turns`, `converse.py`); a `Cancel` stops the
    in-flight turn and drops the queue and the stream stays open (`_cancel_turn`, dispatched from
    the pump on `kind == "cancel"`). Pinned by `test_cancel_behind_a_queued_turn_stops_current_and_drops_queued`
    (A dies mid-stream, B never runs, A's user message persisted with no partial reply) and
    `test_cancel_mid_confirm_drops_the_turn_and_the_stream_stays_open` (a pending confirm on a
    cancelled turn runs no tool and the stream survives), both in `test_converse.py` /
    `test_converse_confirm.py`.
  - **The lease-cancellation crux (the tricky part the entry flags) is clean and now has a
    dedicated proof.** The GPU lease is a non-reentrant `asyncio.Lock` held across the whole
    streaming block (`SingleResidentModelManager._lock`, taken in `LlamaCppBackend.stream` via
    `async with manager.acquire(...)`); a `CancelledError` mid-inference propagates out through
    that `async with` and frees the lock before the next turn leases it. Proven by
    `test_cancelling_mid_stream_frees_the_model_lease` (`brain/packages/inference/tests/test_backend.py`):
    it suspends a turn mid-stream with the lease held, cancels it, and asserts a fresh acquire
    returns at once. Proved able to fail: releasing the lock outside a `finally` (so a
    mid-`yield` cancel skips it) deadlocks the re-acquire and makes the test fail. No partial reply is persisted
    on cancel (`TurnEngine.handle_turn`'s `finally: await loop.aclose()` drops the in-flight
    generation; `test_aclose_mid_generation_keeps_user_and_drops_partial_reply`, `test_engine.py`).
  - **What is genuinely deferred is body-side and coupled.** The `BrainTransport::converse` port
    is one turn per call (`turn_request` sends exactly one `UserTurn`, `body/crates/rpc/src/converse.rs`),
    and the overlay opens a fresh `Converse` per submit (`useOverlay.ts`). A client-sent `Cancel`
    cannot cleanly precede body multi-turn: on the one-turn-per-call body, a `Cancel` then a
    half-close ends the body stream **with no terminal event** (the server emits none for a
    cancelled turn), which `converse_turn` maps to `TransportError::Protocol("converse stream
    ended before the turn completed")`. So client `Cancel` needs either multi-turn-within-one-stream
    (keep the stream and send the next `UserTurn`, the case that makes it worth having) or a new terminal
    cancelled-ack (a server-semantics change), and multi-turn-within-one-stream carries the
    per-turn-confirm-keying knock-on above.
  - **Today's Stop is UI-only in the Tauri embedding, and that is why the deferral is
    fix-when-it-bites rather than actionable-now.** The overlay's Stop denies a pending confirm
    and mutes the JS sink (`tauriBridge.ts` sets `live = false`), but does not half-close or abort
    the RPC (documented in `useOverlay.ts`), so the Rust `converse` command streams the turn to
    completion: the brain finishes generating, persists the **full** reply, and holds the lease
    until the turn ends naturally. Drop-to-cancel therefore behaves as "stop showing me this
    turn", not "abort the compute", and the overlay can show a truncated reply while the store
    keeps the full one. That is adequate at loopback personal scale where compute is cheap; a real
    abort (release the lease, drop the partial, keep the store consistent) is worth building only when
    Slice 11's real model swap makes mid-turn compute expensive and evictable, the same trigger
    the reconnect and streamed-brain-status deferrals wait on. The clean v1 fix for one-turn-per-call
    is a real drop-to-cancel: make the Tauri command abort its RPC on Stop (a body-local signal, no
    proto change), which the brain already tears down cleanly through `events()`'s finally. Both
    that and the multi-turn+`Cancel` build live entirely in the ungated, host-validated Tauri
    shell + overlay glue, so neither is a gated slice today.

## Trail

- 2026-07-16: Read against the code and sharpened rather than built. The proto `Cancel` has existed
  since the first proto commit, and the server already carries multiple turns per stream and handles
  `Cancel` end to end, lease release on a mid-inference cancel included, so what remains is
  body-side glue whose two parts are coupled. The area count did not move.
- 2026-08-09: A trigger sweep read this against the tree and found it half fired and deliberately
  not picked. The brain-side swap it names as its trigger has landed and the body glue it waits on
  is confirmed absent, `body/crates/rpc/src/converse.rs` carrying no `Cancel` at all, while the
  economic half of the trigger, compute expensive enough that muting the sink stops being adequate,
  still wants a live deployment.
