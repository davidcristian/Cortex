# The shipped subagent VRAM ask placeholder

**Status:** landed 2026-08-08
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

The shipped subagent VRAM ask is a placeholder about 2.3 GiB above what the tier measures.
It bites the moment a deployment wants GPU subagents.
`docker-compose.subagents.yml` sets `CORTEX_SUBAGENTS_VRAM_GB=5.5` and the code default is 2.0,
neither of them measured; the GPU-placed subagent tier read **3319 MiB** on this card on
2026-08-04, which is 3.24 GiB. With the reservation corrected the headroom is 5.4 GiB, so the ask
is now the only reason the shipped stack still refuses every GPU placement, where before it was
one of two. The reservation was **not** rounded down to 8.5 to make 5.5 fit, which would have
been choosing the answer and would have left two wrong numbers agreeing; the ask is the wrong
number and it should be corrected by measuring one spawn of the roster's default entry rather
than by arithmetic. It is a compose default plus a `SubagentsConfig` field, so nothing behind a
port has to move, and the same sitting should decide whether the roster's alternate entry needs
its own figure. Pinned by a test today
(`test_shipped_vram_budget_still_refuses_the_compose_placeholder_ask`), so a later change to the
reservation cannot quietly flip the shipped stack into GPU placement without answering this.
**Closed 2026-08-08 by measuring the tier, one day after it opened
([ADR-0012 measured-ask addendum](../../adr/ADR-0012-resource-governance.md), procedure in
[runbooks/subagents-cpu.md](../../runbooks/subagents-cpu.md) section 2c).** The ask is **3.5 GiB**
in both declarations, the compose default and the `SubagentsConfig` field. Measured at the shape
read out of the running child's argv (`-ngl 99 --ctx-size 8192 --parallel 2 --jinja` with
thinking off, no projector), with the cortex resident throughout and `nvidia-smi` total used
sampled every 0.2 s, the tier is 3228 to 3355 MiB idle and costs at most **3410 MiB** above a
floor read with it stopped at both ends of the session (10448 to 10500, then 10428 to 10493 MiB,
agreeing within 20 MiB). Twelve requests each filling its slot's whole half of the 8192 KV
(3803 prompt tokens plus 293 decoded, exactly 4096) moved nothing beyond the idle band: this tier
has no vision path, so unlike the cortex the peak is a load-time figure with no late allocation at
all. The margin is 174 MiB, which covers the sampler's spread and the floor bracket twice over.
**The entry's own account was right about one placeholder and wrong about the other**, which is
worth stating because it was the safe-sounding one: 5.5 was about 2.1 GiB high as recorded, but
the code default of 2.0 was about 1.3 GiB **low**, so a deployment wiring subagents without the
compose file was admitting a spawn onto room the tier would overrun, the unsafe direction, while
the docs called it a GPU-less-safe placeholder. **The alternate needed no figure of its own**,
which this entry asked the same sitting to decide: no GPU executor exists for the roster's
alternate at all (its `gpu_endpoint` falls back to its own CPU server), so its 2.5 charges a
ledger for a placement that always runs on the CPU, and that is the interim one-executor stance
rather than a measurement anybody could take today. What replaces the old pin is a pair of tests
reading the deployment's own numbers rather than literals: one places the shipped ask and its
successor (GPU then CPU), the other holds the margin above the measured peak. Proven on the stack
and not only in the gate: under the old ask the live GPU arm could not select itself (5.5 against
5.4 GiB of headroom) and the tier served no task; under 3.5 the same command places one spawn
there, answered in 152.11 ms against 13134.73 ms for the sibling that overflowed, and the arm was
shown able to redden first by pointing the GPU endpoint at a closed port. **What is not fixed is
what the ask means for the second spawn:** the ledger charges one tier's whole footprint per
spawn, and a second spawn onto that standing process allocates nothing, so refusing it buys decode
speed rather than memory. That is the modelling gap recorded in
[inference-model-manager.md](../index.md#inference-model-manager), unchanged here and now the honest
reading of the refusal.

## Trail

- 2026-08-07: Opened by the cortex reservation's re-measurement, which refused to bend this term:
  8.5 GiB would have exactly admitted the 5.5 GiB the compose file asks, and choosing it would have
  been choosing the answer on a 131 MiB margin.
- 2026-08-08: Closed by measuring the tier one day after it opened, recorded at the
  [ADR-0012 measured-ask addendum](../../adr/ADR-0012-resource-governance.md) with the procedure in
  [runbooks/subagents-cpu.md](../../runbooks/subagents-cpu.md) section 2c. It was taken straight away
  because the trigger is a deployment wanting GPU subagents and the shipped stack is that deployment
  the moment the arithmetic allows it.
- 2026-08-08: The two declarations of the ask are tied together by nothing but the comments that say
  so, `crosscheck.py` reading module-level constants where these are a pydantic field default and a
  compose environment value.
- 2026-08-08: With this ask measured, the index recorded every term of that VRAM budget as a
  measurement rather than a declared figure.
