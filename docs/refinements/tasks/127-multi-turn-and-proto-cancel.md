# Multi-turn within one stream plus proto `Cancel`

**Status:** open, waiting for its trigger
**Area:** body-overlay
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Trigger:** a body caller that needs a `Converse` stream to outlive its turn. On 2026-10-07 the
overlay's `submit` in `body/app/src/overlay/useOverlay.ts` returns while `isTurnActive`, so no
question is sent while another runs, and `turn_request` in `body/crates/rpc/src/converse.rs` sends
one `UserTurn` and no `Cancel`. A question accepted mid-turn, or a stop that must keep its stream
open, fires it.
**Verified:** 2026-10-07

The body sends one turn per `Converse` call and never sends `Cancel`; dropping the stream is how
v1 cancels (ADR-0011 decision 1 and risks). Slice 8.8 (ADR-0022) took the interleaving half, so
the body's client stream stays open past the first `UserTurn` to answer `ConfirmRequest`s
mid-turn.

**The proto and the whole brain half are already built.** `proto/body.proto:57` has
`Cancel cancel = 3`, round-tripped by `test_client_event_oneof_holds_a_cancel`. The server
supports multiple turns per stream and handles `Cancel` end to end: a `UserTurn` arriving mid-turn
is queued and starts when the running turn finishes (`_enqueue_turn`, `_start_next_turn`,
`_drain_turns` in `converse_stream.py`), and a `Cancel` stops the in-flight turn and drops the
queue while the stream stays open (`_cancel_turn`). Two tests assert it:
`test_cancel_behind_a_queued_turn_stops_current_and_drops_queued` and
`test_cancel_mid_confirm_drops_the_turn_and_the_stream_stays_open`.

The GPU lease releases cleanly on a mid-inference cancel with escalation off. The lease is then a
non-reentrant `asyncio.Lock` held across the whole streaming block
(`SingleResidentModelManager._lock`, taken in `LlamaCppBackend.stream`), and a `CancelledError`
propagates out through that `async with` and frees it before the next turn leases it. With
escalation on, the backend leases from the swap runtime's manager instead (`wiring.py:76`), which
the test below does not use.
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
then needs per-turn keying for Slice 8.8's single-slot `ConfirmRoute` and the `RpcConfirmer`'s
one-confirm-per-stream assumption: a map rather than one slot, contained in a route that is
already generation-tagged.

**Stop already ends the turn without either part.** The overlay's Stop sends the shell's
`stop_turn`, and the `converse` command (`body/app/src-tauri/src/converse.rs`) drops the turn's
RPC, which the brain reads as a dropped stream: `events()`'s `finally` cancels the turn task, the
model's generation ends, the lease is freed, and the store keeps the question with no reply. Two
streams naming one session no longer interleave either, since the brain runs a session's turns one
at a time across streams (`SerialTurnRunner`, `session_turns.py`). What remains here is needed only
when one stream should hold several turns.

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
- 2026-09-24: Read against the tree; not fired. No task under `docs/host/tasks/` and no runbook
  records a stopped turn holding the lease. The handoff wait commits of this date change what a
  waiting turn shows, not whether a stopped one keeps running. Three citations had drifted: the
  `Cancel` field is at `proto/body.proto:57` (line 52 on 2026-09-17), the `Protocol`
  error at `body/crates/rpc/src/converse.rs:138`, and the Tauri loop's one early exit at
  `body/app/src-tauri/src/converse.rs:205`. The 2026-09-17 line counted five tests where the body
  names four. The lease paragraph held only with escalation off, since `wiring.py:76` hands the
  backend the swap manager when escalation is on, and it now says so.
- 2026-10-02: Read against the tree; not fired. No task under `docs/host/tasks/` and no runbook
  records a stopped turn holding the lease. The headless handoff client added that day sends one
  `UserTurn` and its `ConfirmResponse`s through the same `turn_request` and reads to the terminal
  event, so it adds a second caller of the one-turn shape and no `Cancel`. The trigger said CI
  could not take the reading because the Tauri command runs only on the host; the brain cannot tell
  a stopped turn from one whose client keeps reading, so the trigger now names what only use shows.
  The attached-image commits moved two sites: the `Protocol` error is at
  `body/crates/rpc/src/converse.rs:154` and the Tauri loop's one early exit at
  `body/app/src-tauri/src/converse.rs:248`. The `Cancel` field is still at `proto/body.proto:57`,
  the escalation lease still at `wiring.py:76`, and the four tests named above still exist.
- 2026-10-07: The trigger fired. On the Linux shell against the real cortex, a Stop came 57% of
  the way through a turn's generation, the generation ran to its end, and a question sent 1.2 s
  after the Stop reached the model only once it had
  ([readings](../../readings/overlay-turn-flows.md#stop)). The simple fix was built: the overlay's
  cancel sends `stop_turn`, the shell drops the RPC, and on the same shell the model freed its slot
  within 15 ms of the cancel and the next question did not wait
  ([readings](../../readings/overlay-turn-flows.md#with-the-abort)). The question it named first was
  settled by keeping the brain's rule: a cancelled turn stores no reply. That the overlay goes on
  writing a stopped reply, and keeps text the chat does not, is
  [R-816](816-a-stopped-reply-goes-on-writing-and-is-not-kept.md). The turn order across streams was
  fixed in the same change with a lock per session in the brain. The task now holds only several
  turns per stream and a client `Cancel`, whose trigger is new.
