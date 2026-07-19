# The 24 GB machine (tag G)

Seven items, one bring-up, one blocker. The first one gates four of the others, which is why this
is a single doc rather than seven: the dependency chain is the whole story on this side in a way
it is not on the Windows side.

Everything here is blocked on VRAM, not on an operating system. The dev GPU is an 8 GB card,
and [ADR-0030](../adr/ADR-0030-brain-handoff.md) measured `gemma-4-12b-it-qat-q4_0.gguf` alone
taking 7715 of its 8188 MiB, so the real cortex cannot be swapped against any deep-model
candidate, and no subagent can be GPU-placed beside a resident cortex. Kept verbatim from the
ROADMAP's Slice 11 status:

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

Derived from `docker/docker-compose.gpu.yml`, the `justfile`, and
`brain/packages/orchestrator/src/cortex_orchestrator/config_swap.py`, then run on the dev machine on
2026-07-19 as far as 8 GB allows. Follow it in this order; the earlier list here named two
settings that no compose file wires and omitted the one whose absence is a boot failure.

1. **Put the three escalation settings in the `brain` service's `environment:` block** of
   `docker/docker-compose.gpu.yml`, which is what that file's header instructs, or in a local
   override you layer after it. Nothing interpolates them, so a `.env` entry and an exported shell
   variable both leave the container without them and the stack comes up with escalation quietly
   off:

   ```yaml
   services:
     brain:
       environment:
         CORTEX_ESCALATION: "1"
         CORTEX_MODELHOST_BACKEND: "supervisor"
         CORTEX_BRAIN_ENDPOINT: "http://model-host:8081"
   ```

   All three or none. `config_swap.py` fails the brain at boot on escalation without a backend and
   on escalation without a brain endpoint, and the container then restarts forever rather than
   serving. `CORTEX_MODELHOST_ENDPOINT` is already set by the GPU override; do not add it.

2. **Name the deep artifact.** These are interpolated on `model-host`, so a repo-root `.env` or
   the calling shell carries them:

   ```
   CORTEX_MODELS_DIR=<the host dir holding the GGUFs>
   CORTEX_MODEL_FILE_BRAIN=<the pick's path under that dir>
   CORTEX_NGL_BRAIN=99
   CORTEX_CTX_SIZE_BRAIN=<the context the brain phase will use>
   ```

   A tier with no artifact file is not in the roster at all, so before item 1 lands a pick the
   deep model answers 404 and boot recovery logs one. That is a stock stack behaving as designed.

3. **Bring it up** with `just up-gpu`, which is `docker compose --project-directory . -f
   docker/docker-compose.yml -f docker/docker-compose.gpu.yml up -d --build`. If step 1 used a
   local override, run that command by hand with your `-f` last. `depends_on` holds the brain
   until the sidecar reports a tier that can serve a turn as READY.

4. **Ask the sidecar what it has.** Its control API is deliberately unpublished, so go through the
   container:

   ```
   docker compose --project-directory . -f docker/docker-compose.yml \
     -f docker/docker-compose.gpu.yml exec model-host \
     curl -s http://127.0.0.1:9300/health
   ```

   That lists the roster, and the deep tier appears in it only once step 2 named its file;
   `GET /models/<id>` gives one tier's state. When a live test needs the control API from the
   host, `just up-modelhost-loopback` layers `docker/docker-compose.modelhost-loopback.yml`, and
   `just down-gpu` takes it down again.

5. Read [runbooks/model-swap.md](../runbooks/model-swap.md) first, whose opening paragraph already
   states which of its numbers are the mechanism's and which are a tier's.

**What the dev machine could and could not reach (2026-07-19).** Steps 1 to 4 ran here on the 8 GB card with the models on the Windows drive, so the sequence is observed rather than reasoned about:
the stack came up, the cortex tier served (at `CORTEX_CTX_SIZE=4096`, because the shipped 16K
cortex is ADR-0004's 11.3 GB and this card has 8188 MiB), a brain with all three escalation
settings booted healthy, and the two live streaming tests in
`brain/packages/inference/tests/test_backend_live.py` passed against it through the real
`LlamaCppBackend`. Dropping `CORTEX_BRAIN_ENDPOINT` was confirmed to be a restart loop, and putting
the three settings in the shell instead of the compose file was confirmed to leave the container
with none of them. One thing to expect on the host box too: the rest of the
`just brain-inference-live` suite starts its own `llama-server` on `127.0.0.1:8080`, which the
sidecar already publishes, so those arms fail on the port rather than on the stack.

Where the dev machine stops is the tier itself, and not in the way the design predicted. Pointed at
`gemma-4-31B-it-qat-q4_0` (a 17 GB artifact) with the cortex evicted first, the deep tier did
**not** fail: llama.cpp logged `failed to fit params to free device memory: n_gpu_layers already
set by user to 99, abort`, kept every layer on the GPU anyway, reported READY after 373 s with
`nvidia-smi` pinned at about 7.7 of 8188 MiB, and then generated 16 tokens in 36 s, which is
roughly half a token per second and is what a WSL2 driver spilling into host RAM looks like. So a
card that cannot hold the tier gives a green swap and numbers that mean nothing, which is the trap
this sitting exists to avoid. Two consequences worth carrying in: no timing, VRAM figure, or
answer quality from an undersized card is a tier-scale result, and that 373 s load already exceeds
the shipped `CORTEX_SWAP_LOAD_TIMEOUT_S` default of 300 s, which is item 4's question.

## The dependency chain

```
1. deep-model pick  ──┬──> 2. tier-scale swap ──┬──> 3. chaos kill at scale
                      │                         └──> 4. measured timings
                      └──> 5. the ~31B injection-harness run

6. GPU subagent beside the cortex · 7. cgroup caps                            (independent)
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

**Fail.** A load that never completes inside `CORTEX_SWAP_LOAD_TIMEOUT_S` is item 4's problem,
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

**What only this proves.** ROADMAP assumption 2 at the brain tier, and whether the default of
`CORTEX_SWAP_LOAD_TIMEOUT_S` (300 s, the knob [runbooks/model-swap.md](../runbooks/model-swap.md)
lists beside the drain timeout) is right. Kept verbatim from that assumption:

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

## 6. A GPU-placed subagent beside a resident cortex

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

**The last clause of that reason is false, and this item is narrower for it (corrected
2026-07-19).** "Which needs a card that holds the cortex first" says the dev GPU does not hold the
cortex; [ADR-0029](../adr/ADR-0029-vision-screen-capture.md) measured it holding one at
`-ngl 99 --ctx-size 4096 --parallel 1` **with the vision projector loaded**, and
[ADR-0030](../adr/ADR-0030-brain-handoff.md) puts a number on how little that leaves: the model
alone takes 7715 of the card's 8188 MiB. Roughly 470 MiB is the remainder, so nothing multi-GB
fits beside it, which is the real reason and the one this item now carries. The **mechanism**, the
placer's GPU arm firing against a real placement at all, needs no resident cortex and is agent-side work listed as actionable now in
[refinements/index.md](../refinements/index.md). Expect it to have been run before this sitting, and
read a green mechanism as saying nothing about the arithmetic below, exactly as with the swap.

**What only this proves.** The fit test against real numbers: `CORTEX_SUBAGENTS_VRAM_GB` under the
soft cap minus a genuinely resident 12B cortex, on a card with room for both.

**Do.** With the cortex resident, set all three of these together. The GPU override's header
documents all three and wires one, so they do not go in one place:

- `CORTEX_MODEL_FILE_SUBAGENT_GPU` puts the tier in the sidecar's roster on `:8083`. Interpolated
  on `model-host`, so `.env` or the calling shell carries it.
- `CORTEX_SUBAGENTS_GPU_ENDPOINT=http://model-host:8083` routes GPU-placed spawns to it.
  Interpolated on the brain by `docker/docker-compose.subagents.yml`, so that override has to be
  layered too (`-f docker/docker-compose.subagents.yml`); without it both placement targets
  resolve to that file's CPU server and the tier serves nothing.
- `CORTEX_SWAP_EVICT_MODELS` names the tier so a handoff stops it first. Nothing interpolates it,
  so it goes in the `brain` service's `environment:` block beside the escalation settings.

Then have the cortex spawn subagents.

**Pass.** A spawn is placed on the GPU (`-ngl 99`) rather than spilling to CPU while the cortex
stays resident and serving, and the placer's ledger accounts for it against the soft cap.

**Fail.** Every spawn still overflowing to CPU with headroom available means the shipped
`CORTEX_SUBAGENTS_VRAM_GB` is above the real headroom, which is a numbers finding and the reason
these values are called placeholders. A spawn placed on the GPU that then degrades the cortex is the
more interesting failure and is an argument about the soft cap, not about the placer.

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

## Withdrawn: "the resident VRAM figure with the projector loaded, at production context"

This doc shipped on 2026-07-19 with an eighth item asking for the resident cortex plus `mmproj`
footprint on the 24 GB card at production context. **It was withdrawn the same day, because the
repo already has that measurement.** It is recorded here rather than deleted silently, since a
maintainer reading an older pointer to "item 8" deserves to find out why it is gone.

The item rested on the claim that its source clause in
[ADR-0029](../adr/ADR-0029-vision-screen-capture.md)'s Consequences, "and the resident VRAM figure
with the projector loaded on the 24 GB GPU", was the only place the figure had ever appeared. The
figure had appeared three times before that clause was ever read:

- [ADR-0004](../adr/ADR-0004-model-lineup.md)'s 2026-06-29 addendum, whose table row for
  `gemma-4-12B q4_0` reads `11.0 GB` weights only and `11.3 GB (mmproj 0.18 GB, +0.3)` with
  vision, measured on "the 24 GB card ... 16K context, single slot, all
  layers on GPU". That is this card, this context, and the deployment's own slot count: the model
  host gives the cortex tier `parallel=1` (`model_manager/config.py`).
- The [runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md) table, whose header says the numbers
  are "`nvidia-smi` total used with the model resident".
- [runbooks/vision.md](../runbooks/vision.md)'s "What the projector costs", which states that
  "ADR-0004's 11.3 GB cortex reservation is a **with-mmproj** measurement".

ADR-0029 itself says the same thing in its decision 14: "The 11.3 GB default is ADR-0004's
**with-mmproj** measurement, so enabling the projector spends budget the placer has been charging
since Slice 8.5 while the server ran text-only at 11.0 ... The only owed correction is
documentary." Nothing is owed the user here, and inventing a sitting for a number the repo
already holds costs more than leaving a gap would have.

---

## Also possible on this hardware, but not host work

Design work recorded in [refinements/](../refinements/index.md) that becomes *testable* here for
the first time: co-residency and the NPU feasibility pass. They stay in that backlog with their code
cost. See the last section of [index.md](index.md).

Three more used to be listed here, on the premise that no card the agent has can run the cortex:
the spontaneous-pick nudge's live uptake and the model passes behind session-history summarization
and the reranker. Corrected 2026-07-19, since the dev GPU does run the cortex at 4K. What this
hardware still adds to them is the production 16K context and more than one slot, which is a
sharper judgment rather than the only possible one.
