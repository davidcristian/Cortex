# The Windows backends build a second windows crate beside Tauri's

**Status:** open, actionable
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

`body/crates/os_windows/Cargo.toml` asks for `windows = "0.58"`, while the Tauri stack the shell
links (`tauri`, `tauri-runtime`, `tauri-runtime-wry`, `tao`, `wry`, `webview2-com` and
`webview2-com-sys`) depends on `windows` 0.61.3. So `body/app/src-tauri/Cargo.lock` resolves two
`windows` packages, 0.58.0 and 0.61.3, and a Windows build of the shell compiles both. The body
workspace's own `body/Cargo.lock` holds only 0.58.0, because nothing there links Tauri.

The fix is to move `os_windows` to the `windows` version the shell's Tauri resolves, with the same
feature list, and to port the calls whose signatures changed between the two. `just check-shell`
type-checks the result for `x86_64-pc-windows-msvc`, so the port can be done and checked on Linux.
What it cannot check is runtime behaviour: the volume, toast, capture and focus backends are each
first run on a Windows desktop by host tasks 002, 003, 012 and 013, none of them attempted yet, so
the bump adds no host task of its own. It also lowers the cost of adopting a safe Core Audio crate
([R-223](223-safe-core-audio-wrapper.md)) whose `windows` version matches Tauri's.

## History

- 2026-10-03: Filed from the premise review of R-223, whose entry said adopting a crate on
  `windows` 0.62 would compile a second version unless the body moved first. The shell already
  compiles two, and no task recorded that move.
