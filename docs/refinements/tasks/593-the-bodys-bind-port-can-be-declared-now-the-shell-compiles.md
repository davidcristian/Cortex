# The body's bind port can be declared now the shell compiles

**Status:** satisfied 2026-09-07
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

Filed on 2026-09-06 out of [R-013](013-couplings-widened-registry-cannot-hold.md), which said the
body's bind port 50151 is a bare literal argument in `body/app/src-tauri/src/body_server.rs`,
against `host.docker.internal:50151` in
[docker-compose.body.yml](../../../docker/docker-compose.body.yml), with no declaration anywhere for
the registry to compare. The only file that could hold one was inside the Tauri shell, which at the
time no check compiled. The shell entered CI on 2026-08-17 ([R-009](009-shell-clippy-in-ci.md)), so
that reason had gone.

## History

- 2026-09-06: filed out of the bind-port part of
  [R-013](013-couplings-widened-registry-cannot-hold.md), whose shell clause had fired.
- 2026-09-07: satisfied, and the premise was already false on the day this entry was filed.
  `body_server.rs` has declared `DEFAULT_BODY_PORT` since 2026-08-22
  ([R-356](356-the-body-port-is-a-bare-literal.md)), `cfg(windows)` beside `DEFAULT_TOAST_APP_ID`,
  and the bind uses it in the `unwrap_or_else` this entry reads as a bare literal. The comparison is
  registered too, and has been widened once since:
  [scripts/endpointcouplings.py](../../../scripts/endpointcouplings.py) has an entry called "the
  body's own listen port" that compares the declaration with 23 far sides, among them the compose
  line this entry names, still written `${CORTEX_BODY_ENDPOINT:-host.docker.internal:50151}` on line
  27 of the body override. [R-383](383-the-body-port-past-the-six-that-were-registered.md) took it
  from six far sides to twenty three on 2026-08-23. The instruction to register it in the boundary
  half of the registry is stale too, since both endpoint entries live in `endpointcouplings.py` now.
- 2026-09-07: proved rather than read, over `just check-crosscheck` on the committed tree.
  `DEFAULT_BODY_PORT` moved to 50251 with every far side unchanged exits 1 with 23 failures, one per
  far side. The compose endpoint default moved to `host.docker.internal:50251` with the constant
  unchanged exits 1 with one failure, naming that line and reporting that the file still contains
  50151 three times under another meaning. The unchanged tree exits 0 over 89 constants, 105
  declarations and 291 mentions.
- 2026-09-07: how the entry came to be filed. It was written out of R-013's bind-port part, whose
  prose still said the port was a bare literal, and that had been wrong for fifteen days: neither
  R-356 nor R-383 named R-013, so registering the comparison in one file left it listed as
  unregistered in another. The 2026-09-06 review answered the trigger clause, which had genuinely
  fired, and took the claim beside it from the sibling document rather than from `body_server.rs`.
  The other five answers in that review were each checked against the tree, the model mount or the
  account's run history.
- 2026-09-07: one claim survives its own close and is filed as work. The reason given for the port
  being declarable, that a constant in `body_server.rs` is now type-checked on every change touching
  the shell, does not hold for this constant or any other item behind `cfg(windows)` there.
  `just check-shell` and the CI `shell` job both run clippy for the host triple, which is Linux in
  each case, and `DEFAULT_BODY_PORT` is `cfg(windows)`, so the compiler leaves it out. Filed as
  [R-595](595-no-check-compiles-the-tauri-shells-windows-half.md).
