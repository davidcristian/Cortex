# The brain's seam port is tied to four places in code and to none of the nine documents stating it

**Status:** open, actionable
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
