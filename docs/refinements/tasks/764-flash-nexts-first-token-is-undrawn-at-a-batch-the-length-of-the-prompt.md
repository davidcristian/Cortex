# Flash-Next's first token is undrawn at a batch the length of the prompt

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-10-01

At the shipped 24g cap Qwen3.8-Flash-Next loads within the swap bound and decodes a fresh
2000-token reply above the 7.5 tok/s floor, but its first delta for the 3400-word prompt came at
198.0 s against the 120 s stall bound ([Qwen3.8-Flash-Next](../../readings/flash-next.md)). The
engine evaluated the prompt in steps of at most 2048 tokens. A first step of 54 tokens took 58.3 s,
the first full step 88.1 s while it read about 20.5 GB of experts from the mount, and the later
steps 12 to 23 s each, because the cap kept most of what a step reads. So the first token waits on
reading the off-card experts once, and the cgroup dropped file pages between the first two steps.

`--batch-size` and `--ubatch-size` set to the deployed context, 8192, would evaluate the prompt in
one step. The cost is a larger compute buffer on the card, which may push expert layers off it
(`--n-cpu-moe` above 35) and slow the decode, which cleared its floor at 8.59 tok/s.

What would close it, with the command, price, rule and prediction written here before each draw:

1. One load at that batch shape under the same cap and `scripts/memwatch.py`, with VRAM read at
   ready, then the first delta of the 3400-word prompt against the 120 s bound. The run D driver,
   `measurements/flash-decode-2026-10-01/decode.py`, and run C's,
   `measurements/flash24-2026-09-28/flash24.py`, are the shapes to copy.
2. If that clears, run D's decode draw repeated at the new placement.

If both floors clear, the switch column, the stop row (its four questions are in
[deep candidates](../../readings/deep-candidates.md)) and the injection row are priced from the
measured decode rate and written here before they are drawn. Counting progress chunks against the
stall bound is a second route that leaves the engine alone
([763](763-the-stall-bound-times-a-whole-prompt-evaluation-as-one-silence.md)). Beyond this
machine, a host with memory for the paged experts, or the files on a local disk, which
[ADR-0004](../../adr/ADR-0004-model-lineup.md) decision 3 keeps on the mount, would change the
result; neither can be drawn here without the maintainer's decision.

## History

- 2026-10-01: filed by
  [735](735-flash-nexts-feasibility-row-is-not-complete-at-the-shipped-memory-cap.md), whose rows
  at the shipped cap left the first token as the one floor that fails.
