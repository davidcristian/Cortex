# Model-manager process lifecycle, co-residency and real swap

**Status:** landed 2026-08-07
**Area:** inference-model-manager
**Origin:** [ADR-0007](../../adr/ADR-0007-model-manager-inference.md)

The entry read: "**`cortex_model_manager` process lifecycle,
co-residency, real swap.** The pure single-resident manager exists now; process I/O and swap land
in **Slice 11** behind the unchanged `ModelManager` port (consequences)." It landed behind that
port exactly as written, `acquire(model) -> ModelLease` untouched: the process half went behind a
**new, segregated** `ModelHost` port rather than into `ModelManager`, and the swap behind a
`ResidencyController` that only `SwappingModelManager` implements, which is what kept the
original port unchanged rather than merely compatible. The real half is the `model-host`
supervisor sidecar: one `llama-server` child per logical tier, an HTTP control API whose requests
carry a logical id and nothing else, and the `HttpModelHost` adapter, all passing the same
contract suite as the in-core scriptable twin. The mechanism is agent-validated in Docker on the
8 GB dev GPU with two small artifacts standing in for the tiers (real processes started,
health-gated, evicted, swapped, killed, restarted; see
[runbooks/model-swap.md](../../runbooks/model-swap.md)); **tier scale stays host-side**, the dev
card being unable to hold the real cortex beside a deep model. **Co-residency remains open**, and
its shape is now recorded rather than sketched: ADR-0030 decision 8's v1 rule is that while the
deep model is resident it is **alone** on the GPU, since no candidate fits beside the ~11.3 GB
cortex in 24 GB, so keeping CPU subagents serving through a swap, or a tiny GPU subagent beside
the deep model on a larger card, is the thing still deferred. What this landing changes about it:
the tiers it would need to keep alive are now real hosted models rather than hypothetical ones,
so the deferral is exercisable for the first time on hardware that fits them.
**Co-residency closed 2026-08-07** ([ADR-0030](../../adr/ADR-0030-brain-handoff.md) co-residency
addendum), measured first and designed second, on an RTX 5090 Laptop reporting 24463 MiB with the
real tiers driven through the shipped sidecar. The paragraph above is wrong in three of its
numbers and the ADR corrects them there; the ones that matter here are that the cortex costs
**8448 to 8468 MiB** with its projector at 16K rather than the ~11.3 GB every doc quoted, and the
deep model **19117 to 19125 MiB**, so the pair wants **29139 MiB against 24463** over a 1552 MiB
floor and misses by **4676 MiB**. **That cortex figure is an idle one**, and a controlled
re-measurement hours later the same day put the tier's peak at 8573 MiB above the floor and
lowered `CORTEX_VRAM_CORTEX_GB` from 11.3 to 8.6, which this paragraph declined to do and was
right to decline; the close is at [resource-governance.md](../index.md#resource-governance), where the
placer's budget lives, and it moves none of the pair arithmetic above. It does not miss loudly. Started with the cortex resident the
deep tier reported `ready` at 23539 to 23642 MiB with 496 MiB free, because WSL2 pages the
overcommit to system memory, and the only witness is decode: **14.80 to 17.29 tok/s co-resident
against 25.07 to 33.28 alone**, with the cortex untouched at 44.68 to 49.47. So `nvidia-smi` alone
cannot tell this deferral's answer either way, which is the methodological finding a later sitting
should not have to rediscover. What **does** fit is the half decision 8 named second, and it needs
no tiny model: the deep model and the **shipped** gemma-4-E4B subagent tier sat at 23555 to 23642
MiB with 908 MiB free, the deep model decoding 28.92 to 29.82 tok/s beside it, which is its solo
rate, and generating on both at once allocated nothing new (23639 MiB under load against 23642
idle). Against that, a handoff costs 0.48 s to evict the cortex, 70.03 s for the deep model to
gate warm, and 32.36 s to restore, **102.9 s** in which every spawn is refused, the deep phase's
own included. What landed is `CORTEX_SWAP_CORESIDENT`, **off by default**, one flag doing two
things that are useless apart: `swap_in` stops the cortex and nothing else, and the conductor
never enters the drain window (nor announces one), so delegation runs through the handoff. It is
safe because a co-resident handoff stops no tier delegated work can reach, which is the reopening
deferral's own condition rather than a way around it. Two things it deliberately does not do are
recorded below as this area's newest entries.

## Trail

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section into this area doc,
  verbatim, as a Slice 4 inference deferral and the oldest entry this backlog has carried.
- 2026-07-17: The pure half landed with the brain-handoff conductor sub-slice, the first of the two
  brain-handoff sub-slices that carried [ADR-0030](../../adr/ADR-0030-brain-handoff.md) decisions 3 to
  5: the `ModelHost` port and its scriptable twin, the `SwappingModelManager` with its segregated
  residency scope, the `SwapConductor`, the deep model's phase, boot recovery and the escalating
  turn wrapper, all proven over fakes by a chaos suite that kills a handoff at every step boundary.
- 2026-07-18: The real process lifecycle landed with the second of them, the model-host sub-slice:
  the supervisor sidecar behind that same port with one `llama-server` child per tier,
  mechanism-validated in Docker on the dev GPU with two small artifacts. The area count did not
  decrement, because co-residency is the other half of this one entry and stayed deferred with
  ADR-0030 decision 8's brain-runs-alone rule.
- 2026-07-19: Stayed in this backlog when host-side work was extracted to `docs/host/`, listed there
  only as something a sitting on the user's hardware could also settle, because the work is code and
  moving it would split a design decision from its area. The blocker it sat under was restated the
  same day, from a slice that had been marked done on 2026-07-18 and so named a blocker that had
  stopped existing, to the hardware itself: a card that fits the tiers this entry would keep alive.
- 2026-08-07: Co-residency closed on the 24 GB card the hardware bucket had been waiting for,
  measured before it was designed, and that bucket emptied with it. The area went 7 to 8, because
  the two refinements that opened in its place are both things the landing made reachable rather
  than things it broke.
- 2026-08-07: The ~11.3 GB the measurement corrects had been quoted from the 2026-06-29 build, which
  is where every doc took it from. On the overcommit the two sources word it differently and both
  readings are kept: the index says WSL2 paged roughly 6 GB to system memory rather than refusing
  the allocation, where this entry's own arithmetic puts the pair's shortfall at 4676 MiB.
- 2026-08-07: Recorded on the host side as settled by the agent in Docker against the real tiers, so
  it was never host work in the end, and the line it had been given there was struck.
