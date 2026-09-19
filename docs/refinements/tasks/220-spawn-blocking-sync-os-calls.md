# `spawn_blocking` for the synchronous OS calls

**Status:** done 2026-07-16
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

The `AudioControl` port is synchronous and was called inline in the async `BodyService` handler.
Moving it to `spawn_blocking` is a body-side change behind the unchanged trait, and the entry was
accurate: the ports really are synchronous, the handlers really did call them inline, and nothing
about the interface had to move ([ADR-0023 decision 11](../../adr/ADR-0023-body-gateway-volume.md)).

It covers three calls rather than one. The reminder toast has the same shape, so `off_worker` in
`body_rpc::server` serves `get_volume`, `set_volume` and `notify`; the toast is the slower backend,
since activating a WinRT factory and asking `ToastNotifier.Setting` both cross to the notification
service. The entry's "fine at personal scale" was also the weaker half of the case: the cost is not
the COM call's latency, it is that `BodyService` shares its runtime with the overlay's own calls, so
a parked worker delays work that has nothing to do with audio.

The safety question was checked before the change, because a `spawn_blocking` that moves a `!Send`
COM object to another thread is a bug rather than a fix: neither backend holds one.
`WindowsAudioControl` is a unit struct that resolves its `IAudioEndpointVolume` per call,
`WindowsNotify` holds only an app-id `String`, and both ports were already `Send + Sync`, so the
whole COM lifetime stays inside one closure on one thread. The backends move behind an `Arc` in
`OsService` purely to be lent to that thread.

One behaviour changed for the better: a backend that panics mid-call used to kill the connection,
which the brain saw as `Cancelled`, and now answers `Internal` like any other backend fault, over a
channel that is still usable afterwards. Proven rather than assumed: the fakes record which thread
each call ran on, and a current-thread test runtime makes an inline call observable, so reverting
`off_worker` makes three tests fail. Checked live as well, with the brain's own `GrpcBodyGateway`
dialling the real Rust server over loopback: the round trip with a token passed, without one it was
still `UNAUTHENTICATED`, and the server log shows all three OS calls on a blocking-pool thread.

## History

- 2026-07-16: Closed. The area's two-part first entry closed as two different outcomes. This half
  grew on the way in, covering three handlers rather than one, and it opened the unbalanced COM
  initialization entry behind it, now that the calls run on a short-lived thread pool.
