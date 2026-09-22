# ADR-0055: Co-residency, the deep model's fit check and the spill watch

**Status:** Accepted (2026-08-19)

## Context

By default the deep model runs alone: a handoff evicts the cortex and every peer tier and drains the
subagent pool for the whole window ([ADR-0030](ADR-0030-brain-handoff.md) decision 8). On the 24 GB
card this repo targets that costs delegation for the whole deep phase, and the swap itself about
1.5 times the deep model's warm load ([model swap](../readings/model-swap.md)).

Measured on that card ([co-residency](../readings/co-residency.md)): the cortex and the deep pick do
not fit together (about 4.6 GiB short), and the deep pick and the shipped GPU subagent tier fill the
card with no margin: beside that peer the deep model decoded at its solo rate on 2026-08-07 and at
0.36 and 0.62 of it in two starts on 2026-09-22, with the same tier sizes. So on that card
co-residency has no peer that fits. The cortex stays evicted in every configuration.

Measuring it is the hard part. Under WSL2 an overcommitted card does not refuse the allocation: the
driver pages the excess out to system memory, both tiers report `ready`, and `nvidia-smi` afterwards
reads the same free memory for a genuine fit as for a 4.6 GiB overcommit. The only sign of the
difference is throughput: the model that loaded second decodes at roughly half its solo rate. So a
check has to read the card **before** the allocation, and something has to watch decode **after**
it.

## Decision

1. **`CORTEX_SWAP_CORESIDENT`, off by default.** `ResidencyPlan.coresident`. Off, nothing changes
   and the deep model runs alone. On, exactly two things change: the swap in stops the cortex and
   nothing else, so the evict-list peers keep serving, and the conductor neither drains the pool nor
   announces a drain, so delegated work flows through the handoff and the deep phase may spawn. They
   belong together: a kept peer nothing may be delegated to buys nothing, and an open pool over an
   evicted peer is the hazard the drain exists for. The rule that makes them safe together is that
   **a co-resident handoff stops no tier delegated work can reach**. The swap back still starts
   every evict-list tier, which does nothing to a running child and also restarts a peer that died
   while the deep model held the card. The setting is the deployment's claim about its own card,
   which the brain container cannot see, and the maintainer approved it with the default off: the
   deep model is exclusive unless a deployment has measured otherwise.
2. **The fit check reads the card at the one moment a reading is evidence.** The deployment declares
   the deep model's measured cost, `CORTEX_SWAP_BRAIN_VRAM_MIB`. Inside the swap in, after the last
   stop and before the start, `ModelHost.device_memory()`
   ([ADR-0053](ADR-0053-model-host-supervisor.md) decision 13) is compared against it; short of it,
   or with no reading at all, the swap in raises `SwapFailedError` with both figures, the deep model
   is never started, and the scope restores. Zero (the default) means no check. With `coresident` on
   over the real supervisor the figure is required at startup. The check is not at wiring time (free
   memory moves by the gigabyte while the machine runs, and at startup the cortex holds the card);
   it does not fall back to evicting the peers (the drain was already skipped, so stopping them now
   would reopen admission onto a stopped tier); and it follows the cortex's stop, costing a
   misconfigured deployment one cortex reload rather than a second declared figure. It cannot see a
   wrong declared figure, memory taken during the load, or a spill afterwards; a deployment that
   wants slack adds it to the figure, since an invented margin would be one more unchecked number.
   The figure is the cost of the deep tier's whole command line, which the sidecar builds from the
   model file, context size, layer count and drafter settings and the brain never receives, so a
   deployment that changes any of them measures and declares the figure again.
3. **The placer is charged for the window.** `SubagentPlacer.charge_handoff(resident_gb=)` and
   `charge_baseline()` (`ports_placement.py`) replace the cortex's reservation with the deep model's
   declared cost for the window and restore it after; the placed-spawn ledger is untouched, since a
   spawn's VRAM did not move. The residency scope writes both edges (`residency_charge.py`, from the
   swap in and the successful restore), since only it knows when the card changes hands and its
   `finally` guarantees the reversal. The charge is the declared figure, not a fresh reading,
   because `place` is synchronous and lock-free and the fit check has already compared that figure
   with the card. It is written before the swap in, so a spawn cannot take the room the check just
   measured; it is reversed only once the cortex serves, so a restore that gave up keeps spawns on
   the CPU. With no declared figure the window is never entered, rather than crediting the evicted
   cortex back.
4. **The spill watch reads decode rate off the deep phase's own completions.** The inference port's
   event stream gains a `DecodeCadence` event (`tokens_per_second`, `tokens`), emitted after the
   text by a backend whose engine reports a rate; `LlamaCppBackend` reads llama.cpp's `timings`
   object off the final streamed chunk, which the server sends unasked. Emitting none is legitimate
   and means no reading, never healthy. `stream_tool_loop` collects it into an optional
   `CadenceWatch` on `ToolLoopContext` and yields nothing, so a rate never reaches a stream the user
   reads; only the deep phase passes a watch. A sample under `MIN_CADENCE_TOKENS` (32) is counted
   and never judged, and the **fastest** qualifying sample decides, since a spill caps every
   completion while it lasts and a card busy for one round is not proof. The minimum rate is the
   deployment's own measurement, `CORTEX_SWAP_BRAIN_DECODE_TPS`; zero reports the rate and judges
   nothing, and co-residency does not require it, because it guards no decision. On a collapse the
   deep phase logs one `WARNING`, and a healthy handoff logs its rate at `INFO`, the number a later
   minimum is set from.
5. **A spill result is sent with the residency report while it still describes the present.** The
   deep phase calls `PaceSink.note_pace(*, spilled)` (synchronous, a judgement and never a reading)
   through `CadenceTerms`, which holds the minimum rate and the sink together. `HandoffPace`
   (`residency_pace.py`), held by the manager, keeps the note for one hour
   (`DEFAULT_SPILL_DWELL_S`, a constructor value) or until a later handoff decides it: one that held
   its pace clears it, one that spilled sets it again. A completion too short to judge, or a
   deployment with no minimum, calls nothing, so no judgement clears an existing note. The note is
   `SPILLED_PACE_DETAIL`, joined after any peer note ([ADR-0054](ADR-0054-baseline-residency.md)
   decision 7): "the last deep task ran far slower than this deployment measured for it, so deep
   tasks are taking much longer than they should". It names the deployment's measurement and the
   consequence, not a rate a tooltip reader cannot judge. It is not stored, since a restart is the
   one event that reliably ends its commonest cause.

## Consequences

- `SwappingModelManager` still leases one resident model: a subagent tier is leased through its own
  `SingleResidentModelManager` against a static endpoint, so keeping peers needs no residency set.
- The card's free memory never reaches `Health`: it means something only at one moment of a swap.
  The reading goes on `ModelHost` rather than a port of its own, its one caller having the other
  verbs.
- The watch asks the server for nothing; the build volunteers `timings`, and a build that did not
  would need `timings_per_token` on every request in the repo.
- The watch does not act: nothing refuses, degrades or withdraws co-residency on a collapse, since
  the rate is known only after the reply has streamed.
- It watches only the deep phase, since only a handoff changes what is on the card.
- It does not watch prefill. The same `timings` object has a prompt rate, but `prompt_n` counts only
  tokens not served from cache, so a mostly cached prompt reads slower than a cold one on an
  unchanged card, and a tool loop's later completions are exactly that case. A prefill minimum would
  need a minimum processed-prompt length as well as a rate.
- Which tier pays depends on load order (the newcomer is paged out first), and a spilled tier does
  not fully recover when its peer is evicted, so a minimum rate is measured from a cold load onto a
  clear card.
- A spill count is stored nowhere: a successful handoff's record is deleted, so the note expires
  unseen if nobody reads the dot within the hour.

## Alternatives rejected

- **`CORTEX_SWAP_KEEP_PEERS` or a `CORTEX_SWAP_KEEP_MODELS` list**: the first names the mechanism,
  the second splits one baseline residency across two settings that could disagree.
- **`CORTEX_SWAP_REQUIRED_FREE_MIB` or `CORTEX_VRAM_BRAIN_GB`**: the first names the test, the
  second reads as a placer budget and hides MiB behind a unit converted at the boundary.
- **Reading free memory after the load**: it reads the same for the fit it must accept and the
  overcommit it must refuse.
- **A flag that stops promising co-residency after a spill**: a judgement covers one handoff, a
  gigabyte the desktop took mid-load produces one, and such a flag has no way back, since the only
  evidence that could clear it is the co-resident handoff it disabled.
- **Telling the user in the reply**: telemetry in an assistant message, arriving after the answer.
- **Counting the drafter from `GET /health`**, the sidecar reporting the size on disk of the files
  a tier loads beside its model and the check adding it to the figure: the file is about nine
  tenths of the drafter's card cost (911 MiB against 997 to 1020), so the rest would be an invented
  margin; the context size and layer count move the cost too and are no file; and the figure would
  stop being a measurement of the load that runs.
- **Refusing co-residency at startup whenever the deep tier drafts**: the brain would need the same
  port change to see the drafter, and the refusal forbids a card with room for all three tiers.

## Related

[co-residency](../readings/co-residency.md), [model swap](../readings/model-swap.md),
[model-swap](../runbooks/model-swap.md), [brain-core](../modules/brain-core.md),
[brain-inference](../modules/brain-inference.md), [ADR-0030](ADR-0030-brain-handoff.md),
[ADR-0053](ADR-0053-model-host-supervisor.md), [ADR-0054](ADR-0054-baseline-residency.md),
[ADR-0012](ADR-0012-resource-governance.md) (the placer and the cortex reservation).
