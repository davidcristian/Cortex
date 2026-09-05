# The harness takes the tier's reasoning flags and not its placement

**Status:** landed 2026-09-05
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

Opened 2026-09-04 by the close of
[R-525](525-the-injection-harness-sends-a-request-key-and-never-the-tiers-argv.md), which gave the
injection harness a way to be handed a tier's argv and handed it one tail rather than a whole
command line.

`server_argv` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
still writes the head of every row's command line itself: `-ngl 99 --ctx-size 8192 --parallel 1`,
whatever tier the row's model belongs to. The shipped subagent servers do not run that way. The CPU
ones `docker-compose.subagents.yml` and `docker-compose.subagents-roster.yml` start run `-ngl 0`
and `--parallel 2`, and the model host's own GPU-placed subagent tier runs `--parallel 2` as well
(`DEFAULT_SUBAGENT_PARALLEL`). Only the context size agrees, and it agrees by coincidence rather
than by being read.

So the switch rows closed the half of "the tier's argv" that decides what the model is told about
thinking, and left the half that decides where it runs and how its KV cache is split. Two of those
three flags are the same number for the harness and for a tier today, which is exactly the shape
that drifts unreported: nothing compares them.

**Why it was left.** The close's own reading is that resistance did not move with the thinking
lever, and placement is a weaker candidate still: the same weights produce the same logits on the
card and on the host, modulo the numerics of a different kernel. Running the whole lineup at
`-ngl 0` would also cost hours of wall clock per sitting where the GPU rows cost about a minute,
which is why every published row is a GPU row in the first place.

**What would close it.** Two steps, and the first is cheap. Take the context size and the slot
count off `ModelHostConfig` the way `shipped_reasoning_off` takes the pair, so a retuned tier moves
the harness's head and the coincidence becomes a reading. Then decide whether `-ngl` is a row or a
constant: a placement row would say whether the numbers this ADR publishes for the subagent tier
are properties of the pick or of the card it was measured on, and the honest scope for that is one
model at one placement rather than the lineup.

## Trail

- 2026-09-04: opened by the close of
  [R-525](525-the-injection-harness-sends-a-request-key-and-never-the-tiers-argv.md), which read
  the tier's reasoning-off pair off the sidecar and left the three flags before it typed here.
- 2026-09-05: **landed**. Re-derived: the head was typed and uncompared, as the entry says, and
  two things it did not say. The head was one head for three tiers, so every cortex row ran at
  8192 against the cortex tier's 16384; and the text arm had drawn no cortex row since 2026-09-04,
  `switch_for` returning `THINKING_ON` under both switches and the test skipping whenever the
  switch returned was not the one asked for (`-k "12B and shipped-argv"` reported `1 skipped`).
  `server_argv` now hands the row's tier, read off `ModelHostConfig` by `tier_args`, to the
  sidecar's `llama_server_argv` with the artifact, port, layer count and tail substituted; a
  `Model` names its tier and `thinking` is read off it. `-ngl` is a row for the one tier the stack
  places twice: `PLACEMENTS` builds on the core's `PlacementTarget`, and the CPU row runs the CPU
  image with no device, the core's layer count for that server and the override's CPU quota off
  `DEFAULT_CPU_BUDGET`, for the shipped switch alone. Eight mutations each fail
  `test_switch_rows.py` (14 tests). Measured on the pick: 0 of 10 framed on the card under the
  tier's own head, cell for cell the 2026-09-04 rows, and 0 of 10 on the CPU in two sittings (1837 s under
  the quota, 819 s without); the cortex row, first drawn since 2026-09-04, is 0 of 10. The ADR-0004 placement-row
  addendum carries the table. Opened
  [R-555](555-the-other-four-subagent-candidates-have-no-cpu-row.md),
  [R-556](556-no-pixel-row-has-been-replicated-at-the-tiers-own-window.md),
  [R-557](557-the-engine-image-names-are-typed-in-five-places.md),
  [R-558](558-thinking-follows-the-tiers-name-and-not-its-shipped-budget.md) and
  [R-559](559-the-cpu-row-carries-the-cpu-quota-and-not-the-memory-cap.md).
