# `spawn_blocking` for the sync OS calls

**Status:** landed 2026-07-16
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

Body gateway & OS actions in Slice 9 ([ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)): each
behind the unchanged `BodyGateway`/`AudioControl`/`BodyService` seams.

The `AudioControl` port is sync and called inline in
the async `BodyService` handler (fine at personal scale, as it is a fast COM call); moving it to
`spawn_blocking` is a body-side tweak behind the unchanged trait.

Now covers three calls rather than one ([ADR-0023
addendum](../../adr/ADR-0023-body-gateway-volume.md)).
The entry was accurate: the ports really are sync, the handlers really did call them
inline, and nothing about the seam had to move. Two things it could not have known. **The
reminder toast joined the same shape**, so `off_worker` in `body_rpc::server` serves
`get_volume`, `set_volume`, and `notify`; the toast is the slower of the two backends, since
activating a WinRT factory and asking `ToastNotifier.Setting` both cross to the notification
service. And **the entry's own "fine at personal scale" was the weaker half of the case**:
the cost is not the COM call's latency, it is that `BodyService` shares its runtime with the
overlay's own seam calls, so a parked worker delays work that has nothing to do with audio.
**The safety question the change turns on was checked before it was made**, because a
`spawn_blocking` that moves a `!Send` COM object to another thread is a bug and not a fix:
neither backend holds one. `WindowsAudioControl` is a unit struct that resolves its
`IAudioEndpointVolume` per call, `WindowsNotify` holds only an app-id `String`, and both
ports were already `Send + Sync`, so the whole COM lifetime stays inside one closure on one
thread. The backends move behind an `Arc` in `OsService` purely to be lent to that thread.
**One behaviour changed, for the better:** a backend that panics mid-call used to kill the
connection (the brain sees `Cancelled`); it now answers `Internal` like any other backend
fault, which the contract tests assert over a channel that is still usable afterwards. Proven
rather than assumed: the fakes record which thread each call ran on, and a current-thread test
runtime makes an inline call observable (reverting `off_worker` turns three tests red).
Validated live as well, with the brain's own `GrpcBodyGateway` dialling the real Rust server
over loopback: tokened round-trip passed, untokened still `UNAUTHENTICATED`, and the server
log shows all three OS calls on a blocking-pool thread.

## Trail

- 2026-07-16: The area's two-part first entry closed as two different outcomes, the second area in
  one day to show that an entry naming two things is two entries. This half grew on the way in: the
  reminder toast is the same shape of synchronous OS call, so the change covers three handlers, and
  the safety question was answered from the backends' types before the change was made. The pass
  opened the unbalanced COM initialization entry behind it, now that the calls run on an ephemeral
  thread pool.
