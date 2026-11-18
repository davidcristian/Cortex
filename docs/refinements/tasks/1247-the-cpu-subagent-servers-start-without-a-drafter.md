# The CPU subagent servers start without a drafter

**Status:** open, waiting for its trigger
**Area:** subagents
**Origin:** [ADR-0077](../../adr/ADR-0077-model-card-settings.md)
**Trigger:** the row of task 1242 that compares two busy CPU servers with two busy slots reads each server at or above each slot, so a drafter for every CPU subagent is what would decide between the two shapes.
**Verified:** 2026-11-18

The drafter settings of decision 7 of the origin ADR reach the model host's tiers: the cortex,
the deep tier and the GPU subagent servers. The CPU subagent servers are compose services,
`llama-subagent` in `docker/docker-compose.subagents.yml` and `llama-subagent-qwen` in
`docker/docker-compose.subagents-roster.yml`, whose commands name no `--model-draft`.

What is measured, in the model baseline of 2026-11-16
(`measurements/model-baseline-2026-11-16/baseline.md`, the CPU image, 4 CPUs, an 8 GiB cap, an 8K
context): gemma-4-E4B wrote at 1.09 times the no-draft rate at a draft length of 3, for about
0.1 GiB more memory. Qwen3.5-2B and Qwen3.5-0.8B wrote slower with drafting. So the gain on the
CPU pick is small, and the roster alternate has none.

What would close it, if the trigger fires:

- A row on the CPU server's own flags, two slots and `--threads 4`, with the drafter and without,
  since the baseline row was drawn on one slot.
- A way to turn the drafter off. A compose command cannot leave a flag out when a variable is
  empty, and `${VAR:-default}` cannot be turned off by an empty value, so this needs an entry
  script or a second compose file.
- `--model-draft` in `ARTIFACT_FLAGS` of `scripts/artifactnames.py`, so the drafter's variable is
  read as an artifact
  ([R-520](520-the-compose-artifact-flag-set-names-two-of-the-engines-file-flags.md)).

## History

- 2026-11-18: filed when the model host's tiers got their drafter settings
  ([R-1239](1239-no-tier-but-the-deep-one-can-name-a-drafter.md)), which left the CPU servers
  out.
