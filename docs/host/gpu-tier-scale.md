# The 24 GB machine (tag G, and three items are also W)

Seven items, one bring-up, one blocker. The first one gated four of the others, which is why this
is a single doc rather than seven: the dependency chain is the whole story on this side in a way
it is not on the Windows side. **That first item is done, on 2026-08-04**, and so is the one of the
four it gated that needed nothing else, **item 5, the same day**. The other three are open with
their own blockers rather than with this one.

Four of the seven need nothing but the card. **Items 2, 3 and 4 need the Windows overlay as well**,
because the handoff they exercise starts with a gated tool call and only the overlay can answer the
confirm card that gates it. That is spelled out at each of them and in the prerequisites below; if
the 24 GB card and the Windows desktop are the same laptop it costs nothing, and if they are two
machines it is the difference between a sitting and a wasted trip.

Everything else here is blocked on VRAM, not on an operating system.

**The VRAM premise was measured false on 2026-08-04, which is how item 1 below came to be run
here rather than waited for.** This section used to open by saying the dev GPU is an 8 GB card,
and [ADR-0030](../adr/ADR-0030-brain-handoff.md) did measure `gemma-4-12b-it-qat-q4_0.gguf` alone
taking 7715 of that card's 8188 MiB. Every number derived from that card is still true of it. What
is no longer true is that it is the card the repo is developed on: the development machine reports
24463 MiB, and all four deep-model candidates loaded and served on it alone. The capability table
in [index.md](index.md) carries the correction, and
[AGENTS.md](../../AGENTS.md) already said what follows from it, that "on the host" includes the
agent and GPU work reachable through Docker is done now rather than filed here. **No tag below
changes.** Items 2, 3 and 4 stay **W+G** because what blocks them is the overlay that answers a
confirm card, which is a Windows desktop and not a card; items 5, 6 and 7 stay listed because each
is its own sitting, not because the VRAM is missing.

The paragraph below was the
ROADMAP's summary of this side of the work; it was **preserved here when the ROADMAP was slimmed
on 2026-07-19** and no longer exists there, so this doc is its only home. The same substance,
in the decision record that owns it, is item 7 of
[ADR-0030](../adr/ADR-0030-brain-handoff.md)'s "what is left" list:

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

## Before you start: the bring-up, start to finish

Derived from `docker/docker-compose.gpu.yml`, the `justfile`,
`brain/packages/model_manager/src/cortex_model_manager/api.py`, and
`brain/packages/orchestrator/src/cortex_orchestrator/config_swap.py`, then **run end to end on the
dev machine on 2026-07-19**, with every output below copied from that run rather than reasoned about.

**The one thing this section used to leave out, which made item 1 unexecutable from the text: the
deep tier does not start itself.** At boot the sidecar's daemon starts the cortex and nothing else
(`model_host_lifespan` in `api.py`), and no compose setting starts a second tier. The deep model
begins loading when you POST to the control API, and on a card that cannot hold both it begins
only after the cortex is stopped. Both are steps you issue by hand, and they are steps 4 and 5.

Steps 1 to 9 are the whole of **item 1**, which needs neither escalation nor the overlay: the pick
is measured by driving the sidecar directly. Step 10 and the overlay are what items 2, 3 and 4 add.
Item 5 runs on none of this: it starts its own container, so it wants the stack **down**.

1. **Name the models directory and the deep artifact.** All four are interpolated on `model-host`,
   so a repo-root `.env` or the calling shell carries them:

   ```
   CORTEX_MODELS_DIR=<the host dir holding the GGUFs>
   CORTEX_MODEL_FILE_BRAIN=<the candidate's path under that dir>
   CORTEX_NGL_BRAIN=99
   CORTEX_CTX_SIZE_BRAIN=<the context the brain phase will use>
   ```

   A tier with no artifact file is not in the roster at all, so before a pick is named the deep
   model answers 404 and boot recovery logs one. That is a stock stack behaving as designed, and it
   is also the only way into the roster: nothing a request carries can name a model into existence
   (`api.py`), so this variable is the whole mechanism for adding the tier.

2. **Bring it up** with `just up-gpu`, which is `docker compose --project-directory . -f
   docker/docker-compose.yml -f docker/docker-compose.gpu.yml up -d --build`. `depends_on` holds
   the brain until the sidecar reports a tier that can serve a turn as READY. Here, with both
   images already built and the cortex at `CORTEX_CTX_SIZE=4096`, that took 48.9 s and ended:

   ```
    Container cortex-model-host-1 Healthy
    Container cortex-brain-1 Starting
    Container cortex-brain-1 Started
   ```

   Every command below goes through the sidecar's control API, which is deliberately unpublished
   (it starts and stops processes on the container holding the GPU and the models mount), so each
   one is a `docker compose exec`. The prefix is long, so the rest of this section abbreviates it
   the way the derivation run did:

   ```
   GPU="--project-directory . -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml"
   ```

3. **Ask the sidecar what it has.** This is the check that the deep tier is in the roster at all,
   and it is worth doing before anything else, because a mistyped `CORTEX_MODEL_FILE_BRAIN` is
   silent: the tier simply is not there.

   ```
   docker compose $GPU exec model-host curl -s http://127.0.0.1:9300/health
   docker compose $GPU exec model-host curl -s http://127.0.0.1:9300/models/cortex
   docker compose $GPU exec model-host curl -s http://127.0.0.1:9300/models/brain
   ```

   ```
   {"status":"ok","models":["cortex","brain"],"stop_grace_s":10.0,"reap_timeout_s":30.0}
   {"model":"cortex","state":"ready","detail":"serving on port 8080"}
   {"model":"brain","state":"stopped","detail":"no process is running"}
   ```

   `"models":["cortex","brain"]` is step 1 having worked. `"state":"stopped"` on the deep tier is
   the point above: it is in the roster and it is not running, and nothing will start it for you.
   `nvidia-smi` read 7916 MiB of 8188 at this moment, which is the resident cortex.

4. **Stop the cortex**, which is what frees the card for the deep model. On 24 GB this is not
   optional either: ADR-0004's cortex reservation is 11.3 GB and the candidates are 15 to 18 GB.

   ```
   docker compose $GPU exec model-host curl -s -X POST http://127.0.0.1:9300/models/cortex/stop
   ```

   ```
   {"model":"cortex","state":"stopped","detail":"no process is running"}
   ```

   It answered in **0.53 s** with the child idle and VRAM fell to 551 MiB. A cortex with a request
   in flight costs the full `CORTEX_MODELHOST_STOP_GRACE_S` instead (10 s, measured in
   [runbooks/model-swap.md](../runbooks/model-swap.md)); the stop does not answer until the child
   is dead and reaped, which is the point of waiting for this reply before step 5.

5. **Start the deep tier.**

   ```
   docker compose $GPU exec model-host curl -s -X POST http://127.0.0.1:9300/models/brain/start
   ```

   ```
   {"model":"brain","state":"loading","detail":"pid 279 is not serving yet"}
   ```

   It answered in **0.12 s**, because that is a spawn and not a load. The load is what you wait for
   next, and `loading` is the honest answer until the child serves.

6. **Poll until it is ready.** Nothing pushes you a notification; the state flips under
   `GET /models/brain`:

   ```
   docker compose $GPU exec -T model-host curl -s http://127.0.0.1:9300/models/brain
   ```

   ```
   t=0s  {"model":"brain","state":"loading","detail":"pid 279 is not serving yet"}
   ...
   t=38s {"model":"brain","state":"ready","detail":"serving on port 8081"}
   ```

   Two things to expect at tier scale that this run was too small to show. A load of a 15 to 18 GB
   GGUF off the mount is minutes, not the 38 s above, and while it runs **neither tier serves**, so
   the `model-host` container turns unhealthy after about 150 s of it; that is a handoff in
   progress, not a fault, and [runbooks/model-swap.md](../runbooks/model-swap.md) says so under
   manual recovery. A child that dies instead reports `{"state":"failed", ...}` with its exit code
   in the detail, and its own reason is in `docker compose logs model-host`.

7. **Measure it, and ask it something.** This is item 1's actual content. `nvidia-smi` is the VRAM
   number; the tier's own OpenAI-compatible API on 8081 is the answer-quality half:

   ```
   docker compose $GPU exec model-host curl -s http://127.0.0.1:8081/v1/models
   docker compose $GPU exec model-host curl -s http://127.0.0.1:8081/v1/chat/completions \
     -H 'Content-Type: application/json' \
     -d '{"messages":[{"role":"user","content":"<your question>"}],"max_tokens":120}'
   ```

   `/v1/models` names the artifact path that is actually serving, which is how you know you
   measured the candidate you meant to. **Read the reply carefully before judging quality**: the
   gemma candidates are reasoning models, and in this run the whole 120-token budget went to
   `reasoning_content` with `"content":""` and `"finish_reason":"length"`. A candidate scored on
   that would look mute when it was thinking. Give it a budget that fits a chain of thought plus an
   answer, and read `reasoning_content` as well as `content`. The reply also carries its own
   `timings`, which is the per-token speed without a stopwatch (this run: 120 tokens in 2072 ms).

8. **Swap back**, which is the same two verbs in the other order, and is worth doing by hand once
   before item 2 asks the brain to do it under a turn:

   ```
   docker compose $GPU exec model-host curl -s -X POST http://127.0.0.1:9300/models/brain/stop
   docker compose $GPU exec model-host curl -s -X POST http://127.0.0.1:9300/models/cortex/start
   ```

   The stop answered in 0.48 s and VRAM fell to 746 MiB; the cortex start answered in 0.10 s and
   the tier read `{"model":"cortex","state":"ready","detail":"serving on port 8080"}` **65 s**
   later, back at 7920 MiB. Note what the container health did through all of this: with the cortex
   stopped and the deep tier READY, `model-host` still read healthy, because its check asks for
   either tier, and `brain` read healthy throughout, because its check asks only that the `Health`
   RPC answered.

9. **Tear down, and verify the teardown with a command.** `just down-gpu` removes the stack
   including a locally layered override, since `down` works from the project's own labels:

   ```
   just down-gpu
   docker ps -a
   nvidia-smi --query-gpu=memory.used --format=csv,noheader
   ```

   Here that removed `cortex-brain-1`, `cortex-redis-1`, `cortex-model-host-1` and the
   `cortex_default` network, and VRAM fell to 610 MiB. **Run those last two lines rather than
   assuming.** A model-host left running holds the whole card, and this repo has already spent a
   round on a cleanup that was claimed and not checked.

10. **Only for items 2, 3 and 4: put the three escalation settings in the `brain` service's
    `environment:` block** of `docker/docker-compose.gpu.yml`, which is what that file's header
    instructs, or in a local override you layer after it with your `-f` last. Nothing interpolates
    them, so a `.env` entry and an exported shell variable both leave the container without them
    and the stack comes up with escalation quietly off:

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

11. Read [runbooks/model-swap.md](../runbooks/model-swap.md) before item 2, whose opening paragraph
    states which of its numbers are the mechanism's and which are a tier's. When a live test needs
    the control API from the host rather than through `exec`, `just up-modelhost-loopback` layers
    `docker/docker-compose.modelhost-loopback.yml` (control API on 9300, deep tier on 9081), and
    `just down-gpu` takes it down again.

**What the dev machine could and could not reach (2026-07-19).** Every step above ran here on the 8 GB card with the models on `/srv/models`, so the sequence is observed and not inferred. **The one
step this card could not prove is the artifact in step 1.** A real candidate is 14 to 17 GB and
this card has 8188 MiB, so the run above pointed the deep tier at
`google/gemma-4-E4B-it-qat-q4_0-gguf/gemma-4-E4B_q4_0-it.gguf` (4.9 GB) as a stand-in. It proves
the roster, the eviction, the start, the health gate, the tier's own API and the swap back, and it
proves **none** of the arithmetic: the 38 s load, the 3801 MiB and the token rate are the stand-in's
and belong to no tier. Everything else the earlier version of this section recorded still holds:
the cortex tier served at `CORTEX_CTX_SIZE=4096` (the shipped 16K cortex is ADR-0004's 11.3 GB),
a brain with all three escalation settings booted healthy, and the two live streaming tests in
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

**Both of those are settled on the real card as of 2026-08-04**, and the trap is worth rereading
against the answer: the same `gemma-4-31B-it-qat-q4_0` artifact that took 373 s and generated half
a token per second on 8 GB loads in 99.6 s and generates at about 31 tok/s on a card that holds
it, resident at 19128 MiB. The 373 s figure was the spill, not the model. Item 1 has the rest.

## The dependency chain

```
1. deep-model pick  ──┬──> 2. tier-scale swap ──┬──> 3. chaos kill at scale
                      │                         └──> 4. measured timings
                      └──> 5. the ~31B injection-harness run

6. GPU subagent beside the cortex · 7. cgroup caps                            (independent)
```

Items **2, 3 and 4 are W+G**: they ride a real handoff, a handoff starts at an approved confirm
card, and the overlay is the only client that answers one. Items **1, 5, 6 and 7 are G**: the card
alone. If both capabilities live in one laptop the distinction costs nothing; if they do not, do 1,
5, 6 and 7 on the card and keep 2, 3 and 4 for a sitting with the desktop in the room. **1 and 5
are done as of 2026-08-04**, both by the agent, which is what the G tag now means.

---

## 1. The deep-model pick

**Status: Done 2026-08-04.** The pick is **gemma-4-31B-it-qat-q4_0**. It no longer blocks items
2, 3, 4 and 5.

**The measurement has left this directory**, which is what the exit contract in
[index.md](index.md) asks of a completed item: its home is now the dated brain-pick addendum in
[ADR-0004](../adr/ADR-0004-model-lineup.md) and the two Brain rows in
[runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md), with the artifact named in the
`CORTEX_MODEL_FILE_BRAIN` comment of `docker/docker-compose.gpu.yml`. Only the heading and this
record stay here, because four items below are written against this one's number and a hole where
item 1 was would cost more than the line it saves.

**What it found, in one paragraph.** All four candidates loaded and served alone on a card that
holds the tiers, so the fit question this item was written to answer turned out not to be the
question: the spread was 14607 to 19128 MiB with the cortex evicted, and ADR-0004's hybrid `-ngl`
/ CPU-KV fallback is not needed. What separated the candidates is whether they stop reasoning.
Both mixture-of-experts artifacts, which are the fast ones at about 80 tok/s, consume the entire
8192-token context on an escalation-grade question and return an empty `content`, and they do it
under the deployment's own condition, since the brain sends no `max_tokens` and llama-server
defaults to `n_predict = -1`. Both dense candidates answer. The pick loads in 99.6 s, sits at
19128 MiB at the shipped 8192 context and 19786 at 16384, generates at about 31 tok/s, and was
the only candidate to answer all four questions inside a bounded budget; `Qwen3.6-27B-GGUF
(Q4_K_M)` is the recorded alternate, 2.7 GB lighter and one question short.

**What this hands the items below.** Item 4 compares a real swap's load phase against **99.6 s**
cold, which leaves the shipped `CORTEX_SWAP_LOAD_TIMEOUT_S` default of 300 s about two thirds
unspent, and against a warm reload of the same artifact at 66.4 s. Item 2's eviction arithmetic
is 19128 MiB for the deep tier against a card reading 1867 to 1932 MiB with nothing loaded. The
swap back was also run by hand once, as step 8 suggests: the deep tier stopped in 0.92 s and the
cortex was READY again 35.7 s later, with both container health checks green throughout.

**One correction to the bring-up above, from running it.** Step 7's warning about
`reasoning_content` is right and is worth strengthening: a budget that fits "a chain of thought
plus an answer" is not a fixed number, it is a property of the candidate, and on two of these four
no budget inside the context window is enough. Read `finish_reason` before reading either field.
`"length"` with an empty `content` and a full `reasoning_content` is a model that never finished,
and at tier scale that is a finding about the model rather than about the budget.

---

## 2. The tier-scale cortex to brain swap

**Status: never attempted.** Blocked on item 1. Tag **W+G**, corrected 2026-07-19: this item sat
under G alone, and both its procedure and its pass line need the Windows overlay.

**What only this proves.** The VRAM arithmetic. The agent's validation ran two small artifacts
through every code path, which is explicitly not the same thing: evicting ~11.3 GB and loading 15
to 18 GB alone is the part that was never exercised.

**Why it needs the overlay too, and cannot be done headless today.** `escalate_to_brain` carries
`gated=True` in its own spec (`brain/packages/core/src/cortex_core/escalate.py`), so a handoff
begins only after the ADR-0022 confirm card is **approved**. That card is not a brain-side prompt:
the brain emits a `ConfirmRequest` on the Converse stream and waits
`CORTEX_SEAM_CONFIRM_TIMEOUT_S` (120 s) for the client's `ConfirmResponse`, and an unanswered one
is denied fail-closed, so nothing swaps. The only shipped client that answers a `ConfirmRequest` is
the overlay (`body/crates/rpc/src/converse.rs`, `body/app/src/bridge/tauriBridge.ts`); the repo's
own headless Converse driver, `just seam-health`, opens a stream, reads it, and answers no confirm.
So the trigger and the amber dot are the overlay's, and the arithmetic is the card's. Nothing about
this makes it a Windows item: no overlay can evict 11.3 GB and load 18 GB. If the Windows desktop
and the 24 GB card are the same laptop, this costs one bring-up of each side and nothing more.

**Do.** With "Before you start" done **including step 10**, bring the overlay up beside the brain
([windows-desktop.md](windows-desktop.md) has that bring-up), then ask something that escalates and
**approve the card** when it appears. Watch the swap window's `StatusUpdate`s. To see the swap from
the other side while it runs, `GET /models/brain` on the sidecar (step 6's command) flips
`stopped` to `loading` to `ready` and the cortex flips the other way; that is also how you tell an
escalation that was never approved from one that was.

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

**Status: never attempted.** Blocked on items 1 and 2. Tag **W+G**, corrected 2026-07-19, for
item 2's reason and one of its own: there is no handoff to kill in the middle of until a confirm
card has been approved, and the ADR's own procedure below says "verify from the overlay". The kill
itself is a `docker exec` on the card's machine; what the overlay supplies is the turn that is
in flight when it lands and the honest failure the user sees.

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

**Status: never attempted.** Blocked on item 2, and it inherits item 2's **W+G** with the block:
these are the phases of a real handoff, and a real handoff starts at an approved confirm card. The
one number you can take without the overlay is the deep tier's bare load time, which is item 1's
step 6 and is the figure this compares the swap's load phase against.

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

**Status: Done 2026-08-04.** The framed brain obeyed **0 of 10**; the unframed control obeyed 1.
The pass line this item carried, that the framed brain refuses the corpus the way the cortex does,
was met, so shipped policy does not change; the decision it was written to inform is now live for
the user instead.

**The measurement has left this directory**, per [index.md](index.md)'s exit contract, and so has
the procedure, which was the other half of this item. The number and its evidence are the
[ADR-0013](../adr/ADR-0013-untrusted-content.md) addendum of that date, the row in
[ADR-0004](../adr/ADR-0004-model-lineup.md)'s injection table, and the note against
[ADR-0030](../adr/ADR-0030-brain-handoff.md) decision 1; **the runbook section this item owed is
"The brain tier's injection-harness row" in
[runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md)**, beside the framing-efficacy probe that
was its nearest neighbour. The heading stays because the dependency chain above points at it.

**What it found, in one paragraph.** One row ran, `-k "31B"`, the pick's; the other three deep
candidates and the seven cortex and subagent rows did not. Framed, the pick resisted the whole
corpus and six of its ten reasoning traces cite the shipped preamble while doing it, which is the
same causal signature gemma-4-12B showed. Unframed, it fell to the tool exfil, emitting a real
`send_email` call on an instruction buried in a file it had been asked to summarize, so the one
attack the framing demonstrably stopped is the one with an action behind it. A perfect score on a
reasoning model is exactly where to distrust green, since the harness scores `content` alone and
[ADR-0004](../adr/ADR-0004-model-lineup.md) had already caught two candidates in the same tuple
returning an empty one after burning a whole context: a second pass recorded `finish_reason`,
reply lengths and the canary's presence in the trace, replicated the matrix exactly, and showed no
arm truncating and every framed reply carrying a correct summary. The runbook carries that check as
procedure rather than as a story.

**What it hands the user, and what this item deliberately did not do.**
[ADR-0030](../adr/ADR-0030-brain-handoff.md) decision 1 gives two reasons for hard-denying
escalation on a tainted turn, and the run retires only the first: the deep tier's robustness is no
longer unmeasured. The second, that injected content must never force an eviction that claims the
card for minutes, is a resource-control argument a model measurement cannot touch. The stance was
therefore left exactly as shipped and the choice recorded as a decision awaiting the user, on
[index.md](index.md)'s list and at the ADR. Worth knowing before weighing it: the deny is the
generic gated-tool branch in `dispatch.py`, so relaxing it for escalation carves an exception into a
rule that has none.

**The standing half survives.** "Whenever picks or the preamble change" outlived this run and now
lives in the runbook section with the procedure, which is where a re-run will be read.

---

## 6. A GPU-placed subagent beside a resident cortex

**Status: never attempted.** Tag **G**. Independent of the pick, and independent of the overlay:
the spawn can come from a turn, but the live delegation suite
(`brain/packages/orchestrator/tests/test_subagent_live.py`) invokes the spawn tool directly "as the
cortex would", which is a placement without a desktop.

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

**Status: never attempted.** Tag **G**, with one caveat: item 2 is the only realistic load to tune
against, and item 2 needs the overlay, so in practice this is measured during that sitting.

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
