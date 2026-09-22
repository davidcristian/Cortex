# The harness takes the tier's reasoning flags and not its placement

**Status:** done 2026-09-05
**Area:** inference
**Origin:** [ADR-0060](../../adr/ADR-0060-injection-rows-follow-the-tier.md)

`server_argv` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
wrote the head of every row's command line itself, `-ngl 99 --ctx-size 8192 --parallel 1`, whatever
tier the row's model belongs to. The shipped subagent servers do not run that way: the CPU servers
started by `docker-compose.subagents.yml` and `docker-compose.subagents-roster.yml` run `-ngl 0` and
`--parallel 2`, and the model host's own GPU subagent tier runs `--parallel 2` as well
(`DEFAULT_SUBAGENT_PARALLEL`). Only the context size agrees, and it agrees by coincidence rather
than by being read.

So the switch rows covered the half of the tier's command line that decides what the model is told
about thinking and left the half that decides where it runs and how its KV cache is split. Two of
those three flags happen to be the same number for the harness and for a tier today, and nothing
compares them.

Closing it takes two steps. Read the context size and the slot count off `ModelHostConfig` the way
`shipped_reasoning_off` reads the reasoning pair, so a retuned tier moves the harness's head. Then
decide whether `-ngl` is a row or a constant: a placement row would say whether the numbers this ADR
publishes for the subagent tier are properties of the pick or of the card it was measured on.

## History

- 2026-09-04: opened by the close of
  [R-525](525-the-injection-harness-sends-a-request-key-and-never-the-tiers-argv.md), which read the
  tier's reasoning-off pair off the sidecar and left the three flags before it typed by hand.
- 2026-09-05: done. The head was typed and uncompared, as the entry says, and two things it did not
  say. The head was one head for three tiers, so every cortex row ran at 8192 against the cortex
  tier's 16384; and the text rows had drawn no cortex row since 2026-09-04, `switch_for` returning
  `THINKING_ON` under both switches and the test skipping whenever the switch returned was not the
  one asked for (`-k "12B and shipped-argv"` reported `1 skipped`). `server_argv` now hands the
  row's tier, read off `ModelHostConfig` by `tier_args`, to the sidecar's `llama_server_argv` with
  the artifact, port, layer count and tail substituted; a `Model` names its tier and `thinking` is
  read off it. `-ngl` is a row for the one tier the stack places twice: `PLACEMENTS` builds on the
  core's `PlacementTarget`, and the CPU row runs the CPU image with no device, the core's layer
  count for that server and the override's CPU quota off `DEFAULT_CPU_BUDGET`, for the shipped
  switch alone. Eight mutations each fail `test_switch_rows.py` (14 tests). Measured on the pick: 0
  of 10 framed on the card under the tier's own head, cell for cell the 2026-09-04 rows, and 0 of 10
  on the CPU in two sessions (1837 s under the quota, 819 s without); the cortex row, first drawn
  since 2026-09-04, is 0 of 10. The 2026-09-05 placement session has the table. Opened
  [R-555](555-the-other-four-subagent-candidates-have-no-cpu-row.md),
  [R-556](556-no-pixel-row-has-been-replicated-at-the-tiers-own-window.md),
  [R-557](557-the-engine-image-names-are-typed-in-five-places.md),
  [R-558](558-thinking-follows-the-tiers-name-and-not-its-shipped-budget.md) and
  [R-559](559-the-cpu-row-applies-the-cpu-quota-and-not-the-memory-cap.md).
