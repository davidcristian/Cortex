# Unbalanced COM initialization on the blocking pool

**Status:** open, fix when it bites
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** Any COM failure or thread growth the user sees on Windows after a long session.

Body gateway & OS actions in Slice 9 ([ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)): each
behind the unchanged `BodyGateway`/`AudioControl`/`BodyService` seams.

Both Windows backends call `CoInitializeEx(COINIT_MULTITHREADED)` per call and never
`CoUninitialize`. That was already true on the async workers, where the thread set is small and
lives as long as the process; on the blocking pool it applies to threads tokio creates on demand and
reaps after an idle timeout, so a long uptime with sporadic OS actions joins the MTA from many
threads that then exit unbalanced. Harmless as far as anything observed goes, and arguably the
behaviour a resident body needs (the apartment stays up), but it is documented as incorrect and it
is now the shape of the code. The trigger is any COM failure or thread growth the user sees on
Windows after a long session: funnel the OS calls through one dedicated COM-initialized thread
instead, which also amortizes the initialization. Uninitializing at the end of each call is the
wrong fix, since it would tear down and rebuild MTA membership per call. Host-Windows to observe;
neither CI nor a Linux run can see it. The observation itself is the standing watch item in
[docs/host/windows-desktop.md](../../host/index.md#windows-desktop); the fix stays here, counted,
because it is code.

## Trail

- 2026-07-16: Opened behind the landed `spawn_blocking`, the pass that moved the synchronous OS
  calls onto tokio's ephemeral blocking pool having made the imbalance visible.
- 2026-07-19: Stayed in this backlog when host-side work was extracted to
  [docs/host/](../../host/index.md), because the work itself is code and belongs with its area even
  though only the host's hardware can observe the trigger.
