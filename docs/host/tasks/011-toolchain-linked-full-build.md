# The toolchain-linked full build

**Status:** standing: an obligation on every change to these trees, not a check to run once
**Sitting:** windows-desktop
**Capability:** W
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

CI checks `cargo fmt` on both ungated Rust trees and runs a cross-target clippy that type-checks
`os_windows` without linking. Only a Windows build links them.

Kept verbatim from [refinements/repo-gates.md](../../refinements/index.md#repo-gates):

> a toolchain-less build, by contrast, is out of reach, so the "build" third of the risk ADR-0011
> named stays host-side

**What this means in practice.** Any change touching `body/crates/os_windows` or
`body/app/src-tauri` is unproven until it has been built on Windows once. The gates catch format
and type errors; they cannot catch a link error.

**Do, once per such change** (this was the only item in this directory carrying no command,
added 2026-07-19, and it is the one repeated most often):

```powershell
cd body/app
npm run tauri build
```

The shell declares `os-windows` under `[target.'cfg(windows)'.dependencies]`, so a Windows build
of the shell is what links both ungated trees at once. The `npm run tauri dev` that every check
above starts with links them too, so a sitting that ran those has already covered whatever change
it was carrying; the build command is the form to use when there is no sitting to attach it to.

**Pass.** It links and the app starts.

**Fail.** A link error, which is exactly the third of the risk the gates cannot reach. Record it
where the change was made, not here.

## Notes

- The host index's recommended order lists neither this item nor the unbalanced COM initialization
  watch, and its roll call carries the two of them under a heading of their own rather than with
  the numbered checks. [ADR-0011](../../adr/ADR-0011-body-v1.md)'s 2026-07-19 mapping of its own user
  list points at this item as "the standing item at the end of the same doc".
- "Every check above" in the body means the numbered checks of the Windows desktop sitting, all of
  which start from the same `npm run tauri dev` bring-up.
