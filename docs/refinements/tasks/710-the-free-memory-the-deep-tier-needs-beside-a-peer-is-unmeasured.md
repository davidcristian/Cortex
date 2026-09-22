# The free memory the deep tier needs beside a peer is unmeasured

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md)
**Verified:** 2026-09-22

The [model-swap](../../runbooks/model-swap.md) runbook sets `CORTEX_SWAP_BRAIN_VRAM_MIB` on the
24 GB card at 20125 MiB: the plain deep tier's 19125 MiB plus a gigabyte for the desktop's share of
the card. Only two readings bound the figure. Beside the E4B subagent tier the deep tier spilled
with 19541 and 19549 MiB of `memory.free` before the load, decoding at 0.36 and 0.62 of its solo
rate, and alone it fits with about 22875 MiB free. So the gigabyte is slack rather than a measured
margin, which ADR-0055 decision 2 calls one more unchecked number. The spill itself is not
explained: beside the peer the deep tier added 186 and 195 MiB less to the card than alone,
although `memory.free` was over 400 MiB above its cost, while stacked E4B tiers used the card down
to 277 MiB free. The readings are in [co-residency](../../readings/co-residency.md).

**What would close it.** Load the plain deep tier beside fillers of known size, a small model at
chosen context sizes, that leave `memory.free` between 19549 and 22875 MiB before the load; read
decode against a solo start at matched clocks, and `nvidia-smi` every second through the load to
see what the deep tier holds above its at-ready size. Then set the runbook's figure at the lowest
free reading that decodes at the solo rate, plus the idle floor's movement. A peer small enough to
fit beside the deep tier would restore co-residency on this card, and that is a model pick for the
maintainer, not this task.

## History

- 2026-09-22: opened by the finding that the E4B tier did not grow between the August and
  September builds (3286 and 3293 MiB, the same buffers on both) and that the pair read as a fit
  in August already filled the card, which the runbook now answers by leaving co-residency off on
  a 24 GB card.
