# The body's bind port can be declared now the shell compiles

**Status:** open, actionable
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
