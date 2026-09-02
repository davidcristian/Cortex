# One roster entry's two placement targets are named by two artifact variables nothing holds together

**Status:** open, fix when it bites
**Area:** subagents
**Trigger:** a deployment that names different files in `CORTEX_MODEL_FILE_SUBAGENT` and
`CORTEX_MODEL_FILE_SUBAGENT_GPU`, whether found by a GPU-placed and an overflowed spawn of the
default entry answering differently or by reading the two variables side by side; or the hosted
subagent tier gaining a second pick, at which point the pairing has to be written down anyway.
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)

Opened 2026-09-02 by the close of
[R-508](508-a-roster-entry-names-an-endpoint-and-not-a-model.md), which declined reading an entry's
artifact into the brain and found, in the wiring that makes an entry, the one expectation such a
read could be held to without a config knob.

`_entry_profile` in `cortex_orchestrator.subagent_builders` gives the default entry two backends, one
per `PlacementTarget`, over `CORTEX_SUBAGENTS_GPU_ENDPOINT` and `CORTEX_SUBAGENTS_ENDPOINT`. With the
hosted tier opted in, those are two different servers whose weights are named by two different
variables: `CORTEX_MODEL_FILE_SUBAGENT` in the `command:` of `docker/docker-compose.subagents.yml`
and `CORTEX_MODEL_FILE_SUBAGENT_GPU` in the model host's env. The second defaults to empty because
the tier is opt-in, so no compose default ties them, and `docs/runbooks/subagents-cpu.md` section
2c sets them equal by hand. `VramBudgetPlacer.place` then picks the target by headroom, which
[ADR-0012](../../adr/ADR-0012-resource-governance.md) designed as a decision about resources and
nothing else, and [ADR-0017](../../adr/ADR-0017-subagent-model-safety.md) pins every tainted spawn
to the default entry on the premise that the entry is the injection-robust pick. A deployment
naming two files breaks that premise on the GPU side only: which weights read untrusted content
depends on how much VRAM was free at the moment of the spawn.

**Why it was left.** Making the two variables disagree takes two deliberate acts, since the hosted
tier is off until a file is named for it and the runbook names the CPU server's own file when it
does; and the check has no natural home yet. The brain cannot read either variable, and the hosted
tier is not necessarily running when the brain boots (the daemon starts the cortex and nothing
else; the tier sweep starts it later, under escalation), so a boot-time comparison of the two
servers' `GET /props` would answer for one side only. The compose comment on the tier and the
runbook's section 2c now say the two must name one file, which is the whole of the repair today.

**What would close it.** One of two shapes. A brain-side read of `GET /props` on both of an entry's
targets, compared with each other and never with a declared expectation, taken when both are up:
at the tier sweep under escalation, or at the first GPU placement of a spawn, with a disagreement
logged as a warning naming both paths. Or a supervisor-side declaration: the model host's tier
could read the same variable the CPU server spends, `CORTEX_MODEL_FILE_SUBAGENT`, with the `_GPU`
name kept as an override, so that the shipped wiring names one artifact twice by construction and
only a deployment that writes the override can split it; that costs the tier's present opt-in
reading, under which an empty file means no tier. The second is cheaper and closes the default
case; the first is what catches the override case. Either way the answer is compared and never
stored, since a reading taken once goes stale under the redeployment the vision probe was moved to
catch.

## Trail

- 2026-09-02: opened by the close of
  [R-508](508-a-roster-entry-names-an-endpoint-and-not-a-model.md), whose decline found this to be
  the one expectation a `/props` read could be held to without a config knob.
