# The 24 GB machine (tag G)

Eight items, one bring-up, one blocker. The first one gates four of the others, which is why this
is a single doc rather than eight: the dependency chain is the whole story on this side in a way
it is not on the Windows side.

Everything here is blocked on VRAM, not on an operating system. The dev GPU is an 8 GB card
and `gemma-4-12b-it-qat-q4_0.gguf` alone takes 7715 of its 8188 MiB, so the real cortex cannot be
swapped against any deep-model candidate, and no subagent can be GPU-placed beside a resident
cortex. Kept verbatim from the ROADMAP's Slice 11 status:

> What remains is the host-side capstone on the 24 GB machine: the brain pick, the tier-scale
> swap, measured timings, the runbook, and the injection-harness run. The ADR states plainly why
> the last of those cannot move here: CI has no GPU and the dev GPU cannot hold the cortex beside
> a ~31B brain, so the swap's **mechanism** is agent-validated against real `llama-server`
> processes with two small stand-ins (started, health-gated, evicted, swapped, killed under the
> daemon, and restarted over their own corpses) while **tier scale and its VRAM arithmetic** stay
> host-validated.

One correction to that sentence, which is why it is quoted rather than carried forward as the
plan: **the runbook exists.** [runbooks/model-swap.md](../runbooks/model-swap.md) landed
2026-07-18 with the measured mechanism in it. What is owed is the user filling in its tier-scale
sections, one of which literally reads "Record the timings here".

## Before you start

- `just up-gpu` with the models mount reachable and the GPU visible through the container toolkit.
- `CORTEX_MODELHOST_BACKEND=supervisor`, so the real `model-host` sidecar runs one `llama-server`
  child per tier.
- `CORTEX_ESCALATION=1` for anything that swaps. Escalation is **off by default**.
- `CORTEX_MODEL_FILE_BRAIN` pointing at the pick, once item 1 has produced one.
- Read [runbooks/model-swap.md](../runbooks/model-swap.md) first, whose opening paragraph already
  states which of its numbers are the mechanism's and which are a tier's.

## The dependency chain

```
1. deep-model pick  ──┬──> 2. tier-scale swap ──┬──> 3. chaos kill at scale
                      │                         └──> 4. measured timings
                      └──> 5. the ~31B injection-harness run

6. GPU-placed subagent · 7. cgroup caps · 8. resident VRAM with the projector   (independent)
```

---

## 1. The deep-model pick

**Status: never attempted. Blocks items 2, 3, 4 and 5.**

**What only this proves.** Which of the four brain candidates actually fits and serves on 24 GB.
Nothing about it is answerable on the dev GPU. [ADR-0004](../adr/ADR-0004-model-lineup.md) locked
the candidate set and says of the tier only that "**Brain** (~31B) is the swap model: it evicts the
cortex, so it gets the full budget; hybrid `-ngl` / CPU-KV fallback if it doesn't fit". The
candidates are `Qwen3.6-27B-GGUF (Q4_K_M)`, `Qwen3.6-35B-A3B-GGUF (UD-Q3_K_M)`,
`gemma-4-31B-it-qat-q4_0-gguf`, and `gemma-4-26B-A4B-it-qat-q4_0-gguf`.

**Do.** Bring each candidate up alone under the model host and measure VRAM at the context size the
brain phase will use, load time off the mount, and answer quality on a handful of the kinds of
question that justify escalating at all. The method is the one
[runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md) already uses for the other tiers: bring the
host up, read `nvidia-smi`, record the row.

**Pass.** One candidate locked, with its measured numbers.

**Fail.** No candidate fits with acceptable context. The recorded fallback is ADR-0004's hybrid
`-ngl` / CPU-KV path, which is a real answer and should be written down as one rather than treated
as a failure of the slice.

**Record it.** An addendum to [ADR-0004](../adr/ADR-0004-model-lineup.md), which
[ADR-0030](../adr/ADR-0030-brain-handoff.md) explicitly expects ("the brain pick (ADR-0004 gains
its addendum)"); the Brain row of the table in
[runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md), which today reads
`| Brain | _tbd (host-side pick)_ | | | | |`; and `CORTEX_MODEL_FILE_BRAIN` in the GPU compose,
whose comment today says there is no deep-model pick yet.

---

## 2. The tier-scale cortex to brain swap

**Status: never attempted.** Blocked on item 1.

**What only this proves.** The VRAM arithmetic. The agent's validation ran two small artifacts
through every code path, which is explicitly not the same thing: evicting ~11.3 GB and loading 15
to 18 GB alone is the part that was never exercised.

**Do.** From the overlay, ask something that escalates. Watch the swap window's `StatusUpdate`s.

**Pass.** The cortex is evicted, the deep model loads, the answer returns, and the cortex is
restored. `Health` reads `ready=false` with a truthful residency detail between turns during the
window, which lights the overlay's connection dot amber.

**Fail.** A load that never completes inside `CORTEX_MODELHOST_LOAD_TIMEOUT_S` is item 4's problem,
not this one. The failure that matters here is a restore that does not happen:

```
could not restore '<cortex model>' after 2 attempts; manual recovery is needed
```

which is `ResidencyRestoreError`, and [runbooks/model-swap.md](../runbooks/model-swap.md) has the
section on what to do about it.

**Record it.** A dated addendum to [ADR-0030](../adr/ADR-0030-brain-handoff.md) and the tier-scale
half of [runbooks/model-swap.md](../runbooks/model-swap.md).

---

## 3. The chaos kill at tier scale

**Status: never attempted.** Blocked on items 1 and 2.

**What only this proves.** That the one hard rule holds when a real ~31B process dies, not a 2B
stand-in. Kept verbatim from [ADR-0030](../adr/ADR-0030-brain-handoff.md):

> **Host half (host-side, runbook-driven).** On the 24 GB machine: `docker exec` into
> `model-host` and `kill -9` the brain's `llama-server` child mid-handoff (and once mid-load),
> then verify from the overlay that the turn fails honestly, the cortex comes back, and the
> next turn works; procedure and expected timings recorded in `docs/runbooks/model-swap.md`.
> Stated plainly: **CI has no GPU and the dev machine's 8 GB card cannot hold the 12B cortex
> and a ~31B brain, so the tier-scale swap can only be validated host-side; the CI chaos test
> over fakes is the gate.**

**Do.** [runbooks/model-swap.md](../runbooks/model-swap.md), "The chaos kill, host-side", which
carries the exact command:

```
docker compose --project-directory . -f docker/docker-compose.yml \
  -f docker/docker-compose.gpu.yml exec model-host sh -c 'kill -9 $(pgrep -f 8081)'
```

Once mid answer and once mid load.

**Pass.** The turn fails honestly on the stream, the cortex comes back (the swap back is a
`finally`), and the next turn works.

**Fail.** A wedged stream, a lost session, or a cortex that does not return. Any of those is a
finding against the hard rule itself and is the most serious thing this directory can produce.

**Record it.** The same runbook section and an ADR-0030 addendum.

---

## 4. Measured swap timings

**Status: never attempted.** Blocked on item 2.

**What only this proves.** ROADMAP assumption 2 at the brain tier, and whether the 300 s load
timeout default is right. Kept verbatim from that assumption:

> **Swap latency.** A cortex↔brain swap is a `llama-server` stop + start (ADR-0005), so its cost is
> loading a multi-GB GGUF from the bind-mounted Windows drive. Assumed acceptable (seconds,
> reported to the overlay via the `Converse` status stream); if the Windows mount is the
> bottleneck, hot models get mirrored into a WSL-side/volume cache (measured in Slice 4).

and from [ADR-0030](../adr/ADR-0030-brain-handoff.md)'s risks:

> **Swap latency is unmeasured for the brain tier.** The 300 s default load timeout is an estimate
> from ADR-0004's mount-read numbers; if the real figure is worse, the fix is the recorded
> WSL-side model mirror lever (ADR-0005 consequences), not a design change.

**Do.** Time the phases of item 2: drain, evict, load, work, restore.

**Pass.** Seconds, not minutes, and comfortably inside the load timeout.

**Fail.** If the mount dominates, the lever is already recorded and is a deployment change: mirror
hot models WSL-side. Do not treat a slow mount as a design finding.

**Record it.** [runbooks/model-swap.md](../runbooks/model-swap.md) contains the literal instruction
`Record the timings here` with nothing recorded, and
[runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md) carries the mount-read figures this
compares against.

---

## 5. The ~31B injection-harness run

**Status: never attempted.** Blocked on item 1. **The only host item whose outcome can change
shipped policy.**

Kept verbatim from [refinements/untrusted-content.md](../refinements/untrusted-content.md), the
entry that moved here:

> **Injection-harness run against the ~31B brain tier.** The harness's brain tier is **opt-in and
> not yet run** (`CORTEX_PROBE_BRAIN=1`, as the VRAM cost needs the others evicted; ADR-0013
> harness addendum + [ADR-0004](../adr/ADR-0004-model-lineup.md) injection addendum). Run it when
> the brain pick lands (**Slice 11**), and whenever picks or the preamble change.

Why it is policy and not just a number, from [ADR-0030](../adr/ADR-0030-brain-handoff.md):

> the ~31B injection-harness run (`CORTEX_PROBE_BRAIN=1`), whose result feeds back into decision
> 1's tainted-escalation stance.

**Do.** There is **no runbook for this one.** The only instructions that exist are a comment in
[`test_injection_defense_live.py`](../../brain/packages/inference/tests/test_injection_defense_live.py):
"The ~31B brain (swap) tier is heavy; opt in with `CORTEX_PROBE_BRAIN=1` (needs ~13-18 GB free)."
The nearest procedure is the framing-efficacy probe in
[runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md), which is agent-runnable and never mentions
the flag. Writing the missing runbook section is part of this item.

**Pass.** The framed brain refuses the corpus the way the cortex does. The published number is the
result whatever it says; a published bad number is the point of the harness.

**Fail.** A brain tier that obeys injections under the shipped preamble. That is not a bug to fix
in the harness; it is evidence that the gated-escalation default should stay, which is exactly the
decision ADR-0030 flagged for maintainer review.

**Record it.** The [ADR-0004](../adr/ADR-0004-model-lineup.md) injection table, which today says
"the brain tier is opt-in and not yet run", plus a dated addendum to
[ADR-0013](../adr/ADR-0013-untrusted-content.md) and a note against ADR-0030 decision 1.

---

## 6. Real GPU-placed subagent validation

**Status: never attempted.** Independent of the pick.

Kept verbatim from [ADR-0012](../adr/ADR-0012-resource-governance.md):

> **What stays host-side is real GPU-placed-*subagent* validation**, for this ADR's own reason: a
> subagent is only ever placed on the GPU when `CORTEX_SUBAGENTS_VRAM_GB` fits under the soft cap
> minus the resident cortex, which needs a card that holds the cortex first. The measured `vram_gb`
> and budget numbers stay host-side with it.

and the consequence, from
[refinements/resource-governance.md](../refinements/resource-governance.md):

> Consequently the `VramBudgetPlacer`'s GPU arm has never fired against a real placement: with the
> shipped settings every spawn overflows to CPU.

**Do.** Set `CORTEX_MODEL_FILE_SUBAGENT_GPU`, `CORTEX_SUBAGENTS_GPU_ENDPOINT` and
`CORTEX_SWAP_EVICT_MODELS` together (the GPU compose override documents all three), then have the
cortex spawn subagents.

**Pass.** A spawn is placed on the GPU (`-ngl 99`) rather than spilling to CPU, and the placer's
ledger accounts for it against the soft cap.

**Fail.** Every spawn still overflowing to CPU with headroom available means the fit test is wrong,
which is a real finding: that arm has never run against a real placement.

**Record it.** A dated addendum to [ADR-0012](../adr/ADR-0012-resource-governance.md) and the note
in [refinements/resource-governance.md](../refinements/resource-governance.md) that points here.

---

## 7. The cgroup cap numbers

**Status: never attempted.** Best done alongside item 2, which is the only realistic load.

**What only this proves.** What leaves the machine usable. Kept verbatim from
[ADR-0012](../adr/ADR-0012-resource-governance.md):

> The values ship as user-tunable placeholders: the 8 GB dev GPU cannot hold a real tier pair, so
> what was validated is the mechanism and not the arithmetic. Note that llama.cpp mmaps the GGUF,
> so mapped model pages count against the memory cap and a cap below the artifact size makes a
> load thrash rather than fail.

**Do.** Tune `CORTEX_MODELHOST_CPUS`, `CORTEX_MODELHOST_MEMORY` and `CORTEX_MODELHOST_MEMSWAP` in
`docker/docker-compose.gpu.yml`, plus the CPU subagent container's set, against a real swap and the
user's own "is this machine still usable while gaming" bar.

**Pass.** Numbers that hold under item 2's load without thrashing.

**Fail.** A load that thrashes points at a memory cap below the artifact size, which is the
documented trap above and not a mystery.

**Know this going in.** There is no per-model cap. The cortex, the deep model and any GPU subagent
share one cgroup, because the model host runs them as children of one container; a per-model cap
would want a container per model, which would want a controller that can start containers, which
is the docker-socket shape ADR-0030 rejected on security grounds.

**Record it.** The compose file's own comment (which says the maintainer measures real numbers on the
24 GB machine), [modules/brain-model-manager.md](../modules/brain-model-manager.md) (which calls
them user-tunable placeholders), and an ADR-0012 addendum.

---

## 8. The resident VRAM figure with the projector loaded

**Status: never attempted.** Independent. **Filed here after being misfiled and then lost.**

**What only this proves.** The real cortex plus `mmproj` footprint against the 14 GB soft cap on
a 24 GB card. Kept verbatim from
[ADR-0029](../adr/ADR-0029-vision-screen-capture.md)'s Consequences, which is the only place it has
ever appeared:

> and the resident VRAM figure with the projector loaded on the 24 GB GPU.

That clause sits inside a list headed "Host-Windows (host only)" although it has no OS-native
content at all, and it was then dropped from the same ADR's own "Still host-only" closeout and
never reached [refinements/vision.md](../refinements/vision.md). It is a **G** item and it lives
here.

**Do.** Bring the cortex up with `--mmproj` under the model host and read `nvidia-smi`.

**Pass.** The measured figure is at or under ADR-0004's 11.3 GB reservation, which is already a
with-mmproj number, so the placer's arithmetic is unchanged.

**Fail.** A materially larger figure means the placer has been charging too little for the resident
cortex and every subagent headroom calculation shifts.

**Record it.** [runbooks/vision.md](../runbooks/vision.md) (whose "What the projector costs"
section states the reservation this checks), the
[runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md) table, and an ADR-0029 addendum.

---

## Also possible on this hardware, but not host work

Design work recorded in [refinements/](../refinements/index.md) that becomes *testable* here for
the first time: co-residency, the NPU feasibility pass, the spontaneous-pick nudge's live uptake,
and the model passes behind session-history summarization and the reranker. They stay in that
backlog with their code cost. See the last section of [index.md](index.md).
