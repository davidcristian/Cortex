# The body-side Notify OS trait and Tauri toast

**Status:** landed 2026-07-16
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Recorded in the [ADR-0025 notify addendum](../../adr/ADR-0025-scheduling-reminders.md). The last of
the three in-slice remainders, so push delivery exists end to end: the ticker's `notify` call
reaches a real handler instead of the shape-now `Unimplemented`. `body_core::os::notify` holds the
port (`Notify::show(&Notification) -> Result<bool, NotifyError>`, `Send + Sync` like `AudioControl`,
in its own submodule because `os.rs` was at the line cap), `os_linux`/ `os_macos` get the stubs
behind the coverage escape hatch, `os_windows` gets the real `WindowsNotify` (a `ToastGeneric` WinRT
toast), and `body_rpc`'s server takes the second backend generic the ADR predicted.
**Three corrections to that ADR's own framing, each found by reading the code:** (1) it placed the
Windows implementation in the **Tauri shell**, but the shell's own contract is that it holds no
branchy decision, and `os_windows` already is the per-platform backend home and already
`cfg(windows)`, so the backend lands there and the shell keeps only which backend to build and from
which env var; (2) `VolumeService` could not keep its name once the server answered two unrelated
capabilities, so it is `OsService<A: AudioControl, N: Notify>` (a rename, no behavior change); (3)
the ADR-0023 `unsafe` authorization widened by one line, still COM only and still `os_windows` only,
because WinRT projections are safe but activating a WinRT factory needs a COM-initialized thread the
tokio workers do not have. The decision that matters most is **where the inert-text rule lives**:
the ADR phrased it as an instruction to the Windows file, which would have rested the whole
data-not-instructions posture on the one file no gate ever sees, so `Notification::new` applies it
in the pure core instead (control characters replaced by spaces, never dropped, so words cannot
fuse; each line bounded at 200 characters with a trailing ellipsis, so an oversized payload degrades
a reminder rather than losing it, the same bias as the daylight-saving fold and the month-length
clamp).
**Escaping split off from sanitizing** once the two were examined: a toast template is XML, but a
future Linux backend renders through markup-limited text where a pre-escaped string would show the
entity literally, and a backend that escapes for itself would double-escape, so `escape_xml` is a
gated helper the renderer calls rather than something the value bakes in. `shown=false` turned out
to be a real answer rather than a dead wire field, because `ToastNotifier.Setting` reports *before*
showing that notifications are off for this app, user, or policy, which is a decline and not a
failure; the brain treats it exactly like an error either way, so the split buys only accurate logs.
The taint badge is a fixed body-authored `from an untrusted source` line, for the reason the
overlay's card already learned (whoever writes the reminder must never write the label that
describes it). CI-gated at 100% line+region+branch with nine guards mutation-proven (the
control-character replacement, the length bound, the truncation mark, the taint-conditional
attribution, the ampersand escape, the declined verdict, the unavailable status mapping, and the
title/body and taint mapping into the value), plus a compile-only cross-check: both `os_windows` and
the ungated Tauri shell were type-checked and clippy-checked against the real `windows` crate for
the `x86_64-pc-windows-msvc` target from Linux. Remaining, and unchanged from what this slice always
owed: the **Host-Windows** look at a real toast (runbook
[scheduling.md](../../runbooks/scheduling.md)), which **moved to
[docs/host/windows-desktop.md](../../host/index.md#windows-desktop) on 2026-07-19** with that
sentence kept verbatim, joined there by the pull surface's own user check, which until that day had
no line in any backlog although ADR-0025's host line and the runbook both named it. Neither was ever
counted in this area, so no count moves. Newly deferred behind it: **toast activation routing** (its
own entry below). Unblocked by it, and still deferred on their own merits: the **task-outcome
delivery notification** and the **push retry policy**.

## Trail

- 2026-07-16: The area held at 10 when this closed and opened one entry behind it, toast
  activation routing, which the index records as the backlog working as intended rather than a
  stalled area.
- 2026-07-19: The Host-Windows look at a real toast moved to
  [docs/host/](../../host/index.md) with the host-side extraction, joined there by the pull
  surface's own user check. Neither had ever been counted in this area, so the move took no
  count with it.
