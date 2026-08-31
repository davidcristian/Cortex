# The brain's seam port is tied to four places in code and to none of the nine documents stating it

**Status:** landed 2026-08-23
**Area:** repo-gates
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

Opened 2026-08-23 by the close of
[R-383](383-the-body-port-past-the-six-that-were-registered.md), which sorted the body's bind port
out of prose and left the port it was modelled on the looser of the two.

`DEFAULT_SEAM_PORT` is declared in `brain/packages/orchestrator/src/cortex_orchestrator/config.py`
and held to four places, all of them code: the base compose publish, the healthcheck dial inside
it, and the two Tauri modules that spend it. That registration has been cited as the worked example
of a coupling done right since the compose survey. It holds no prose at all.

**Where it is still loose.** Nine documents state the port and none is tied.
[host/index.md](../../host/index.md) carries it in the same prerequisites list whose body half is
now held, as "a reachable brain at `CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:50051`)". Four
module contracts restate it: [modules/body-rpc.md](../../modules/body-rpc.md) three times, in the
dial example and in the sentence pairing `CORTEX_BRAIN_ADDR` with the server's own
`CORTEX_SEAM_HOST`/`CORTEX_SEAM_PORT` defaults; [modules/body-app.md](../../modules/body-app.md) in
the shell's config list, one line above the body port that is now held;
[modules/brain-orchestrator.md](../../modules/brain-orchestrator.md) twice, on the field and on the
address the body dials. [runbooks/body-overlay.md](../../runbooks/body-overlay.md) writes it in the
prerequisites and again in a PowerShell export a reader copies, and
[runbooks/local-dev-wsl.md](../../runbooks/local-dev-wsl.md) writes it in two table rows and in two
copyable one-liners.

**What would close it.** The four shapes the body port's sort settled reach almost all of it
already: a stated default, an export a reader copies, an endpoint another process dials, and a
declaring file's own prose. Read the nine, sort by the tense test, and register the ones that
state. Two of them want a decision rather than a row. The WSL runbook's log excerpt
(`port=50051` in a captured line of server output) is a paste of what a run printed, which is
history by the same rule that keeps a measured arm out. And `body-rpc.md` names the port beside
`CORTEX_SEAM_HOST`, so whether the host and the port are one coupling or two is worth a sentence
before either becomes a row.

## Trail

- 2026-08-23: opened by the close of
  [R-383](383-the-body-port-past-the-six-that-were-registered.md), which found the brain's port
  held in four places of code and in no prose while sorting the body's port out of thirteen files.
- 2026-08-23: landed as nineteen more mentions on the existing entry, taking it from four far sides
  to twenty three over twenty six spellings in eighteen files. **The entry was wrong about the kind
  of gap this was.** It counts nine documents and names six; it counts four module contracts and
  names three; and its title says the port is loose in prose, when eight of the loose spellings are
  code the entry never reaches: `brain/Dockerfile`'s `EXPOSE`, `body/crates/rpc/src/client.rs`'s
  dial example, `body/crates/rpc/tests/live.rs` twice, `body_server.rs`'s doc comment,
  `docker/docker-compose.body.yml`'s comment, and the two `integration`-marked live seam suites in
  the brain. Counted off the tree the port is spelled 32 times in 19 files outside the decision
  records, the backlog and this gate's own suite. **The judgement this settles is when a suite
  holds itself**: `test_config.py` asserts this default three times and is deliberately out,
  because it runs on every commit and a retune that left it behind fails in the suite that owns the
  constant, while the two live suites are in because `integration` keeps them out of CI and their
  drift surfaces weeks later as a server that is not answering. That is a fact about the file
  rather than a reading of the test, and it is the same distinction `capture_bytes.rs` falls on.
  The WSL runbook's `port=50051` stays out as a paste of captured output. Twenty three planted
  drifts each exited 1 and each restoration returned the gate to green, with three controls staying
  green; tabled in the ADR-0023 seam-port-prose addendum. Two residues filed: the loopback address
  that appears inside a dozen of these needles as fixed text
  ([R-396](396-the-seam-host-rides-inside-the-ports-needles.md)), and the fact that three sorts in
  a row have corrected their own count upward by hand because nothing reads what the registry does
  not name ([R-397](397-nothing-counts-what-the-registry-does-not-name.md)).
