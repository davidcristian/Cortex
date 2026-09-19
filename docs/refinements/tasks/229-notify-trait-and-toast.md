# The body-side Notify trait and Windows toast

**Status:** done 2026-07-16
**Area:** scheduling
**Origin:** [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md)

Decided in [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md) decisions 1 to 5. Push
delivery now works end to end: the ticker's `notify` call reaches a real handler instead of
`Unimplemented`. `body_core::os::notify` defines the port (`Notify::show(&Notification) ->
Result<bool, NotifyError>`, `Send + Sync` like `AudioControl`, in its own submodule because `os.rs`
was at the line cap). `os_linux` and `os_macos` get stubs behind the coverage escape hatch,
`os_windows` gets `WindowsNotify`, which shows a `ToastGeneric` WinRT toast, and `body_rpc`'s
server takes a second backend type parameter. `VolumeService` was renamed to `OsService<A:
AudioControl, N: Notify>`, since it now serves two unrelated capabilities.

Three things came out different from the ADR's description:

- The Windows implementation is in `os_windows`, not the Tauri shell. The shell only chooses which
  backend to build, from an env var.
- The `unsafe` authorization from ADR-0023 widened by one line, still COM only and still inside
  `os_windows`: activating a WinRT factory needs a COM-initialized thread, which the tokio workers
  do not have.
- The rule that toast text is data and never an instruction is applied by `Notification::new` in
  the pure core, not in the Windows file, which no check ever reads. Control characters become
  spaces rather than being dropped, so words cannot run together, and each line is cut at 200
  characters with a trailing ellipsis, so an oversized payload shortens a reminder instead of
  losing it.

Escaping is separate from sanitizing. A toast template is XML, but a future Linux backend renders
through markup-limited text, where a pre-escaped string would show the entity literally and a
backend that escapes for itself would escape twice. So `escape_xml` is a helper the renderer calls
rather than something the value applies. `shown=false` is a real result and not a dead field:
`ToastNotifier.Setting` reports before showing that notifications are off for this app, user or
policy, which is a refusal rather than a failure. The brain treats both the same, so the
distinction only makes the logs accurate. The taint label is a fixed body-written `from an
untrusted source` line, because whoever writes the reminder must not also write the label that
describes it.

Tested in CI at 100% line, region and branch coverage, with nine checks proven by mutation, plus a
compile-only cross-check: `os_windows` and the Tauri shell were type-checked and clippy-checked
against the real `windows` crate for the `x86_64-pc-windows-msvc` target from Linux.

## History

- 2026-07-16: Closed, and one entry opened behind it: toast activation routing.
- 2026-07-19: The Windows-desktop look at a real toast moved to
  [docs/host/](../../host/index.md), together with the pull surface's own user check. Neither had
  been counted in this area, so no count changed.
