# The body's bind port can be declared now the shell compiles

**Status:** satisfied 2026-09-07
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Filed 2026-09-06 out of [R-013](013-couplings-widened-registry-cannot-hold.md), whose bind-port
sub-entry was blocked on a fact about the tree that stopped being true.

**What was blocking it.** The body's bind port 50151 is a bare literal argument in
`body/app/src-tauri/src/body_server.rs`, against `host.docker.internal:50151` in
[docker-compose.body.yml](../../../docker/docker-compose.body.yml). The registry holds a coupling
by reading a declaration on one side and a mention on the other, and this port has no declaration
anywhere. The only file that could carry one was inside the Tauri shell, which at the time no gate
compiled, so landing a constant there meant shipping a source edit nothing type-checks. That was
judged a worse trade than leaving one port untied.

**Why it is actionable now.** The shell entered CI on 2026-08-17
([R-009](009-shell-clippy-in-ci.md)). `.github/workflows/ci.yml` runs a `shell` job that installs
the Tauri Linux dev stack and calls `just check-shell`, and clippy there compiles the crate rather
than parsing it. A constant declared in `body_server.rs` is now type-checked on every change that
touches the shell, and the same host can run `just check-shell` by hand against an unpacked
`libdbus-1-dev` in a userspace prefix.

**What the work is.** Declare the port once in `body_server.rs`, spend it where the literal is
today, register the coupling in the seam half of the registry against the compose file's mention,
and prove the gate fails in both directions before trusting it: the constant moved with the compose
file standing, and the compose file moved with the constant standing. The mutation table names the
suite its counts are over.

**What to check first, because this entry may already be wrong about the tree.** Read
`body_server.rs` and the compose file at HEAD before writing anything. The port may have moved, the
argument may already be behind a settings field, and the compose mention may be spelled differently
from the form recorded above.

## Trail

- 2026-09-06: filed out of the bind-port sub-entry of
  [R-013](013-couplings-widened-registry-cannot-hold.md), which was struck there when the shell
  clause of its trigger was found to have fired.
- 2026-09-07: **satisfied, and the premise was already false on the day this entry was filed.**
  `body/app/src-tauri/src/body_server.rs` has declared `DEFAULT_BODY_PORT` since 2026-08-22
  ([R-356](356-the-body-port-is-a-bare-literal.md)), `cfg(windows)` beside `DEFAULT_TOAST_APP_ID`,
  and the bind spends it in the `unwrap_or_else` this entry reads as a bare literal. The coupling
  is registered as well, and has been widened once since:
  [scripts/endpointcouplings.py](../../../scripts/endpointcouplings.py) carries an entry called
  "the body's own listen port" that holds the declaration against 23 far sides, among them the
  compose mention this entry names, still spelled
  `${CORTEX_BODY_ENDPOINT:-host.docker.internal:50151}` on line 27 of the body override.
  [R-383](383-the-body-port-past-the-six-that-were-registered.md) took it from six far sides to
  twenty three on 2026-08-23. The instruction above to write the entry in the seam half of the
  registry is stale too: `seamcouplings.py` split later, and both endpoint entries live in
  `endpointcouplings.py` now.
- 2026-09-07: proved rather than read, over `just check-crosscheck` on the committed tree, whose
  fault lines name the entry and every far side. `DEFAULT_BODY_PORT` moved to 50251 with every far
  side standing exits 1 with 23 faults, one per far side. The compose endpoint default moved to
  `host.docker.internal:50251` with the constant standing exits 1 with one fault, naming that line
  and reporting that the file still spells 50151 three times under another meaning. The unchanged
  tree exits 0 over 89 constants, 105 declaring sites and 291 mentions.
- 2026-09-07: **how the entry came to be filed, since that is the part worth keeping.** It was
  written out of R-013's bind-port sub-entry, whose prose still said the port was a bare literal,
  and that sub-entry had been wrong for fifteen days: neither R-356 nor R-383 named R-013, so
  registering the coupling in one file left it listed as unregistered in another. The 2026-09-06
  sweep answered the trigger clause, which had genuinely fired, and took the claim beside it from
  the sibling document rather than from `body_server.rs`. The other five answers in that sweep were
  each re-derived against the tree, the model mount or the account's run history, so this was the
  only one of the six taken from a document, and there is no sweep-wide fault to file. R-013 now
  carries a struck paragraph under the sub-entry, in the convention its three other closed
  sub-entries already use.
- 2026-09-07: **one claim in this entry survives its own close and is filed as work.** The reason
  given above for the port being declarable, that a constant in `body_server.rs` is now
  type-checked on every change touching the shell, does not hold for this constant or for any other
  Windows-gated item there. `just check-shell` and the CI `shell` job both run clippy for the host
  triple, which is Linux in each case, and `DEFAULT_BODY_PORT` is `cfg(windows)`, so the compiler
  configures it out. Filed as
  [R-595](595-no-gate-compiles-the-tauri-shells-windows-half.md).
