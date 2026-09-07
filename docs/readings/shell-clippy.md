# Readings: what linting the Tauri shell costs

What a runner pays to clippy `body/app/src-tauri` for the host and for `x86_64-pc-windows-msvc`.
Cited by [ADR-0011](../adr/ADR-0011-body-v1.md), decisions 10 and 11.

## The host run

**2026-08-17.** The `-dev` closure the host clippy needs, resolved from five roots
(`libwebkit2gtk-4.1-dev`, `libgtk-3-dev`, `libayatana-appindicator3-dev`, `librsvg2-dev`,
`libdbus-1-dev`) with `--no-install-recommends`: **103 packages, 39.6 MB fetched**. An earlier
630-package figure was a recursive `apt-cache depends` walk without `--no-recommends` or
`--no-suggests`, which counts alternatives and runtime closures a real install does not. `cargo
clippy --locked --all-targets -- -D warnings` over the whole Tauri graph, from an empty target
directory against those five roots, finished in about half a minute on the development machine, of
the same order as the package fetch. None of the libraries is loaded, since clippy does not link;
they exist to get the `-sys` build scripts past a `pkg-config` probe.

On a host without sudo the same prefix is built by `apt-get download` of the closure, `dpkg-deb -x`
into a directory outside the repo, and `PKG_CONFIG_PATH` naming its two `pkgconfig` directories.

## The Windows-target run

**2026-09-07.** `cargo clippy --locked --target x86_64-pc-windows-msvc --all-targets -- -D warnings`
type-checks the Tauri Windows graph (`webview2-com-sys`, `tao`, the `windows` crates, `os_windows`,
`body-core`) from an empty target directory, with the registry already fetched, in about five
sixths of the host run's time. It needs none of the five Linux roots, only a resource compiler.

| Resource compiler | Fetched | Installed | Also needs |
| --- | --- | --- | --- |
| GNU windres, `binutils-mingw-w64-x86-64` | 6.1 MB | 52 MB | nothing |
| `llvm-rc`, from `llvm-18` over `libllvm18` | 25 MB | 117 MB | a `cl.exe` stand-in for the `cc` preprocessing step |

No rustup component ships `llvm-rc`: `llvm-tools` installs `llvm-ar`, `llvm-cov`, `llvm-objcopy`
and others, not it.

Method: `just check-shell`, run from an empty `target/`; package sizes from `apt-get` on the
development machine's Ubuntu release.
