# Measured swap timings

**Status:** never attempted
**Session:** gpu-tier-scale
**Capability:** W+G
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Blocked on the tier-scale swap, and it inherits that item's **W+G** with the block: these are the
phases of a real handoff, and a real handoff starts at an approved confirm card. The one number you
can take without the overlay is the deep tier's bare load time, which the deep-model pick measured
and which this compares the swap's load phase against.

**What only this proves.** ROADMAP assumption 2 at the brain tier, and whether the default of
`CORTEX_SWAP_LOAD_TIMEOUT_S` (300 s, listed in
[runbooks/model-swap.md](../../runbooks/model-swap.md) beside the drain timeout) is right. That
assumption says a cortex-to-brain swap is a `llama-server` stop and start (ADR-0005), so its cost is
loading a multi-GB GGUF from the bind-mounted Windows drive, assumed to be seconds and reported to
the overlay over the `Converse` status stream; if the Windows mount is the bottleneck, hot models
get mirrored into a WSL-side cache. [ADR-0030](../../adr/ADR-0030-brain-handoff.md)'s risks say the
same: the 300 s default is an estimate from ADR-0004's mount-read numbers, and if the real figure is
worse, the fix is the recorded WSL-side model mirror rather than a design change.

**Do.** Time the phases of the swap: drain, evict, load, work, restore.

**Pass.** Seconds, not minutes, and comfortably inside the load timeout.

**Fail.** If the mount dominates, the answer is already recorded and is a deployment change: mirror
hot models WSL-side. Do not treat a slow mount as a design finding.

**Record it.** [runbooks/model-swap.md](../../runbooks/model-swap.md) contains the literal
instruction `Record the timings here` with nothing recorded, and
[runbooks/llamacpp-gpu.md](../../runbooks/llamacpp-gpu.md) has the mount-read figures this compares
against.

## History

- 2026-07-19: marked as needing both capabilities with the swap and the chaos kill, after an audit
  tried to execute the three of them from the GPU doc alone. The marking is inherited here, these
  being the phases of the swap rather than a run of their own.
- 2026-08-04: the deep-model pick closed and produced the figure this item's load phase is compared
  against, the deep tier loading cold in 99.6 s, which leaves the shipped 300 s
  `CORTEX_SWAP_LOAD_TIMEOUT_S` about two thirds unspent. That close unblocked this item along with
  the swap and the chaos kill, leaving the overlay as what still blocks it.
