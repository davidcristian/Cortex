# The toolchain-linked full build

**Status:** ongoing: an obligation on every change to these trees, not a check to run once
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

CI runs `cargo fmt` on both Rust trees outside `just check` and a cross-target clippy that
type-checks `os_windows` without linking it. Only a Windows build links them, so the "build" third
of the risk ADR-0011 named stays host-side.

**What this means in practice.** Any change touching `body/crates/os_windows` or
`body/app/src-tauri` is unproven until it has been built on Windows once. The checks catch format
and type errors; they cannot catch a link error.

**Do, once per such change:**

```powershell
cd body/app
npm run tauri build
```

The shell declares `os-windows` under `[target.'cfg(windows)'.dependencies]`, so a Windows build of
the shell links both Rust trees at once. The `npm run tauri dev` that every numbered check starts
with links them too, so a session that ran those has already covered whatever change it included;
the build command is the form to use when there is no session to attach it to.

**Pass.** It links and the app starts.

**Fail.** A link error, which is exactly the third of the risk the checks cannot reach. Record it
where the change was made, not here.

## Notes

- This was the only item in this directory with no command, added 2026-07-19, and it is the one
  repeated most often.
- The host index's recommended order lists neither this item nor the unbalanced COM initialization
  watch, and its item list keeps the two of them under a heading of their own rather than with the
  numbered checks. [ADR-0011](../../adr/ADR-0011-body-v1.md)'s 2026-07-19 mapping of its own user
  list points at this item as the ongoing one at the end of the same doc.
