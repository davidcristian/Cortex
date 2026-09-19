# Model-manager process lifecycle, co-residency and real swap

**Status:** done 2026-08-07
**Area:** inference-model-manager
**Origin:** [ADR-0007](../../adr/ADR-0007-model-manager-inference.md)

The pure single-resident manager existed; process I/O and a real swap did not. Both arrived
behind an unchanged `ModelManager` port, with `acquire(model) -> ModelLease` untouched: the
process half went behind a new `ModelHost` port rather than into `ModelManager`, and the swap
behind a `ResidencyController` that only `SwappingModelManager` implements. The real half is the
`model-host` supervisor sidecar: one `llama-server` child per logical tier, an HTTP control API
whose requests name a logical id and nothing else, and the `HttpModelHost` adapter, all passing
the same contract suite as the in-core scriptable twin. It was tested in Docker on the 8 GB dev
GPU with two small artifacts in place of the tiers (real processes started, checked healthy,
evicted, swapped, killed, restarted; see [runbooks/model-swap.md](../../runbooks/model-swap.md)).

**Co-residency closed 2026-08-07**
([ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md)), measured first and designed
second, on an RTX 5090 Laptop reporting 24463 MiB, with the real tiers driven through the shipped
sidecar.

- The cortex costs 8448 to 8468 MiB with its projector at 16K, not the ~11.3 GB every doc had
  quoted from a 2026-06-29 build, and the deep model 19117 to 19125 MiB. The pair needs 29139 MiB
  against 24463 over a 1552 MiB floor, and misses by 4676 MiB.
- Nothing reports that shortfall. Started with the cortex resident, the deep tier reported `ready`
  at 23539 to 23642 MiB with 496 MiB free, because WSL2 pages the overcommit to system memory. The
  only sign is decode rate: 14.80 to 17.29 tok/s co-resident against 25.07 to 33.28 alone, with
  the cortex unaffected at 44.68 to 49.47. So `nvidia-smi` alone cannot answer this question
  either way.
- What does fit is the deep model beside the shipped gemma-4-E4B subagent tier: 23555 to 23642 MiB
  with 908 MiB free, the deep model decoding 28.92 to 29.82 tok/s, which is its solo rate, and
  generating on both at once allocated nothing new (23639 MiB under load against 23642 idle).
- Against that, a handoff costs 0.48 s to evict the cortex, 70.03 s for the deep model to become
  ready, and 32.36 s to restore: 102.9 s in which every spawn is refused, the deep phase's own
  included.

`CORTEX_SWAP_CORESIDENT` shipped, off by default. It is one flag doing two things that are
useless apart: `swap_in` stops the cortex and nothing else, and the conductor never enters the
drain window nor announces one, so delegation runs through the handoff. It is safe because a
co-resident handoff stops no tier that delegated work can reach.

## History

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section into this area, as a
  Slice 4 inference deferral and the oldest entry in this backlog.
- 2026-07-17: The pure half shipped with the brain-handoff conductor sub-slice, which delivered
  [ADR-0030](../../adr/ADR-0030-brain-handoff.md) decisions 3 to 5: the `ModelHost` port and its
  scriptable twin, `SwappingModelManager` with its separate residency scope, `SwapConductor`, the
  deep model's phase, boot recovery and the escalating turn wrapper, all proved over fakes by a
  chaos suite that kills a handoff at every step boundary.
- 2026-07-18: The real process lifecycle shipped with the model-host sub-slice. The area count did
  not go down, because co-residency was the other half of this one entry and stayed deferred under
  ADR-0030 decision 8's rule that the deep model is alone on the GPU.
- 2026-07-19: Stayed in this backlog when host-side work was moved to `docs/host/`, listed there
  only as something a run on the user's hardware could also settle, because the work is code. The
  blocker was restated the same day, from a slice that had been marked done on 2026-07-18 to the
  hardware itself: a card that fits the tiers this entry would keep alive.
- 2026-08-07: Co-residency closed on the 24 GB card, measured before it was designed, and the
  hardware bucket emptied with it. The area went 7 to 8, because the two refinements that opened
  in its place are both things this work made reachable
  ([R-107](107-co-resident-fit-check.md) and [R-108](108-notice-a-spilled-handoff.md)).
- 2026-08-07: A controlled re-measurement hours later put the cortex tier's peak at 8573 MiB above
  the floor and lowered `CORTEX_VRAM_CORTEX_GB` from 11.3 to 8.6, which is recorded at
  [resource-governance.md](../index.md#resource-governance) and moves none of the pair arithmetic
  above. On the overcommit the two sources word it differently and both readings are kept: the
  index says WSL2 paged roughly 6 GB to system memory rather than refusing the allocation, where
  the arithmetic above puts the shortfall at 4676 MiB.
- 2026-08-07: Recorded on the host side as settled by the agent in Docker against the real tiers,
  so it was never host work, and the line it had been given there was removed.
