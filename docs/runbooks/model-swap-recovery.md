# Runbook: recovering from a model swap

The failure modes a handoff has shown, the two errors that send an operator here, and the manual
recovery. Turning escalation on and every setting named here: [model-swap.md](model-swap.md),
which also says where to read why a handoff failed. What the swap costs and whether two tiers fit:
[model-swap-measurements.md](model-swap-measurements.md).

## Failure modes, each observed rather than reasoned about

- **A child that dies at load reports `failed`, never `ready`.** Pointed at a missing artifact,
  the child exited with code 1 and `GET /models/cortex` answered
  `{"state":"failed","detail":"the process exited with code 1"}`; the daemon kept answering and
  the compose healthcheck stayed red. The child's own reason is in `docker logs model-host`,
  interleaved with the daemon's, because children inherit its streams. This is what the
  supervisor's status ordering exists for: it reads the child's exit code before it acts on a
  health probe, so a start that died on a port collision cannot pass as ready while the previous
  weights are still serving.
- **A child killed under you reports `failed` with its signal.** `kill -9` on the resident child
  gave `{"state":"failed","detail":"the process exited with code -9"}` and VRAM returned to
  baseline. `POST .../start` then replaces it, with no `stop` needed first, which is what the swap
  back and boot recovery both do.
- **The supervisor dying takes its children with it, and it comes back serving.** `kill -9` on the
  daemon, with two children resident and VRAM at 4941 MiB, ended the container;
  `restart: unless-stopped` revived it, both `llama-server`s were gone, VRAM fell, and the boot
  default started the cortex again. Nothing can outlive the container holding the GPU reservation.
  The other direction does not reconverge by itself: with escalation on, the brain's residency
  record is in-process, so a restart mid handoff leaves the brain recording the deep model as
  resident while the fresh sidecar serves the cortex. The handoff's own swap back usually settles
  it, and if that gives up the brain re-reads the machine every `CORTEX_SWAP_TIER_HEAL_S` seconds
  and publishes the cortex again the first pass that finds it serving with the deep tier off the
  card. What still needs an operator is a cortex that is genuinely not running: start it as in
  step 2 below, and the dot follows within the interval.
- **Both verbs do nothing the second time, and an unknown id is a 404.** A second `start` spawned
  no second child, a second `stop` answered 200 and `stopped`, and `POST /models/ghost/start`
  answered `404 {"error":"unknown model 'ghost'; this host serves cortex, brain"}`. Nothing a
  request contains can name a model into existence: the roster comes from the sidecar's own env.
- **A peer tier that will not restart leaves the brain serving and delegation on the CPU.**
  Restarting each `CORTEX_SWAP_EVICT_MODELS` tier on the way back is deliberately best effort: the
  turn the user is waiting on needs the cortex, and a tier that will not come back must not be
  reported as the cortex being gone. The failure is loud in the brain's log (`a tier evicted for
  the handoff could not be restarted`) and, because it is recorded rather than only logged, three
  further things are true. `Health` answers `ready=true` with `the model host is not running
  <tier>, so delegated work is running on the CPU`, which the overlay's connection tooltip shows
  as `Brain ready: <that line>`. Every subagent spawn is placed on the CPU without trying the GPU
  first. And the brain checks every `CORTEX_SWAP_EVICT_MODELS` tier every
  `CORTEX_SWAP_TIER_HEAL_S` seconds, a `GET` of each tier's state and a `start` for any that is
  not coming, clearing all of that the first pass that sees the tier `ready`. That pass is why a
  tier that dies without anybody asking it to restart is caught too, since it reads the machine
  rather than a list of refusals (`a tier of the standing residency stopped without anything
  asking it to`). Nothing here needs an operator, so the useful check is whether the retry is
  failing for a reason a retry cannot fix: look for `a tier of the standing residency could not be
  started` in the brain's log, then ask the sidecar with
  `curl -fsS http://127.0.0.1:9300/models/subagent-gpu` (the loopback override) and read the
  child's own reason out of `docker logs model-host`. A missing artifact or a bad `-ngl` is a
  config fix and a `docker compose up -d`; the retry cannot invent a GGUF.
- **The same is true at boot, and the commonest cause is a tier named but never given a file.** A
  tier listed in `CORTEX_SWAP_EVICT_MODELS` whose `CORTEX_MODEL_FILE_*` is unset is not in the
  sidecar's roster at all, so it answers `404 unknown model` to every verb. Boot recovery records
  it and continues: the dot stays green, the tooltip names the tier, and delegated work runs on
  the CPU. The repeating pass does not keep asking about this one, which is the difference between
  a tier the daemon lost and a tier it never had: a 404 is that daemon's env for the life of its
  container, so the tier is recorded once, skipped by every later pass, and left closed at the
  placer until the sidecar is replaced. Three log lines say which phase saw it, `a tier the
  standing residency includes could not be cleared at boot`, `a tier named for eviction is not in
  the model host's roster at all`, and `the model host does not serve this model at all, so this
  tier will not be asked about again`, which names both settings and has the tier's id in its own
  `model=` field ([brain-logs.md](brain-logs.md)). The fix is to name
  the artifact, or to drop the tier from the evict list, and `docker compose up -d`; nothing here
  needs a restart of the brain. What still goes amber at boot is the cortex itself failing its
  readiness check, an unreachable sidecar, a deep model that is resident and will not stop, and a
  cortex id the daemon's roster does not have.
- **A deep tier the daemon does not serve is a green boot and one loud line.**
  `CORTEX_ESCALATION=1` with `CORTEX_MODEL_FILE_BRAIN` unset leaves the deep tier out of the
  roster, so it 404s for the life of that container. The dot stays green, because the cortex is
  serving and nothing can be resident under a name the daemon never had, and the brain says once
  at startup: `escalation is enabled but the model host does not serve the deep model, so no
  handoff can ever run: name an artifact for that tier (CORTEX_MODEL_FILE_BRAIN) or turn
  escalation off (CORTEX_ESCALATION); the cortex is unaffected`. Until it is fixed, every
  escalation the user asks for is refused before anything is drained or evicted: the conductor
  asks the host whether it has the tier at all, logs `escalation was asked for but the model host
  does not serve the deep model, so the handoff was refused with nothing drained and nothing
  unloaded`, and the reply ends with "this machine has no deep model set up, so the handoff was
  not started and nothing was unloaded". Measured 2026-08-16 against the real sidecar with `brain`
  absent from its roster: the residency scope the conductor used to reach regardless took 29.7 s,
  having stopped the real cortex, met the 404 at the `start` and reloaded the cortex from the
  mount, while the refusal ahead of it took under 0.01 s with the cortex never leaving `ready`. At
  the deep tier's own scale that difference is minutes. The answer is recomputed at every attempt
  rather than remembered, so naming the artifact and `docker compose up -d` on the sidecar is
  enough and the next escalation goes through with no restart of the brain.

## The error that sends you here

```
could not restore '<cortex model>' after 2 attempts, the last of which failed on '<tier>';
manual recovery is needed
```

That is `ResidencyRestoreError` from `residency.py`, logged just before as `could not restore the
cortex after a model swap; the GPU serves nothing` with `model=<cortex model> failed_model=<tier>
attempts=2`.

**Read the second tier before the first.** The swap back has two subjects, the deep model it takes
off the card and the cortex it puts back, and either can be what failed. `<tier>` is the one the
last attempt failed on, so when it names the deep model the cortex was never even asked for: its
`start` never ran, `GET /models/<cortex model>` says `stopped` for a reason that has nothing to do
with the cortex, and what is holding the card is a deep tier that would not stop. Step 2 below is
then the whole of it, and its first half rather than its second: stop that tier, and only then
start the cortex.

The error means the swap back failed twice, so the brain has no model recorded as resident and
every later turn that needs the GPU fails until residency is fixed. Nothing in the swap will try
again, which is why it is loud. What does try again is the background pass, which re-reads the
machine every `CORTEX_SWAP_TIER_HEAL_S` seconds and publishes the cortex as the resident the first
time it finds it serving with the deep tier off the card, so the fix is to make that true (step 2)
and the brain follows on its own. On the user's side the turn ends with the matching note: "the
usual assistant could not be reloaded after the handoff, so the next message may fail until the
machine recovers".

Over the `scripted` host nothing stopped or started a process, so what is broken is the brain's
own residency record or the host it was talking to. Over the `supervisor` host a real
`llama-server` really did fail to come back, so ask the sidecar which tier and why
(`GET /models/{id}`, whose `detail` has the exit code) before restarting anything. Check both
either way, because a cortex that really is down and a brain whose record is merely wrong produce
the same user-visible symptom.

## The other error that sends you here

```
could not release the finished handoff; escalation stays refused until a restart
```

Logged by the conductor (`swap_conductor.py`) when the handoff store failed both the write that
settles a finished handoff and the delete that would drop it. The turn itself converged: the deep
model's answer stands, the cortex is serving, subagent admission reopened. But the record is still
readable as a handoff in flight, so every later escalation in that process is refused with "a
handoff to the deep model is already running" while none is. One refused settling write on its own
does not do this, because the conductor then drops the record instead, which is what frees the
store's active pointer. So the thing to fix is redis, and then step 3 below is the whole recovery:
boot recovery marks the stranded record `FAILED` and escalation works again.

## Manual recovery

1. **See what is actually running.**

   ```
   docker compose --project-directory . -f docker/docker-compose.yml \
     -f docker/docker-compose.gpu.yml ps
   ```

   `brain` and `model-host` should both read healthy. `model-host` is healthy when the cortex tier
   or the deep tier is READY, so an unhealthy one says no model is serving, not which one is
   missing. A handoff in progress is not a fault, and one state of it does read unhealthy: while
   the deep model is loading (up to `CORTEX_SWAP_LOAD_TIMEOUT_S`, 300 s) neither tier serves, and
   at `interval: 30s` with `retries: 5` the container turns unhealthy after about 150 s of that,
   which a tier-scale load can exceed. Anything that waits on health (`up -d --wait`, a monitor)
   must therefore not be pointed at a handoff window.

   `brain` is different, deliberately: its check asks only that the `Health` RPC answered, not
   that the reply says ready. `Health` answers `ready=false` for the whole swap window and for
   good after a restore that gave up, and a container that read unhealthy then would send you to
   fix a machine that is working. So a red `brain` means the gRPC server is broken or the process
   is gone, never that a handoff is running. Residency is read from the overlay's connection dot
   (amber, with the brain's own line: "swapping to the deep model", "a deep task is in progress",
   "bringing the usual assistant back", "could not be reloaded after a deep task", or "did not
   come up at startup"), or from `docker compose logs model-host` (the daemon and every child,
   interleaved, each daemon line naming its tier and pid) and `docker compose logs brain`. Both
   print each line's own fields after its message, and a message never repeats a field it already
   has, so `started a model process model=cortex pid=8 port=8080` reads each value once
   ([how to read either log](brain-logs.md)). Which tier is up, precisely:

   ```
   docker compose --project-directory . -f docker/docker-compose.yml \
     -f docker/docker-compose.gpu.yml exec model-host \
     curl -s http://127.0.0.1:9300/models/cortex
   ```

2. **Ask which tier is up before you start anything.** If the deep tier is READY, a handoff is
   running and there is nothing to fix: starting the cortex now would put a second model on a GPU
   the deep model is already resident on, which on a 24 GB card is how a working handoff becomes a
   CUDA out-of-memory error. Wait for it, or fail it by stopping the deep tier first. Only when no
   tier is serving, bring the cortex model back. Ask the sidecar, which needs no restart:

   ```
   docker compose --project-directory . -f docker/docker-compose.yml \
     -f docker/docker-compose.gpu.yml exec model-host \
     curl -s -X POST http://127.0.0.1:9300/models/cortex/start
   ```

   `start` is a spawn and answers in milliseconds; loading a multi-GB GGUF off the model mount
   takes minutes, so poll `GET /models/cortex` for `ready` rather than treating the `start` as
   done. If the sidecar itself is gone, `docker compose ... up -d model-host` recreates it and its
   boot default starts the cortex; `just up-gpu` does the same for the whole GPU stack.

   **This is the step that fixes the dot, and there is nothing to do after it.** Within one
   `CORTEX_SWAP_TIER_HEAL_S` the brain reads the cortex `ready` and the deep tier off the card,
   publishes the cortex as the resident again, says `the cortex is serving again, so residency was
   regained without a restart` in its log, and answers `Health` green. Turns work from that
   moment, and so does the subagent pool's GPU placement.

3. **Restart the brain only if a handoff record is stuck.**

   ```
   docker compose --project-directory . -f docker/docker-compose.yml \
     -f docker/docker-compose.gpu.yml restart brain
   ```

   At startup, and before the gRPC service serves a turn, `recover_handoffs` marks
   any handoff record a crash stranded as `FAILED` and moves residency back onto the cortex.
   Conversation state lives in redis, so the restart loses no chat.

   The one thing only a restart clears is a handoff record that is still readable as in flight,
   which refuses every later escalation with "a handoff to the deep model is already running".
   Residency itself does not need it. So run this step when escalation is being refused, and skip
   it when the dot is the only complaint.

   **Do step 2 first, and check the dot afterwards.** `restart` does not re-evaluate the GPU
   override's `depends_on`, so a brain restarted while the cortex still will not load comes back
   with recovery having failed. It says so instead of showing green: the dot stays amber reading
   "did not come up at startup", and that clears itself the moment the cortex comes up and a pass
   reads it. A green dot after this step confirms that recovery settled the cortex.

4. **Confirm.** Run one ordinary turn. It must answer normally; escalation is only worth retrying
   after that.

## The chaos kill, host-side

At tier scale on the 24 GB machine, from the overlay, since a handoff to kill in the middle of
begins at an approved confirm card. The small-scale equivalent is the third and fourth failure
modes above.

```
docker compose --project-directory . -f docker/docker-compose.yml \
  -f docker/docker-compose.gpu.yml exec model-host sh -c 'kill -9 $(pgrep -f 8081)'
```

Expect the turn to fail plainly on the stream, the cortex to come back (the swap back is a
`finally`), and the next turn to work. Do it once mid load as well as mid answer, and record the
timings here.

## If it keeps happening

Nothing here is a substitute for the logs: the conductor logs each swap step, and a restore that
fails twice logs both attempts. A repeat means the model host cannot serve the cortex at all (a
wedged `llama-server`, a model file that no longer loads, a GPU the driver lost), so fix that
first rather than retrying the handoff. A handoff aborted before anything was evicted (a drain
that timed out, a second handoff that lost the claim) needs none of this: the user is told nothing
was unloaded, subagent admission reopens on its own, and the next turn works.
