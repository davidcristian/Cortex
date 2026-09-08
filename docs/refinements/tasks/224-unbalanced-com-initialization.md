# Unbalanced COM initialization on the blocking pool

**Status:** open, fix when it bites
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** any COM failure or thread growth the user sees on Windows after a long session. Only a
Win32 desktop can show it, and the standing observation is the `windows-desktop` watch item in
`docs/host/`. The code half is rechecked with
`grep -rn 'CoInitializeEx\|CoUninitialize' body/crates/os_windows/src/`, which reports two
initializations and no uninitialization as of 2026-09-08; a third initialization, or any
`CoUninitialize`, means the shape below has changed and this entry needs rereading before the
observation does.

Body gateway & OS actions in Slice 9 ([ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)): each
behind the unchanged `BodyGateway`/`AudioControl`/`BodyService` seams.

Two Windows backends call `CoInitializeEx(COINIT_MULTITHREADED)` per call and never
`CoUninitialize`. That was already true on the async workers, where the thread set is small and
lives as long as the process; on the blocking pool it applies to threads tokio creates on demand and
reaps after an idle timeout, so a long uptime with sporadic OS actions joins the MTA from many
threads that then exit unbalanced. Harmless as far as anything observed goes, and arguably the
behaviour a resident body needs (the apartment stays up), but it is documented as incorrect and it
is now the shape of the code. The fix is to funnel the OS calls through one dedicated
COM-initialized thread instead, which also amortizes the initialization. Uninitializing at the end
of each call is the wrong fix, since it would tear down and rebuild MTA membership per call.
Host-Windows to observe; neither CI nor a Linux run can see it. The observation itself is the
standing watch item in
[docs/host/windows-desktop.md](../../host/index.md#windows-desktop); the fix stays here, counted,
because it is code.

**Re-read 2026-09-08. The trigger has not fired, and this machine cannot fire it.** There is no
Win32 desktop session here, the crate is `cfg(windows)` and compiles to nothing on Linux, and
`just check` does not run `check-shell`, so nothing in the gate executes these calls. What can be
read is the source, and it says the same thing it said, over a larger crate.

**The count of initializations is still two, and there is still no uninitialization.**
`grep -rn 'CoInitializeEx\|CoUninitialize' body/crates/os_windows/src/` reports
`audio.rs:43`, inside `WindowsAudioControl::endpoint`, and `notify.rs:61`, at the top of
`WindowsNotify::show`. Both ignore the returned status, which is what makes them idempotent per
thread. `CoUninitialize` appears nowhere in the repository.

**Two modules have joined the crate since, and neither adds a third apartment.** The crate
holds five modules today: `audio` and `notify` initialize; `windows` reaches the OS through
`global-hotkey`, which owns whatever it needs; and `screen` and `focus`, added 2026-07-18 and
2026-08-10, are raw Win32 with no COM at all. That was a decision rather than an accident, recorded
in ADR-0029: GDI was chosen over DXGI Desktop Duplication and `Windows.Graphics.Capture` partly so
that screen capture would not put a third initialized backend on the blocking pool.

**The blocking pool now carries four calls, three of which initialize.**
`body_rpc::server::off_worker` has four call sites: `get_volume` and `set_volume` in
[server.rs](../../../body/crates/rpc/src/server.rs), which both reach `endpoint`, `notify` in the
same file, and the capture in [screen.rs](../../../body/crates/rpc/src/screen.rs), which does not.
So the exposure grew by one handler, not by one apartment, and the fix is unchanged: one dedicated
COM-initialized thread the OS calls are funnelled through.

## Trail

- 2026-07-16: Opened behind the landed `spawn_blocking`, the pass that moved the synchronous OS
  calls onto tokio's ephemeral blocking pool having made the imbalance visible.
- 2026-07-19: Stayed in this backlog when host-side work was extracted to
  [docs/host/](../../host/index.md), because the work itself is code and belongs with its area even
  though only the host's hardware can observe the trigger.
- 2026-09-08: Trigger rechecked from the source and not fired. Two initializations, no
  uninitialization, three of four blocking-pool call sites reaching an initializing backend. The
  description names the two initializing backends instead of saying both of them, the crate having
  grown from three modules to five.
