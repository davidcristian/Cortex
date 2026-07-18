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
and swapped, on the dev GPU with two small artifacts standing in for the tiers, with the timings
and the exact commands in "The mechanism, as measured" below. **Tier scale is not validated and
cannot be here:** gemma-4-12B alone takes 7715 of the dev GPU's 8188 MiB, so the real cortex and
any deep-model candidate cannot be swapped between on 8 GB, and the 24 GB machine owns that
half (plus the deep-model pick itself, which ADR-0004 does not have yet). Read every number below
as the mechanism's, never as a tier's.

## Is the capability even on?

Escalation is **off by default**. It is on only when `CORTEX_ESCALATION` is set, and then the
deployment must also set `CORTEX_MODELHOST_BACKEND` (`scripted`, or `supervisor` with a
`CORTEX_MODELHOST_ENDPOINT`) and
`CORTEX_BRAIN_ENDPOINT`, or the brain refuses to boot (`config_swap.py`). With escalation off,
nothing below can happen: no `escalate_to_brain` tool, no conductor, no boot recovery. The
`model-host` sidecar itself is not gated by that switch: it comes up with the GPU override either
way, serving the cortex as the always-on `llama-cortex` service used to.

Other knobs: `CORTEX_MODEL_BRAIN` (the deep tier's logical id, default `brain`),
`CORTEX_SWAP_EVICT_MODELS` (further hosted tiers a swap stops first, comma separated),
`CORTEX_SWAP_DRAIN_TIMEOUT_S` (60 s), `CORTEX_SWAP_LOAD_TIMEOUT_S` (300 s),
`CORTEX_MODELHOST_TIMEOUT_S` (60 s, one control call's deadline).

**One pairing to keep, because nothing validates it for you.** The sidecar's `stop` answers only
once the child is dead and reaped, so it can legitimately take `CORTEX_MODELHOST_STOP_GRACE_S`
(10 s) plus `CORTEX_MODELHOST_REAP_TIMEOUT_S` (30 s) before replying, **plus**
`CORTEX_MODELHOST_PROBE_TIMEOUT_S` (5 s) when a `status` got the tier's lock first: `status` holds
the same per-model lock as `stop` and probes the child's `/health` inside it, and the compose
healthcheck asks for a status every 30 s, so a queued one is the normal case, not a corner. So the
rule is

    probe_timeout_s + stop_grace_s + reap_timeout_s  <  CORTEX_MODELHOST_TIMEOUT_S

which the shipped defaults satisfy (5 + 10 + 30 = 45 < 60). Measured against a SIGSTOPped child on
the shipped grace: a stop whose lock was free took **10.89 s**, and the same stop issued 0.2 s
behind a `GET /models/cortex` took **15.70 s**, that status itself taking **5.80 s**, which is the
probe timeout plus its request overhead. Both stops ended correctly (`stopped`, no `llama-server`
left). Tuning by the grace and the reap alone (say 20 and 35, a compliant sum of 55) reaches 60 s,
the control client times out, and the handoff aborts although the eviction was working.
`GET /health` reports the two stop bounds the daemon actually got, which is how you check a running
container rather than its env.

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
| end to end | one `Converse` turn through the brain container | `Health` ready, `text_delta`s, `turn_complete`; the reply came off the supervised child over `http://model-host:8080` |

Tier scale will be minutes rather than seconds on both halves: an 18 GB GGUF off the model mount at
the measured mount read rate is what `CORTEX_SWAP_LOAD_TIMEOUT_S` (300 s) exists for. The eviction
half is sub-second only while the child is **idle**; every path that evicts a tier which was
answering (the cancellation restore, and the shutdown sweep) pays the whole grace per busy tier,
which is what `stop_grace_period: 45s` on the container is sized for (3 tiers x 10 s plus slack,
the sweep being sequential).

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
   tier still loading, reads unhealthy. Logs for either:
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
