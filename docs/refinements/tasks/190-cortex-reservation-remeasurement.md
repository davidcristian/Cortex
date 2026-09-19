# Measuring the cortex reservation again

**Status:** done 2026-08-07
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

`CORTEX_VRAM_CORTEX_GB` is the term the placer subtracts from the soft cap on every spawn's
fit-test, and it was never measured. It had been deferred at two ADRs and recorded on no index at
all, so for three days a number bounding every admission sat outside every count. That is the
doc-first rule's own failure mode, recorded here rather than fixed quietly.

The previously published 8448 to 8468 MiB was an idle figure, and a reservation has to cover a peak.
At the shipped tier shape, read out of the running child's argv (`-ngl 99 --ctx-size 16384
--parallel 1 --jinja` with the projector and `--image-max-tokens 1024`), the tier is 8400 to 8484
MiB idle and 8573 MiB at its peak, above a floor read with the tier stopped at both ends of the
session (1261 to 1301, then 1259 to 1308 MiB, agreeing within 7 MiB). A 13180-token prompt with 924
tokens decoded allocated nothing, because llama.cpp takes the 16K KV and the compute buffers at
load; the only thing that arrives with the work is the vision path's 70 to 90 MiB on the first
image, and it stays.

Most of the apparent 2.8 GB gap was a unit: 11.3 was `nvidia-smi` total used with the desktop's
floor inside it, while every other term in this budget is a tier's own cost.

The reservation is 8.6 GiB, 233 MiB over the measured peak, which covers the sampler's spread, the
floor bracket and one more vision-sized allocation. The headroom goes from 2.7 to 5.4 GiB, so a
spawn declared at the GPU tier's measured 3319 MiB is GPU-placed where nothing ever was
([ADR-0012](../../adr/ADR-0012-resource-governance.md) decision 14, procedure in
[runbooks/llamacpp-gpu.md](../../runbooks/llamacpp-gpu.md)).

## History

- 2026-08-07: Closed as a new measurement of `CORTEX_VRAM_CORTEX_GB`, recorded at ADR-0012 decision
  14 with the procedure in [runbooks/llamacpp-gpu.md](../../runbooks/llamacpp-gpu.md). Read its own
  way the old reservation was about 1.7 GiB high, and read the budget's way about 2.6 GiB high. One
  entry opened in its place, the term this measurement deliberately left alone.
