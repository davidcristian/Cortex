# The body's listen port is a bare literal, so nothing compares it with the endpoint that calls it

**Status:** done 2026-08-22
**Area:** repo-checks
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

The brain's own port is the worked example done right: `DEFAULT_RPC_PORT` is declared once in
`brain/packages/orchestrator/src/cortex_orchestrator/config.py`, and `scripts/crosscheck.py`
compares the compose publish, the compose healthcheck and the two Tauri modules that call it
against that one number. The body's port had none of that.

`body/app/src-tauri/src/body_server.rs` binds `SocketAddr::from((Ipv4Addr::LOCALHOST, 50151))` as a
bare literal inside a fallback expression, so no tree declares the value.
`docker/docker-compose.body.yml` restates it as
`${CORTEX_BODY_ENDPOINT:-host.docker.internal:50151}`, three runbooks quote the same port to an
operator (`body-volume.md`, `local-dev-wsl.md`, `scheduling.md`), and the brain's live gateway test
falls back to `127.0.0.1:50151`. Six files write one number and nothing compares them.

The fix is to make the literal an item-level constant in that module (the scan reads Rust `const`
and `static` at item level), then register it with the compose default and one runbook sentence.
The question worth recording is where the constant belongs: the Tauri shell is outside `just
check`, only CI's `check-shell` compiling it, so a constant there is format-checked and
clippy-checked elsewhere while the cross-tree scan reads it unconditionally.

## History

- 2026-08-21: Opened by the close of [R-333](333-compose-defaults-that-restate-a-declaration.md),
  which found the endpoint default among the thirteen compose defaults nothing declares and
  recorded that this one is a missing declaration rather than a value with no other side.
- 2026-08-22: Done. `DEFAULT_BODY_PORT` is declared in `body/app/src-tauri/src/body_server.rs`,
  `cfg(windows)` beside `DEFAULT_TOAST_APP_ID`, and one entry in `scripts/wirecouplings.py`
  compares it against five places: the body override's endpoint default, three runbook sentences,
  and the brain's live gateway fallback. The placement question is answered in the shell's favour:
  moving it into `body_core` or `body_rpc` would buy a compiler's opinion of a `u16` while putting
  a host process's deployment default in a crate that never binds, and no compiler can compare a
  YAML string with a runbook cell anyway, while the scan can and fails closed, so a rename here
  fails `just check` before the CI job that compiles the crate runs. One claim did not hold: "six
  files write one number" is the six the entry lists, not the eighteen that write it. The other
  twelve are sorted in the ADR and left to
  [R-383](383-the-body-port-past-the-six-that-were-registered.md), three of them not other sides at
  all. Six planted differences, one per registered place, each exiting 1 and restored by digest;
  the one in the Rust constant produced five faults, which is the scan reading a declaration in the
  shell that `just check` does not compile. `just check-shell` ran green here over the sudo-less
  pkg-config prefix, though that is a Linux clippy and the constant is `cfg(windows)`, so the item
  was compiled out and was checked in isolation instead. The placement is ADR-0023 decision 12.
