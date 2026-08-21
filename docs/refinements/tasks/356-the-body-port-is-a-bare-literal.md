# The body's own listen port is a bare literal, so nothing ties the endpoint that dials it

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

Opened 2026-08-21 by the close of [R-333](333-compose-defaults-that-restate-a-declaration.md). The
brain's own seam port is the worked example of a coupling done right: `DEFAULT_SEAM_PORT` is
declared once in `brain/packages/orchestrator/src/cortex_orchestrator/config.py`, and
`scripts/crosscheck.py` holds the compose publish, the compose healthcheck and the two Tauri
modules that dial it to that one number. **The body's port has none of that.**

`body/app/src-tauri/src/body_server.rs` binds `SocketAddr::from((Ipv4Addr::LOCALHOST, 50151))` as a
bare literal inside a fallback expression, so no tree declares the value.
`docker/docker-compose.body.yml` restates it as `${CORTEX_BODY_ENDPOINT:-host.docker.internal:50151}`,
three runbooks quote the same port to an operator (`body-volume.md`, `local-dev-wsl.md`,
`scheduling.md`), and the brain's live gateway test falls back to `127.0.0.1:50151`. Six files
spell one number and nothing compares them. The survey filed it under "nothing declares this" rather than
"untied coupling", which is accurate today and is the thing to change.

**What would close it.** Promote the literal to an item-level constant in that module (the scan
reads Rust `const`/`static` at item level and already registers two mentions in the same crate for
the brain's port), then register it with the compose default and one runbook sentence. The one
question worth recording is where the constant belongs: the Tauri shell is outside `just check`
(only CI's `check-shell` compiles it), so a constant there is fmt-checked and clippy-checked
elsewhere while the cross-tree scan reads it unconditionally, which is a split the seam-port entry
already lives with in the other direction.

## Trail

- 2026-08-21: opened by the close of
  [R-333](333-compose-defaults-that-restate-a-declaration.md), which found the endpoint default
  among the thirteen compose defaults nothing declares and noticed that this one is a missing
  declaration rather than a value with no other side.
