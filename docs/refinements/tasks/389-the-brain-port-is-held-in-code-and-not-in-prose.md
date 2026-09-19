# The brain's port is registered in four places of code and in none of the documents stating it

**Status:** done 2026-08-23
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

`DEFAULT_SEAM_PORT` is declared in `brain/packages/orchestrator/src/cortex_orchestrator/config.py`
and tied to four places, all of them code: the base compose publish, the healthcheck dial inside
it, and the two Tauri modules that use it. No prose is covered.

Nine documents state the port and none is tied. [host/index.md](../../host/index.md) has it in the
prerequisites list whose body half is now covered, as "a reachable brain at `CORTEX_BRAIN_ADDR`
(default `http://127.0.0.1:50051`)". [modules/body-rpc.md](../../modules/body-rpc.md) restates it
three times, [modules/body-app.md](../../modules/body-app.md) once in the shell's config list, and
[modules/brain-orchestrator.md](../../modules/brain-orchestrator.md) twice.
[runbooks/body-overlay.md](../../runbooks/body-overlay.md) writes it in the prerequisites and in a
PowerShell export a reader copies, and [runbooks/local-dev-wsl.md](../../runbooks/local-dev-wsl.md)
in two table rows and two copyable one-liners.

The four shapes settled by the body port's sorting reach almost all of it: a stated default, an
export a reader copies, an endpoint another process dials, and a declaring file's own prose. Two
places want a decision rather than a row. The WSL runbook's log excerpt (`port=50051` in captured
server output) is a paste of what a run printed, which is a record of the past. And `body-rpc.md`
names the port beside `CORTEX_SEAM_HOST`, so whether the host and the port are one coupling or two
is worth a sentence first.

## History

- 2026-08-23: opened by the close of
  [R-383](383-the-body-port-past-the-six-that-were-registered.md), which found the brain's port
  tied to four places of code and to no prose while sorting the body's port out of thirteen files.
- 2026-08-23: closed as nineteen more matches on the existing entry, taking it from four
  registered places to twenty three over twenty six occurrences in eighteen files. The entry was
  wrong about the kind of gap this was. It counts nine documents and names six; it counts four
  module contracts and names three; and its title says the port is loose in prose, when eight of
  the loose occurrences are code the entry never reaches: `brain/Dockerfile`'s `EXPOSE`,
  `body/crates/rpc/src/client.rs`'s dial example, `body/crates/rpc/tests/live.rs` twice,
  `body_server.rs`'s doc comment, `docker/docker-compose.body.yml`'s comment, and the two
  `integration`-marked live suites in the brain. Counted off the tree, the port appears 32 times in
  19 files outside the decision records, the backlog and this check's own suite. The judgement this
  settles is when a suite covers itself: `test_config.py` checks this default three times and is
  deliberately out, because it runs on every commit and a retune that left it behind fails in the
  suite that owns the constant, while the two live suites are in because `integration` keeps them
  out of CI and a mismatch there appears weeks later as a server that does not respond. That is a
  fact about the file rather than a reading of the test, and it is the same distinction
  `capture_bytes.rs` falls on. The WSL runbook's `port=50051` stays out as a paste of captured
  output. Twenty three planted changes each exited 1 and each restoration returned the check to
  passing, with three controls staying green; the suite rule is ADR-0042 decision 12. Two residues
  filed: the loopback address that appears inside a dozen of these search texts as fixed text
  ([R-396](396-the-seam-host-rides-inside-the-ports-needles.md)), and the fact that three sortings
  in a row have corrected their own count upward by hand because nothing counts what the registry
  does not name ([R-397](397-nothing-counts-what-the-registry-does-not-name.md)).
