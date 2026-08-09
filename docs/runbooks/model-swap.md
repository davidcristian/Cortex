# Runbook: model swap (brain handoff)

What to do when a handoff leaves the GPU in a state you have to fix by hand. Design and
rationale: [ADR-0030](../adr/ADR-0030-brain-handoff.md). Ops loop and the compose basics:
[local-dev-wsl.md](local-dev-wsl.md); the cortex `llama-server` itself:
[llamacpp-gpu.md](llamacpp-gpu.md).

**Scope today.** Two model hosts can be wired (`CORTEX_MODELHOST_BACKEND`, `swap_builders.py`):
the **scripted** one, which tracks residency and readiness honestly so the whole path runs end to
end but **starts no process and moves no weights**, and the **supervisor** one, the real
`HttpModelHost` over the `model-host` sidecar's control API. The sidecar's own contract is
[brain-model-manager.md](../modules/brain-model-manager.md).

The swap **mechanism** is validated: real `llama-server` processes started, health-gated, killed,
and swapped, on an 8 GB card with two small artifacts standing in for the tiers, with the timings
and the exact commands in "The mechanism, as measured" below. **Read every number below as the
mechanism's, never as a tier's:** gemma-4-12B alone takes 7715 of that card's 8188 MiB, so the
real cortex and any deep-model candidate cannot be swapped between on 8 GB, and every figure in
this file was taken with stand-ins.

**Two pieces of the tier-scale half have since been measured on a card that holds the tiers**, and
both live in [docs/host/gpu-tier-scale.md](../host/gpu-tier-scale.md): the deep-model pick, which
landed 2026-08-04 as gemma-4-31B QAT q4_0 at 19128 MiB alone and 99.6 s from start to READY
(ADR-0004's brain-pick addendum), and one cortex to deep to cortex cycle driven by hand against
the control API. What this runbook still owes is that cycle under a real escalated turn, which
begins at a confirm card only the overlay answers, and the timings of its phases.

## Is the capability even on?

Escalation is **off by default**. It is on only when `CORTEX_ESCALATION` is set, and then the
deployment must also set `CORTEX_MODELHOST_BACKEND` (`scripted`, or `supervisor` with a
`CORTEX_MODELHOST_ENDPOINT`) and
`CORTEX_BRAIN_ENDPOINT`, or the brain refuses to boot (`config_swap.py`). **None of those three is
interpolated by any compose file**, so a `.env` entry or an exported shell variable does not reach
the brain container and the stack comes up with escalation quietly off (verified against a running
container 2026-07-19): they go in the `brain` service's `environment:` block in
`docker/docker-compose.gpu.yml`, or in a local override layered after it. With escalation off,
nothing below can happen: no `escalate_to_brain` tool, no conductor, no boot recovery. The
`model-host` sidecar itself is not gated by that switch: it comes up with the GPU override either
way, serving the cortex as the always-on `llama-cortex` service used to.

Other knobs: `CORTEX_MODEL_BRAIN` (the deep tier's logical id, default `brain`),
`CORTEX_SWAP_EVICT_MODELS` (further hosted tiers a swap stops first, comma separated),
`CORTEX_SWAP_BRAIN_VRAM_MIB` (0, the deep tier's measured VRAM cost, see below),
`CORTEX_SWAP_DRAIN_TIMEOUT_S` (60 s), `CORTEX_SWAP_LOAD_TIMEOUT_S` (300 s),
`CORTEX_MODELHOST_TIMEOUT_S` (60 s, one control call's deadline). On the sidecar,
`CORTEX_MODELHOST_NVIDIA_SMI` (`nvidia-smi`) names the binary it reads the card with.

**`CORTEX_SWAP_CORESIDENT` is the one knob that changes what a handoff does to the machine, and
it is off.** Set it and a swap stops the cortex and nothing else, every `CORTEX_SWAP_EVICT_MODELS`
tier keeps serving beside the deep model, and the subagent pool is never quiesced, so delegated
work runs through the handoff and the deep phase may spawn. Nothing else changes, and the swap
back still starts every listed tier, which is a no-op against one that never stopped and a heal
for one that died on its own.

**Setting it also requires `CORTEX_SWAP_BRAIN_VRAM_MIB`, and the brain refuses to boot without
it.** That figure is how much free device memory the deep tier needs, measured on your own card
(the procedure is the co-residency section below; on this stack's card it is 19125 MiB). The
sidecar reports what the card has free on `GET /health`, and a swap reads it **after the
evictions and before the load**, which is the only instant the number means anything. Short of
the figure, the handoff is refused with both numbers in the log and in the reply's note, the deep
model is never started, and the standing residency is put back. A model host that can see no card
at all refuses the same way, because a deployment that asked to be checked and cannot be must not
run unchecked. Set the figure generously if the machine shares its card with a desktop: this one's
idle floor moves by about a gigabyte, and the check cannot see memory taken **during** a load that
runs for a minute or more. What the check still cannot tell you is whether the figure itself is
right, or whether a load spilled anyway; for that, measure decode, exactly as below.

The same figure is honoured with co-residency off, where it is optional: it then guards the
ordinary handoff on a card too small for the deep tier at all.

**One pairing to keep, and the brain now refuses to start when you break it.** The sidecar's
`stop` answers only once the child is dead and reaped, so it can legitimately take
`CORTEX_MODELHOST_STOP_GRACE_S` (10 s) plus `CORTEX_MODELHOST_REAP_TIMEOUT_S` (30 s) before
replying, **plus** `CORTEX_MODELHOST_PROBE_TIMEOUT_S` (5 s) when a `status` got the tier's lock
first: `status` holds the same per-model lock as `stop` and probes the child's `/health` inside it,
and the compose healthcheck asks for a status every 30 s, so a queued one is the normal case, not a
corner. So the rule is

    probe_timeout_s + stop_grace_s + reap_timeout_s  <  CORTEX_MODELHOST_TIMEOUT_S

which the shipped defaults satisfy (5 + 10 + 30 = 45 < 60). Measured against a SIGSTOPped child on
the shipped grace: a stop whose lock was free took **10.89 s**, and the same stop issued 0.2 s
behind a `GET /models/cortex` took **15.70 s**, that status itself taking **5.80 s**, which is the
probe timeout plus its request overhead. Both stops ended correctly (`stopped`, no `llama-server`
left). Tuning by the grace and the reap alone (say 20 and 35, a compliant sum of 55) reaches 60 s,
the control client times out, and the handoff aborts although the eviction was working.

`GET /health` reports all three bounds the daemon actually got, and the brain reads them once at
boot: if `CORTEX_MODELHOST_TIMEOUT_S` does not sit strictly above their sum, the brain **refuses to
serve** and says so in one line naming every term, so a mispaired stack fails at `docker compose
up` instead of inside somebody's handoff:

```
CORTEX_MODELHOST_TIMEOUT_S is 60.0 s and the model host's worst stop is 60.0 s (probe 5.0 s,
grace 20.0 s, reap 35.0 s), so a control call would time out on an eviction that was still
working and abort the handoff that asked for it. Raise the brain's deadline above that sum, or
lower the sidecar's own bounds
```

Raise `CORTEX_MODELHOST_TIMEOUT_S`, or lower whichever sidecar bound you had raised, and bring the
stack up again. Two cases deliberately do **not** refuse: a `model-host` that is not answering yet
(logged at warning, and the brain serves, because a sidecar that is merely down comes back on its
own under the restart policy), and the `scripted` backend, which stops no process and so has no
bounds to report.

## Bringing the real host up

```
CORTEX_MODELS_DIR=/srv/models just up-gpu
```

That is the whole thing: the GPU override runs `model-host` instead of `llama-cortex`, and the
brain waits on its healthcheck, which asserts that **a tier that can serve a turn is READY** (the
cortex tier, or the deep one) rather than merely that the daemon answers. At cold boot the daemon
starts only the cortex, so what `depends_on` waits for is the cortex serving, exactly as it was
with `llama-cortex`. Ask it what it is doing from inside the network:

```
docker compose --project-directory . -f docker/docker-compose.yml \
  -f docker/docker-compose.gpu.yml exec model-host \
  curl -s http://127.0.0.1:9300/health
```

The control API is deliberately **not published** to the host: it can start and stop processes on
the container holding the GPU and the models mount, and on WSL2 a `127.0.0.1` publish is reachable
from Windows' own localhost too. Layer `docker/docker-compose.modelhost-loopback.yml` when a
host-side live test needs it (control API on 9300, deep tier on 9081, GPU subagent on 9083), and
take it down after. The cortex tier's own `127.0.0.1:8080` stays published exactly as the old
service published it, so `just brain-inference-live` and
[llamacpp-gpu.md](llamacpp-gpu.md) are unchanged.

To give the deployment a deep tier, name its artifact in the `model-host` environment
(`CORTEX_MODEL_FILE_BRAIN`, with `CORTEX_NGL_BRAIN` / `CORTEX_CTX_SIZE_BRAIN` to fit it) and set
`CORTEX_ESCALATION=1`, `CORTEX_MODELHOST_BACKEND=supervisor`,
`CORTEX_BRAIN_ENDPOINT=http://model-host:8081` on the brain. **A tier with no artifact file is not
in the roster at all**, so a stock stack answers 404 for the deep model rather than spawning a
doomed process, and `GET /health` lists exactly the tiers it can run.

## The mechanism, as measured

Agent-validated 2026-07-18 on the dev GPU (8 GB card, 8188 MiB, driver 610.74, 2516 MiB
used at rest), with two small artifacts standing in for the tiers: the cortex tier pointed at
`Qwen3.5-0.8B-Q8_0.gguf` and the deep tier at `Qwen3.5-2B-Q4_K_M.gguf`, both at `--ctx-size 4096`.
Every number is one observation on this card, not a benchmark.

| Step | Command | Observed |
|---|---|---|
| boot | `up -d model-host` | control API answering at once; cortex child spawned, `{"state":"loading","detail":"pid 9 is not serving yet"}`; compose healthcheck went `healthy` when it turned ready |
| resident | `GET /models/cortex` | `{"state":"ready","detail":"serving on port 8080"}`; `/v1/models` on 8080 named the 0.8B path; VRAM 3501 MiB (about 985 MiB for the model) |
| evict, idle child | `POST /models/cortex/stop` | answered in **0.40 s**; no `llama-server` in `ps`; 8080 refused connections; VRAM back to **2513 MiB** |
| evict, child mid answer | `POST /models/cortex/stop` with a stream in flight | answered in **10.09 s** (**10.90 s** in a second run): llama-server logged `cleaning up before exit` and then did **not** exit, so the full `CORTEX_MODELHOST_STOP_GRACE_S` (10 s) was paid, it was SIGKILLed, and the reap plus the HTTP round trip account for the rest. The shipped tiers run `--parallel 1`, so one in-flight request blocks the graceful exit. This is the eviction cost to plan for, not the idle number |
| load | `POST /models/brain/start` | answered in **0.007 s**, which is a spawn and not a load; `loading` immediately after |
| health gate | poll `GET /models/brain` | `ready` **18.0 s** after the start; `/v1/models` on 8081 named the 2B path; exactly one `llama-server` in `ps`; cortex still `stopped`; VRAM 3952 MiB |
| swap back | `POST /models/brain/stop` then `POST /models/cortex/start` | stop answered in **0.10 s** with the child idle; cortex `ready` **11.3 s** later, serving the 0.8B path again; deep tier `stopped` |
| the scope | `SwappingModelManager.swap_scope(deep)` over the real adapter (`just brain-modelhost-live`) | inside the scope the deep tier was READY and the standing one STOPPED, and the endpoint the lease handed out was the deep tier's; after it, the reverse. Deleting the eviction from `swap_in` reddens it with both tiers READY at once |
| what the seam would say | `manager.residency()` read at those same instants | "a deep task is in progress" inside the scope, the serving report before and after, checked against the sidecar's own reads rather than beside them. A report that always claims serving reddens it |
| the brain's own healthcheck | `docker inspect cortex-brain-1` after the predicate change | **healthy**; the same command against a port with no server exits 1, so the check still catches the broken gRPC server it exists for |
| end to end | one `Converse` turn through the brain container | `Health` ready, `text_delta`s, `turn_complete`; the reply came off the supervised child over `http://model-host:8080` |

**Do not run the tier-scale swap on an undersized card to "see if it works": it will say yes.**
Measured 2026-07-19 on the same dev GPU, with the cortex evicted first and the deep tier pointed
at a 17 GB `gemma-4-31B-it-qat-q4_0` artifact, llama.cpp logged `failed to fit params to free
device memory: n_gpu_layers already set by user to 99, abort`, kept every layer assigned to the
GPU, reached `ready` after **373 s** with `nvidia-smi` pinned at about 7.7 of the card's 8188 MiB,
and then served 16 tokens in 36 s (roughly half a token per second), which is what the WSL2 driver
spilling into host RAM costs. Nothing failed, so nothing warns you: the swap, the health gate and
the stream all behave, and every timing and VRAM number from such a run is meaningless. Tier scale
is a host measurement on a card that holds the tier
([docs/host/gpu-tier-scale.md](../host/gpu-tier-scale.md)).

Tier scale will be minutes rather than seconds on both halves: an 18 GB GGUF off the model mount at
the measured mount read rate is what `CORTEX_SWAP_LOAD_TIMEOUT_S` (300 s) exists for. The eviction
half is sub-second only while the child is **idle**; every path that evicts a tier which was
answering (the cancellation restore, and the shutdown sweep) pays the whole grace per busy tier,
which is what `stop_grace_period: 45s` on the container is sized for (3 tiers x 10 s plus slack,
the sweep being sequential).

## Co-residency, and how to tell a fit from a spill

Measured 2026-08-07 by the agent on a 24 GB card (RTX 5090 Laptop, 24463 MiB, driver 610.88,
llama.cpp build `b10236-1464c62d8`), through this same control API with the **real** tiers rather
than stand-ins. Read the floor first and subtract it: this machine's idle reading moved between
**1529 and 2836 MiB** inside one session, because Windows' own desktop shares the card, so about a
gigabyte of the budget is not yours to plan with.

| Configuration | `nvidia-smi` used | Free | Deep decode | Verdict |
|---|---|---|---|---|
| cortex alone, 16K, projector, 1024-token image budget | 11284 to 11298 MiB | | | 8448 to 8468 MiB above floor |
| deep alone (gemma-4-31B q4_0, 8K, `-ngl 99`) | 20671 to 20723 MiB | ~3.8 GB | 25.07 to 33.28 tok/s | 19117 to 19125 MiB above floor |
| **cortex + deep** | 23539 to 23642 MiB | ~0.5 GB | **14.80 to 17.29 tok/s** | **spilled**, 4676 MiB short |
| **deep + gemma-4-E4B subagent tier** | 23555 to 23642 MiB | ~0.9 GB | **28.92 to 29.82 tok/s** | **fits**, peer costs 2878 MiB |

**The two bottom rows read the same on `nvidia-smi` and are opposite results.** That is the whole
warning. A card 4676 MiB short does not refuse the second load: both tiers report `ready`, the
stream works, and the WSL2 driver quietly pages about 6 GB to system memory. The tell is decode
rate, roughly halved, plus a prefill that collapses to 13.8 tok/s on the first request after each
switch where a fitting pair holds 105 to 134. So **measure `predicted_per_second` from
llama.cpp's own `timings`, on each tier, before and after**, and treat a memory reading alone as no
evidence either way. The brain reads decode itself since 2026-08-08 (the spill watch below);
prefill it still does not, so that half of this stays a hand measurement. It is the same lesson the 8 GB warning above teaches at a different scale, and
it survives having enough card to be fooled by.

What co-residency buys, on the same run and the same control API, with the artifact warm in the
page cache: `stop(cortex)` **0.48 s**, deep tier `ready` **70.03 s** later, `stop(brain)`
**0.89 s**, cortex `ready` **31.43 s** later, so **102.9 s** of swap either side of the deep phase
(about 132 s cold, at ADR-0004's 99.6 s load). Without the flag every spawn is refused for all of
it and for the deep phase too. With it, delegated work never stops. Generating on both tiers at
once costs both (deep 18.74 tok/s, peer 22.91) and allocates nothing: 23639 MiB under load against
23642 MiB idle, which is why a spawn onto an already-resident tier is not a VRAM decision.

To reproduce, layer `docker/docker-compose.modelhost-loopback.yml`, name all three artifacts, and
drive `POST /models/{id}/start` by hand with the cortex stopped first. The live suite has it as
`test_a_coresident_scope_leaves_its_peer_serving_beside_the_deep_model`
(`just brain-modelhost-live`), which skips unless the sidecar hosts all three tiers.

### The fit check, and what it is worth

Since 2026-08-07 the sidecar answers `curl -s http://127.0.0.1:9300/health` with
`device_free_mib` and `device_total_mib` beside the roster and the three timing bounds, read with
`nvidia-smi` inside the container that holds the GPU reservation, and a swap compares
`CORTEX_SWAP_BRAIN_VRAM_MIB` against the free figure between its last eviction and its load.
Measured on this card the same day, with the cortex resident and the desktop quiet:

| What was resident | `/health` free | Declared need | Outcome |
|---|---|---|---|
| cortex (text only) | 14905 MiB of 24463 | 19125 MiB | **refused in 0.03 s**, nothing started |
| nothing (cortex evicted, as a handoff evicts it) | about 22.8 GB | 19125 MiB | loaded, `ready` in 69.24 s, 3579 MiB left free |

The sidecar's figure matched the host's own `nvidia-smi` exactly (14905 of 24463 on both sides),
which is the check worth running first if a refusal ever looks wrong.

**A handoff also changes what the subagent placer will admit, from the same declared figure.**
Since 2026-08-07 the residency scope charges `CORTEX_SWAP_BRAIN_VRAM_MIB` against
`CORTEX_VRAM_SOFT_CAP_GB` for the length of a handoff, in place of `CORTEX_VRAM_CORTEX_GB`, so a
GPU-placed spawn during a co-resident handoff is fit-tested against the card as it actually is.
On this card, with the cap raised to 23 GiB, that is 4.32 GiB of headroom during the window against
14.4 GiB outside it. At the **shipped** 14 GB cap the same window leaves nothing at all, the deep
tier's 18.68 GiB being over the whole budget, so the measured 3.5 GiB subagent ask is GPU-placed
outside a handoff, overflows to the CPU server while the deep model is resident, and is GPU-placed
again once the cortex is back. Both readings say the same thing; the raised cap is what a
deployment sizing the budget to this card would use, and the shipped one is what ships. The operator-visible effects:
delegated work through a co-resident handoff may be slower than the same work outside one, and a
restore that gave up (`could not restore the cortex after a model swap`) keeps every spawn on the
CPU until the process is restarted, deliberately, because nothing then knows what is on the card.
With `CORTEX_SWAP_BRAIN_VRAM_MIB` unset there is no charge and the placer behaves as it always did.

**Read the refusal as "there was not room", never the pass as "it fitted".** The check is blind
to a figure declared too low, and blind to memory taken while a load runs, and both of those end
in the silent spill above: two tiers reporting `ready`, `nvidia-smi` reading like a fit, and the
deep model decoding at half its rate. When a co-resident deep phase feels slow, do not read
memory. Read `timings.predicted_per_second` off a completion on each tier and compare it against
the solo rates in the table above.

### The spill watch, which now runs that reading for you

Since 2026-08-08 the brain does that comparison itself
([ADR-0030](../adr/ADR-0030-brain-handoff.md) spill-watch addendum). `LlamaCppBackend` surfaces the
server's `timings.predicted_per_second` as a `DecodeCadence` on every completion, and a deep phase
compares the **best** completion of the whole handoff against `CORTEX_SWAP_BRAIN_DECODE_TPS`, the
tokens per second you measured for that tier on this card. Set it from a **cold** load of the tier
alone, and set it as a floor rather than a target: a rate a healthy tier clears comfortably, not
the number it peaks at.

- Under the floor, once per handoff, at WARNING: *the deep model decoded below the rate this
  deployment measured for it, which is what an overcommitted card looks like*, with
  `tokens_per_second`, `floor_tokens_per_second`, `shortfall`, `tokens`, `samples` and `judged` on
  the record. That is your signal, and it is the only one there is.
- At or above it, at INFO, with the same numbers. Worth having: the healthy figure is what makes a
  later warning readable, and it is what you would set the next floor from.
- With `CORTEX_SWAP_BRAIN_DECODE_TPS` unset, the same INFO line and no verdict at all, which is
  what an unmeasured deployment gets rather than a boot failure.
- No reading at all also logs at INFO and **is not a pass**: a completion under 32 decoded tokens
  is not judged, and a phase that failed before decoding anything reports nothing.

It watches only the deep phase, since only a handoff changes what is on the card, and it never
touches the turn: the reply has already streamed by the time the rate is known, so refusing would
spend a user's answer on an operator's problem.

**Measured on this card 2026-08-08**, through the shipped adapter and watch, three completions of
about 120 words an arm. The last two rows are reproducible with
`packages/inference/tests/test_decode_cadence_live.py` (integration-marked; start or stop the peer
through the control API to choose the arm). The cold row is not: it came from a script driving the
same adapter and watch, so reproducing it means arranging a clear card yourself:

| Arm | free after | decode | best | at a declared 25.0 |
|---|---|---|---|---|
| deep alone, cold onto a clear card | 2310 MiB | 31.08, 31.85, 33.78 | 33.78 | not collapsed |
| **cortex resident, then deep** | **423 MiB** | **21.64, 20.38, 22.77** | **22.77** | **collapsed**, 2.23 short |
| deep alone, peer evicted under it | 8649 MiB | 28.32, 29.82, 29.38 | 29.82 | not collapsed |

Every tier an arm had resident answered `ready`, and in the middle arm that is both of them, which
is the one where it matters; the outer two run the deep tier alone. Two things worth carrying: **a
spilled tier does not
fully recover when its peer is evicted** (29.82 against 33.78 from cold, at 8649 MiB free where the
cold load read 2310, so part of it stays off the card until reloaded), and **which tier pays
depends on load order**. Loading the cortex second, beside an already-resident deep model, cost the
deep model less (23.28 tok/s at best) than loading it second did, the driver paging the newcomer
first. A handoff always loads the deep model second, so the middle row is the one that matters,
but a report of a slow *cortex* after a handoff is the same fault read from the other end.

## Failure modes, each observed rather than reasoned about

- **A child that dies at load reports `failed`, never `ready`.** Pointed at a missing artifact, the
  child exited with code 1 and `GET /models/cortex` answered
  `{"state":"failed","detail":"the process exited with code 1"}`; the daemon kept answering (so you
  can ask it what happened) and the compose healthcheck stayed red. The child's own reason is in
  `docker logs model-host`, interleaved with the daemon's, because children inherit its streams.
  This is the hazard the supervisor's status ordering exists for: it reads the child's exit code
  **before** it trusts a health probe, so a start that died on a port collision cannot pass as
  ready while the previous weights are still serving.
- **A child killed under you reports `failed` with its signal.** `kill -9` on the resident child
  gave `{"state":"failed","detail":"the process exited with code -9"}` and VRAM returned to
  baseline. `POST .../start` then replaces it, no `stop` needed first, which is what the swap back
  and boot recovery both do.
- **The supervisor dying takes its children with it, and it comes back serving.** `kill -9` on the
  daemon (two children resident, VRAM 4941 MiB) ended the container, `restart: unless-stopped`
  revived it, both `llama-server`s were gone, VRAM fell, and the boot default started the cortex
  again from a clean slate. Nothing can outlive the container holding the GPU reservation.
  **What does not reconverge is the other direction:** with escalation ON, the brain's residency
  bookkeeping is in-process and nothing tells it the sidecar restarted, so a restart mid handoff
  leaves the brain believing the deep model is resident while the fresh sidecar serves the cortex.
  Recovery is step 3 below (restart the brain). This is a recorded deferral, not a surprise
  ([inference-model-manager.md](../refinements/inference-model-manager.md)).
- **Both verbs are idempotent, and an unknown id is a 404.** A second `start` spawned no second
  child; a second `stop` answered 200 and `stopped`; `POST /models/ghost/start` answered
  `404 {"error":"unknown model 'ghost'; this host serves cortex, brain"}`. Nothing a request
  carries can name a model into existence: the roster comes from the sidecar's own env.

## The chaos kill, host-side

This and the rest of the tier-scale half are tracked in
[docs/host/gpu-tier-scale.md](../host/gpu-tier-scale.md), which carries the dependency chain. The
deep-model pick at the head of that chain landed 2026-08-04; what still gates this section is the
overlay, since a handoff to kill in the middle of begins at an approved confirm card.

ADR-0030 decision 7's host half, at tier scale on the 24 GB machine. The agent-side equivalent at
small scale is the third and fourth bullets above; what is host-only is doing it mid handoff with
a real deep model, from the overlay:

```
docker compose --project-directory . -f docker/docker-compose.yml \
  -f docker/docker-compose.gpu.yml exec model-host sh -c 'kill -9 $(pgrep -f 8081)'
```

Expect: the turn fails honestly on the stream, the cortex comes back (the swap back is a `finally`),
and the next turn works. Do it once mid load as well as mid answer. Record the timings here.

## The error that sends you here

```
could not restore '<cortex model>' after 2 attempts; manual recovery is needed
```

That is `ResidencyRestoreError` from `residency.py`, logged just before as
`could not restore the cortex after a model swap; the GPU serves nothing`. It means the swap
back failed twice, so the brain now believes **no model is resident** and every later turn that
needs the GPU fails until residency is fixed. It is the one swap failure that does not
self-heal, which is why it is loud. On the user's side the turn ends with the matching note:
"the usual assistant could not be reloaded after the handoff, so the next message may fail
until the machine recovers" (`swap_notes.py`).

**What it means per backend.** Over the **scripted** host nothing stopped or started a process, so
what is broken is the brain's own residency bookkeeping (or the host it was talking to). Over the
**supervisor** host a real `llama-server` really did fail to come back, so ask the sidecar which
tier and why (`GET /models/{id}`, whose `detail` carries the exit code) before restarting anything;
the container's log has the child's own reason. Check both either way, because a cortex that really
is down and a brain that only thinks so produce the same user-visible symptom.

## The other error that sends you here

```
could not release the finished handoff; escalation stays refused until a restart
```

Logged by the conductor (`swap_conductor.py`) when the handoff store refused **both** the write
that settles a finished handoff and the delete that would drop it. The turn itself converged
(the deep model's answer stands, the cortex is serving, subagent admission reopened), but the
record is still readable as a handoff in flight, so every later escalation in that process is
refused with "a handoff to the deep model is already running" while none is. One refused
settling write on its own does not do this: the conductor then drops the record instead, which
is what frees the store's active pointer. Only a store that refuses that too gets stuck. So the
thing to fix is redis, and then step 3 below is the whole recovery: boot recovery marks the
stranded record `FAILED` and escalation works again.

## Manual recovery

1. **See what is actually running.**

   ```
   docker compose --project-directory . -f docker/docker-compose.yml \
     -f docker/docker-compose.gpu.yml ps
   ```

   `brain` and `model-host` should both read healthy. `model-host` is healthy when the cortex tier
   **or** the deep tier is READY, so an unhealthy one says no model is serving, not which one is
   missing. **A handoff in progress is not a fault, and one state of it does read unhealthy:** while
   the deep model is loading (up to `CORTEX_SWAP_LOAD_TIMEOUT_S`, 300 s) neither tier serves, and
   at `interval: 30s` with `retries: 5` the container turns unhealthy after about 150 s of that,
   which a tier-scale load can exceed. Anything that gates on health (`up -d --wait`, a monitor)
   must therefore not be pointed at a handoff window. Measured on the dev GPU with the small
   stand-ins: cortex stopped and the deep tier READY reads **healthy**; both stopped, or the deep
   tier still loading, reads unhealthy.

   `brain` is different, and deliberately: its check asks only that the `Health` RPC **answered**,
   not that the reply says ready. Since `Health` earned an honest readiness it answers
   `ready=false` for the whole swap window and for good after a restore that gave up, and a
   container that read unhealthy then would send you to fix a machine that is working. So a red
   `brain` means the gRPC server is broken or the process is gone, never that a handoff is
   running. **Residency is read from the overlay's connection dot** (amber, with the brain's own
   line: "swapping to the deep model", "a deep task is in progress", "bringing the usual
   assistant back", "could not be reloaded after a deep task", or, when the brain started against
   a GPU it could not settle, "did not come up at startup"), or from the logs below.
   Logs for either:
   `docker compose logs model-host` (the daemon and every child, interleaved, each daemon line
   naming its tier and pid) or `docker compose logs brain`. Which tier is up, precisely:

   ```
   docker compose --project-directory . -f docker/docker-compose.yml \
     -f docker/docker-compose.gpu.yml exec model-host \
     curl -s http://127.0.0.1:9300/models/cortex
   ```

2. **Ask which tier is up before you start anything.** If the deep tier is READY, a handoff is
   running and there is nothing to fix: starting the cortex now would put a second model on a GPU
   the deep model is already resident on, which on a 24 GB card is how a working handoff becomes a
   CUDA OOM. Wait for it, or fail it by stopping the deep tier first. Only when **no** tier is
   serving, bring the cortex model back. Ask the sidecar, which needs no restart:

   ```
   docker compose --project-directory . -f docker/docker-compose.yml \
     -f docker/docker-compose.gpu.yml exec model-host \
     curl -s -X POST http://127.0.0.1:9300/models/cortex/start
   ```

   `start` is a spawn and answers in milliseconds; loading a multi-GB GGUF off the model mount
   takes minutes, so poll `GET /models/cortex` for `ready` rather than believing the `start`
   ([llamacpp-gpu.md](llamacpp-gpu.md)). If the sidecar itself is gone,
   `docker compose ... up -d model-host` recreates it and its boot default starts the cortex;
   `just up-gpu` does the same for the whole GPU stack.

3. **Restart the brain so boot recovery runs.**

   ```
   docker compose --project-directory . -f docker/docker-compose.yml \
     -f docker/docker-compose.gpu.yml restart brain
   ```

   At startup, and before the seam serves a turn, `recover_handoffs` (`swap_recovery.py`) marks
   any handoff record a crash stranded as `FAILED` and converges residency back onto the cortex.
   That is what clears both the dead residency state and a record that would otherwise refuse
   the next handoff. Conversation state lives in redis, so the restart loses no chat (the same
   check [local-dev-wsl.md](local-dev-wsl.md) documents).

   **This step is not optional once a restore has given up.** The brain's residency is in-process
   bookkeeping the swap publishes, so a manager that stopped trying goes on answering `Health`
   with "the usual assistant could not be reloaded" (an amber dot) even after step 2 put the
   cortex back by hand. Restarting is what re-reads the machine; nothing else does.

   **Do step 2 first, and check the dot afterwards.** `restart` does not re-evaluate the GPU
   override's `depends_on`, so a brain restarted while the cortex still will not load comes back
   with recovery having failed. It says so rather than lying: the dot stays amber reading "did
   not come up at startup". A green dot after this step is the confirmation that recovery
   actually settled the cortex, which is why step 4 is still worth running.

4. **Confirm.** Run one ordinary turn. It must answer normally; escalation is only worth
   retrying after that.

## If it keeps happening

Nothing here is a substitute for the logs: the conductor logs each swap step, and a restore
that fails twice logs both attempts. A repeat means the model host cannot serve the cortex at
all (a wedged `llama-server`, a model file that no longer loads, a GPU the driver lost), so fix
that first rather than retrying the handoff.

A handoff aborted **before** anything was evicted (a drain that timed out, a second handoff
that lost the claim) needs none of this: the user is told nothing was unloaded, subagent
admission reopens on its own, and the next turn works.
