# The boot fit warning has not been read on the card

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0054](../../adr/ADR-0054-baseline-residency.md)
**Verified:** 2026-11-23

Once every boot tier answers ready, the model host reads the card and logs
`the tiers started at boot leave the card less free memory than its floor` when less than
1,536 MiB is free (`BootFit` in
[boot_fit.py](../../../brain/packages/model_manager/src/cortex_model_manager/boot_fit.py)). The
tests drive it with fakes only. Nobody has started the model host with a context that fills the
card and read the log.

What would close it: the model host (image `cortex-model-host`, the tree's model manager bound
over the image's packages, compose defaults) started twice on the 24 GB card, once with
`CORTEX_CTX_SIZE=400000` and once with the default. Pass rule, written before the draw: the first
logs the warning once, with a free figure within 300 MiB of what `nvidia-smi` reads at the same
time and the cortex's `--ctx-size` 400000; the second logs the `INFO` line and no warning. Write
the two log lines and the readings into
[store-and-process-restarts.md](../../readings/store-and-process-restarts.md#a-server-that-keeps-exiting).

## History

- 2026-11-23: filed when the warning was added without a live read, which the slot that added it
  was told not to draw.
