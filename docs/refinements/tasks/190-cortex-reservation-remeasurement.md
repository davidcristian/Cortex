# The cortex reservation re-measurement

**Status:** landed 2026-08-07
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

It had never been an entry here. Where it lived was two ADRs and no index:
[ADR-0004](../../adr/ADR-0004-model-lineup.md)'s
swap-latency note 8, which saw the cortex read about 9.7 GB against its own 11.0 and asked a later
sitting to confirm which figure the deployment pays, and
[ADR-0030](../../adr/ADR-0030-brain-handoff.md)'s co-residency addendum, which measured 8448 to 8468
MiB and deliberately left `CORTEX_VRAM_CORTEX_GB=11.3` alone because lowering it widens what the
placer admits and that is this area's decision rather than the handoff's. Both were right to
defer and neither wrote a line anywhere that counts open work, so an item that bounded every
spawn's fit-test sat outside every count for three days. That is the doc-first rule's own failure
mode, recorded here plainly rather than quietly fixed.
**What the re-measurement found.** The published 8448 to 8468 was an idle figure and a reservation
has to cover a peak, which is why this was never a one-line edit. At the shipped tier shape, read
out of the running child's argv (`-ngl 99 --ctx-size 16384 --parallel 1 --jinja` with the projector
and `--image-max-tokens 1024`), the tier is **8400 to 8484 MiB idle and 8573 MiB at its peak**
above a floor read with the tier stopped at both ends of the session (1261 to 1301, then 1259 to
1308 MiB, agreeing within 7 MiB, so nothing of the desktop's own drift is folded in). A 13180-token
prompt with 924 tokens decoded allocated **nothing**, llama.cpp taking the 16K KV and the compute
buffers at load; the only thing that arrives with the work is the vision path's 70 to 90 MiB on the
first image, and it stays. And most of the apparent 2.8 GB gap was a unit: the 11.3 was
`nvidia-smi` total used with the desktop's floor inside it, while every other term in this budget
is a tier's own cost. **The reservation is 8.6 GiB**, 233 MiB over the measured peak, which covers
the sampler's in-phase spread, the floor bracket and one more vision-sized allocation. The
headroom goes from 2.7 to 5.4 GiB, so a spawn declared at the GPU tier's measured 3319 MiB is
GPU-placed where nothing ever was ([ADR-0012](../../adr/ADR-0012-resource-governance.md)
re-measured-reservation addendum, procedure in
[runbooks/llamacpp-gpu.md](../../runbooks/llamacpp-gpu.md)). One entry opens in its place, below,
and it is the term the re-measurement deliberately did not touch.

## Trail

- 2026-08-07: Landed as a re-measurement of `CORTEX_VRAM_CORTEX_GB`, the term the placer subtracts
  from the soft cap on every spawn's fit-test, recorded at the ADR-0012 re-measured-reservation
  addendum with the procedure in [runbooks/llamacpp-gpu.md](../../runbooks/llamacpp-gpu.md). It had
  been deferred at two ADRs and recorded on no index at all, so for three days a number bounding
  every admission sat outside every count, which is the doc-first rule's own failure mode.
- 2026-08-07: Read its own way the old reservation was about 1.7 GiB high, and read the budget's way
  about 2.6 GiB high, most of the apparent gap being a unit rather than a build. The default is
  8.6 GiB, 233 MiB over the measured peak, and the headroom goes from 2.7 to 5.4 GiB. It arrived
  with no matching departure, having closed nothing this area's count had ever carried, and one
  entry opened in its place, the term the sitting refused to bend.
