# Unbalanced COM initialization on the blocking pool

**Status:** open, waiting for its trigger
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Verified:** 2026-09-17
**Trigger:** either of two readings. On a Win32 desktop, the watch item in `docs/host/`: a volume or
toast call failing with a COM error after a long uptime, or the body process's handle count climbing
across bursts of OS actions spaced further apart than tokio's blocking thread keep-alive (10 s by
default, and nothing under `body/` sets another), rather than returning to its idle level between
them. The thread count is the weaker witness, because tokio exits an idle blocking thread after that
keep-alive whatever its apartment. In the tree,
`grep -rn 'CoInitializeEx\|CoUninitialize' body/crates/os_windows/src/` reports two initializations
and no uninitialization as of 2026-09-17; a third initialization, or any `CoUninitialize`, means the
shape below has changed and this entry needs rereading before the observation does.

Two Windows backends call `CoInitializeEx(COINIT_MULTITHREADED)` per call and never
`CoUninitialize`. That was already true on the async workers, where the thread set is small and
lives as long as the process. On the blocking pool it applies to threads tokio creates on demand and
reaps after an idle timeout, so a long uptime with sporadic OS actions joins the multithreaded
apartment from many threads that then exit without leaving it. Nothing observed has gone wrong, and
it is arguably the behaviour a resident body wants, but it is documented as incorrect.

The fix is to send the OS calls through one dedicated COM-initialized thread, which also avoids
repeating the initialization. Uninitializing at the end of each call is the wrong fix, since it
would tear down and rebuild apartment membership per call.

Only a Windows desktop can observe it; neither CI nor a Linux run can. The observation is the watch
item in [docs/host/windows-desktop.md](../../host/index.md#windows-desktop), and the fix stays here
because it is code.

`grep -rn 'CoInitializeEx\|CoUninitialize' body/crates/os_windows/src/` reports `audio.rs:43`,
inside `WindowsAudioControl::endpoint`, and `notify.rs:61`, at the top of `WindowsNotify::show`.
Both ignore the returned status, which is what makes them idempotent per thread. `CoUninitialize`
appears in no Rust source.

The crate holds five modules: `audio` and `notify` initialize; `windows` reaches the OS through
`global-hotkey`, which owns whatever it needs; and `screen` and `focus`, added on 2026-07-18 and
2026-08-10, are raw Win32 with no COM at all. That was a decision rather than an accident, recorded
in ADR-0029: GDI was chosen over DXGI Desktop Duplication and `Windows.Graphics.Capture` partly so
that screen capture would not put a third initialized backend on the blocking pool.

`body_rpc::server::off_worker` has four call sites: `get_volume` and `set_volume` in
[server.rs](../../../body/crates/rpc/src/server.rs), which both reach `endpoint`, `notify` in the
same file, and the capture in [screen.rs](../../../body/crates/rpc/src/screen.rs), which does not.
So the exposure grew by one handler, not by one apartment.

## History

- 2026-07-16: Opened behind the `spawn_blocking` change, which moved the synchronous OS calls onto
  tokio's short-lived blocking pool and made the imbalance visible.
- 2026-07-19: Stayed in this backlog when host-side work was extracted to
  [docs/host/](../../host/index.md), because the work itself is code even though only the host's
  hardware can observe the trigger.
- 2026-09-08: Rechecked from the source and not fired. The description now names the two
  initializing backends rather than saying both of them, the crate having grown from three modules
  to five.
- 2026-09-10: Rechecked again, every count unchanged. The observation half is out of reach here,
  there being no Win32 desktop session on this machine.
- 2026-09-17: Rechecked from the source and unchanged: no commit since 2026-09-10 touches
  `body/crates/os_windows`, `body/crates/rpc/src/server.rs` or `body/crates/rpc/src/screen.rs`. The
  trigger now names a reading a Windows run can take, the handle count across bursts spaced past the
  blocking pool's keep-alive, in place of thread growth the user sees. A safe Core Audio crate would
  not close this by itself: `volumecontrol-windows`, the nearest one
  ([R-223](223-safe-core-audio-wrapper.md)), initializes and uninitializes around every call, which
  is the fix rejected above.
