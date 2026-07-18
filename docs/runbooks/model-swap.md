# Runbook: model swap (brain handoff)

What to do when a handoff leaves the GPU in a state you have to fix by hand. Design and
rationale: [ADR-0030](../adr/ADR-0030-brain-handoff.md). Ops loop and the compose basics:
[local-dev-wsl.md](local-dev-wsl.md); the cortex `llama-server` itself:
[llamacpp-gpu.md](llamacpp-gpu.md).

**Scope today.** This is the manual-recovery half only. The wired model host is the
**scripted** one (`CORTEX_MODELHOST_BACKEND=scripted`, `swap_builders.py`): it tracks residency
and readiness honestly, so the whole path runs end to end, but it **starts no process and moves
no weights**. The real supervisor backend, the procedure for a live swap, and the measured
timings ADR-0030 expects here all arrive with that sub-slice, and this file grows them then.
No real model swap has been validated yet.

## Is the capability even on?

Escalation is **off by default**. It is on only when `CORTEX_ESCALATION` is set, and then the
deployment must also set `CORTEX_MODELHOST_BACKEND` (`scripted` today) and
`CORTEX_BRAIN_ENDPOINT`, or the brain refuses to boot (`config_swap.py`). With escalation off,
nothing below can happen: no `escalate_to_brain` tool, no conductor, no boot recovery.

Other knobs: `CORTEX_MODEL_BRAIN` (the deep tier's logical id, default `brain`),
`CORTEX_SWAP_EVICT_MODELS` (further hosted tiers a swap stops first, comma separated),
`CORTEX_SWAP_DRAIN_TIMEOUT_S` (60 s), `CORTEX_SWAP_LOAD_TIMEOUT_S` (300 s).

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

**What it does not mean today.** With the scripted host nothing stopped or started a container,
so `llama-cortex` is exactly where compose left it; what is broken is the brain's own residency
bookkeeping (or the host it was talking to). Check the containers anyway, because a cortex
that really is down produces the same user-visible symptom.

## Manual recovery

1. **See what is actually running.**

   ```
   docker compose --project-directory . -f docker/docker-compose.yml \
     -f docker/docker-compose.gpu.yml ps
   ```

   `brain` and `llama-cortex` should both read healthy. Logs for either:
   `docker compose logs llama-cortex` / `docker compose logs brain`.

2. **Bring the cortex model back if it is not healthy.**

   ```
   docker compose --project-directory . -f docker/docker-compose.yml \
     -f docker/docker-compose.gpu.yml up -d llama-cortex
   ```

   `just up-gpu` does the same for the whole GPU stack. Loading a multi-GB GGUF off the model
   mount takes minutes; wait for the healthcheck rather than the `up` returning
   ([llamacpp-gpu.md](llamacpp-gpu.md)).

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
