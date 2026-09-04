# The harness takes the tier's reasoning flags and not its placement

**Status:** open, actionable
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
