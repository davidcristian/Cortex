# Runbook: the model swap (brain handoff)

How to turn escalation on, what every setting does, and where to read why a handoff failed.
Whether the two tiers fit on one card: [model-swap-measurements.md](model-swap-measurements.md).
When a handoff leaves the GPU in a state you have to fix by hand:
[model-swap-recovery.md](model-swap-recovery.md). Design:
[ADR-0030](../adr/ADR-0030-brain-handoff.md). The compose basics are in
[local-dev-wsl.md](local-dev-wsl.md), the cortex `llama-server` itself in
[llamacpp-gpu.md](llamacpp-gpu.md), and the sidecar's contract in
[brain-model-manager.md](../modules/brain-model-manager.md).

Two model hosts can be wired through `CORTEX_MODELHOST_BACKEND`. The `scripted` one tracks
residency and readiness so the whole path runs end to end, but starts no process and moves no
weights. The `supervisor` one is the real `HttpModelHost` over the `model-host` sidecar's control
API.

## Is the capability even on?

Escalation is off by default. It is on only when `CORTEX_ESCALATION` is set, and then the
deployment must also set `CORTEX_MODELHOST_BACKEND` (`scripted`, or `supervisor` with a
`CORTEX_MODELHOST_ENDPOINT`) and `CORTEX_BRAIN_ENDPOINT`, or the brain refuses to boot. The GPU
override passes all of these through from the host by name, so an exported shell variable or a
line in the repo-root `.env` is enough. Confirm what the brain will receive before starting it:

```bash
docker compose --project-directory . -f docker/docker-compose.yml \
  -f docker/docker-compose.gpu.yml config brain | grep -E 'CORTEX_(ESCALATION|MODELHOST|BRAIN|SWAP)'
```

The lines under `brain:` are what that container gets, and the `model-host:` lines below them are
the sidecar's own. A key rendered as `null`, such as `CORTEX_ESCALATION: null`, is unset on the
host and never enters the container. With escalation off there is no `escalate_to_brain` tool, no
conductor and no boot recovery. The `model-host` sidecar itself comes up with the GPU override
either way and serves the cortex.

The other settings: `CORTEX_MODEL_BRAIN` (the deep tier's id, default `brain`),
`CORTEX_SWAP_EVICT_MODELS` (further hosted tiers a swap stops first, as a JSON list such as
`["subagent-gpu"]`; a comma-separated string fails the brain at boot, and so does a list naming
the cortex or the deep tier), `CORTEX_SWAP_BRAIN_VRAM_MIB` (0, the deep tier's measured VRAM
cost), `CORTEX_SWAP_DRAIN_TIMEOUT_S` (60 s), `CORTEX_SWAP_LOAD_TIMEOUT_S` (300 s),
`CORTEX_MODELHOST_TIMEOUT_S` (60 s, one control call's deadline) and `CORTEX_SWAP_TIER_HEAL_S`
(30 s, how often the brain re-reads the evicted tiers and restarts one found down). On the
sidecar, `CORTEX_MODELHOST_NVIDIA_SMI` names the binary it reads the card with.

**`CORTEX_SWAP_DRAIN_TIMEOUT_S` bounds your wait, not a subagent's run.** The drain waits for the
subagent runs already admitted to finish, and a whole CPU subtask on the shipped model takes 200
to 300 s, so a handoff asked for while delegated work is in flight usually spends the 60 s and
aborts before anything is evicted. That abort is the safe direction: the cortex never stops
serving and the reply says so. Raise the setting only if you would rather wait than retry, and
size it against that 200 to 300 s subtask. The smallest value that even covers a wedged stream
sits above the pool's 600 s ceiling, which hands that stream ten minutes of your handoff.

**`CORTEX_SWAP_CORESIDENT` is the one setting that changes what a handoff does to the machine,
and it is off.** Set it and a swap stops the cortex and nothing else: every
`CORTEX_SWAP_EVICT_MODELS` tier keeps serving beside the deep model, the subagent pool is never
quiesced, delegated work runs through the handoff, there is no drain at all, and the deep phase
may spawn. The swap back still starts every listed tier, which does nothing to one that never
stopped.

Setting it also requires `CORTEX_SWAP_BRAIN_VRAM_MIB`, and the brain refuses to boot without it.
That figure is how much free device memory the deep tier needs, measured on your own card by the
procedure in [model-swap-measurements.md](model-swap-measurements.md). The sidecar reports what the
card has free on `GET /health`, and a swap reads it after the evictions and before the load. Short
of the figure, the handoff is refused with both numbers in the log and in the reply's note, the deep
model is never started, and the recorded residency is put back. A model host that can see no card at
all refuses the same way. Set the figure above the deep tier's own cost: under WSL the driver puts
part of its last buffers in system memory with most of a gigabyte still free, and the check cannot
see memory taken during the load. On this card the pick's cost is 19125 MiB (Qwen3.8-27B's 15,770,
its spill point not measured), and the pick spilled beside an idle peer at up to 19967 MiB free, so
20125 refuses every spill seen by at least 158 MiB, little room for the floor rising mid-load. **So
on a 24 GB card leave co-residency off**: beside the E4B tier the check refuses every handoff, each
costing a cortex reload. The same figure is used with co-residency off, where it is optional and
guards the ordinary handoff on a card too small for the deep tier at all.

**One pairing to keep, and the brain fails to start when you break it.** The sidecar's `stop`
answers only once the child is dead and reaped, so it can legitimately take
`CORTEX_MODELHOST_STOP_GRACE_S` (10 s) plus `CORTEX_MODELHOST_REAP_TIMEOUT_S` (30 s) before
replying, plus `CORTEX_MODELHOST_PROBE_TIMEOUT_S` (5 s) when a `status` took the tier's lock
first. `status` holds the same per-model lock as `stop` and probes the child's `/health` inside
it, and the compose healthcheck asks for a status every 30 s, so a queued one is the normal case.
The rule is

    probe_timeout_s + stop_grace_s + reap_timeout_s  <  CORTEX_MODELHOST_TIMEOUT_S

which the shipped defaults satisfy (5 + 10 + 30 = 45 < 60). Measured against a SIGSTOPped child
on the shipped grace: a stop whose lock was free took 10.89 s, and the same stop issued 0.2 s
behind a `GET /models/cortex` took 15.70 s, that status itself taking 5.80 s. Both stops ended
correctly. Tuning by the grace and the reap alone (say 20 and 35, a compliant sum of 55) reaches
60 s, the control client times out, and the handoff aborts although the eviction was working.

`GET /health` reports all three bounds the daemon got, and the brain reads them once at boot. If
`CORTEX_MODELHOST_TIMEOUT_S` does not sit strictly above their sum the brain fails at boot, so a
mispaired stack fails at `docker compose up` instead of inside somebody's handoff. The traceback
names every term; the brain logs the same refusal one line earlier as one constant message:

```
ERROR:cortex_orchestrator.swap_builders:the control deadline does not clear the model host's worst stop deadline_s=60.0 probe_timeout_s=5.0 reap_timeout_s=35.0 stop_grace_s=20.0 worst_s=60.0
```

`grep "does not clear"` matches every instance whatever the numbers are. Raise
`CORTEX_MODELHOST_TIMEOUT_S`, or lower whichever sidecar bound you had raised, and bring the stack
up again. Two cases deliberately do not fail the boot: a `model-host` that is not answering yet,
logged at warning since a sidecar that is merely down comes back under the restart policy, and the
`scripted` backend, which stops no process and so has no bounds to report.

**Restarting the sidecar under a running brain is safe.** `GET /health` includes a `boot_id`, a
fresh value per daemon process, and the brain records which one it was talking to at startup and
asks again before each handoff evicts anything. A different answer means the sidecar was replaced,
so everything the brain recorded about which model holds the card is about a process that is gone.
It then moves residency back onto the cortex, republishes what it observed, and re-reads the three
stop bounds. At warning level you will see `the model host has been replaced since the last
handoff; reconciling residency against the daemon that is answering now`.

Two conditions abort that one handoff rather than serving it, both before anything is unloaded, so
the cortex keeps answering: a machine the reconciliation could not settle back onto the cortex, and
a sidecar that came back with stop bounds the brain's own deadline no longer clears. Fix the
second by editing env and restarting; the brain keeps serving ordinary turns meanwhile. Nothing
detects a sidecar replaced under a brain that then never escalates, so a green connection dot can
be a reading taken before that restart. What is watched is the direction that costs an operator
something: a report saying the GPU is not serving is checked against the machine every
`CORTEX_SWAP_TIER_HEAL_S` seconds, so an amber dot clears itself within one interval of the cortex
coming back. The line to look for is `the cortex is serving again, so residency was regained
without a restart`.

## Bringing the real host up

```
CORTEX_MODELS_DIR=/srv/models just up-gpu
```

The GPU override runs `model-host` instead of `llama-cortex`, and the brain waits on its
healthcheck, which asks whether a tier that can serve a turn is READY rather than whether the
daemon answers. At cold boot the daemon starts only the cortex. Ask it what it is doing from
inside the network:

```
docker compose --project-directory . -f docker/docker-compose.yml \
  -f docker/docker-compose.gpu.yml exec model-host \
  curl -s http://127.0.0.1:9300/health
```

The control API is deliberately not published to the host: it can start and stop processes on the
container holding the GPU and the models mount, and on WSL2 a `127.0.0.1` publish is reachable
from Windows' own localhost too. Layer `docker/docker-compose.modelhost-loopback.yml` when a
host-side live test needs it (control API on 9300, deep tier on 9081, GPU subagent on 9083) and
take it down after; the cortex tier's own `127.0.0.1:8080` stays published.

To give the deployment a deep tier, name its artifact in the `model-host` environment
(`CORTEX_MODEL_FILE_BRAIN`, with `CORTEX_NGL_BRAIN` and `CORTEX_CTX_SIZE_BRAIN` to fit it; each
candidate's cost: [deep candidates](../readings/deep-candidates.md)) and set `CORTEX_ESCALATION=1`
and `CORTEX_MODELHOST_BACKEND=supervisor`. The GPU override already points `CORTEX_BRAIN_ENDPOINT`
at `http://model-host:8081`. A tier with no artifact is not in the roster, so a stock stack answers
404 for the deep model, and `GET /health` lists exactly the tiers it can run.

**Name the deep model's drafter beside it, and four settings move with it.** Naming
`CORTEX_MODEL_FILE_BRAIN_DRAFT` (the drafter is
`google/gemma-4-31B-it-assistant/assistant-F16.gguf`) starts the deep model with its
multi-token-prediction drafter, which on this card decoded one reasoning prompt at 1.86 to 1.89
times the plain rate and a tool-call turn and an answer-text turn at 1.34 times it. It costs 997
to 1020 MiB more on the card and about a tenth more load time, which a handoff recovers within its
first 1500 decoded tokens. The setting stays empty by default, because the drafter serves only
this deep model: name both or neither. A deployment naming it:

- adds the drafter's cost to `CORTEX_SWAP_BRAIN_VRAM_MIB`, so the fit check compares the free
  figure against the load that really runs, since nothing in the brain can see the drafter;
- measures `CORTEX_SWAP_BRAIN_DECODE_TPS` again with the drafter drafting, on a tool-call turn,
  since a plain floor misses a drafter-sized overcommit and a drafting one sees it only there;
- lists the GPU subagent tier in `CORTEX_SWAP_EVICT_MODELS` and leaves `CORTEX_SWAP_CORESIDENT`
  off, so a handoff stops that tier before the load.

To confirm the drafter is drafting, read `timings` on a deep-tier reply: `draft_n` and
`draft_n_accepted` are present only while it drafts, and nothing on `GET /health` says whether a
drafter is loaded. Expect a lower SM clock while it drafts, 0.45 to 0.48 of `clocks.max.sm`
against the plain tier's 0.56 to 0.62 on this card under its power cap; a lower clock beside a
higher decode rate is the drafter working, not a fault.

## Why a handoff failed

The reply a user gets says what is true of the GPU, never what broke: "the deep model could not
be loaded, so the handoff was cancelled" is the whole of it, deliberately. What broke is written
in two places instead, and either is enough.

**The brain's own log, which is where to look while somebody is waiting.** Every handoff that
ends failed writes one `WARNING` from `cortex_core.swap_settle`:

```
WARNING:cortex_core.swap_settle:a handoff ended failed reason="<what happened>" session_id=<chat id> turn_id=<turn id>
```

The fields print in name order, whatever order the call site wrote them in. `turn_id` is the
escalating turn's id, which is also the handoff's, since one turn escalates at most once, so
`grep turn_id=` on that id returns this line beside the turn's own failures and every tool call it
made. Grep the field name with an id you already have and never a prefix: a turn id is a bare
`uuid4`. The Redis key below is the one place that id is still written with the word `handoff`,
being the record's own address.

`session_id` is the chat that turn belongs to, and it is on every swap-path line rather than on
this one alone, so `grep session_id=` on the chat's own id returns the refusals that chat met, the
settle that ended its handoff, the deep tier's decode rate for it and the boot that found it
stranded, beside that chat's recalls, summaries and tool calls. A line about the card rather than
about any one handoff names neither id: every residency line boot recovery and the swap back write
names the `model` instead, because a tier's state is the deployment's rather than one chat's.
Start from the chat when a user reports something, from the turn when you already have one, and
from the model when the machine itself is the suspect.

The `reason` field is the whole sentence. On a swap that broke it is the model host's own words:
the method, the route, the tier, the HTTP status and the leading characters of the daemon's
response body, wrapped in which move the swap was making. Six kinds of sentence are possible:

| What `reason` starts with | What actually happened |
| --- | --- |
| `the model host failed while swapping in ...`, `the model host does not serve ...`, `model ... did not become ready in time`, or one of the fit check's two (`needs N MiB of free device memory`, `reports no device memory`) | the swap in broke, and on the first two the daemon's own answer follows the colon |
| `could not restore '<cortex>' after 2 attempts ...` | the swap back gave up; [model-swap-recovery.md](model-swap-recovery.md) is entirely about this one |
| `a residency scope for ... is already active` | nothing was evicted for this turn; something entered the swap without taking the handoff claim first, and another handoff owns the GPU |
| `delegated work was still running when the drain bound elapsed ...` | nothing was evicted and nothing broke; a subagent outlasted `CORTEX_SWAP_DRAIN_TIMEOUT_S` |
| `the turn was torn down before the handoff finished` | the user or the stream ended the turn; the machine is fine |
| `the brain restarted while this handoff was still in flight` | boot recovery settled a record its own process did not write |

Anything else is the deep model's own server dying mid answer, whose message comes from the
inference backend rather than from the swap, and the user already has that one.

**One thing that reads like a failure does not settle as one.** A completion cut by a token limit
while the deep model was writing a tool call leaves a fragment that will not parse, and the phase
ends the handoff rather than failing it: the record settles `done`, the reply says what every
capped reply says, and the only line about it is a `WARNING` from `cortex_core.brain_phase`.

```
WARNING:cortex_core.brain_phase:a tool call the deep model wrote could not be read; ending this handoff where it broke capped=<whether a limit did it> model=<the deep model> session_id=<chat id> turn_id=<turn id>
```

`capped` is the field to read. True means a token limit ended the completion, either
`CORTEX_REPLY_MAX_TOKENS` if the deployment set one or the deep tier's own context window if not.
False means no limit was reported and the model wrote a call its own grammar broke, which is a
model problem rather than a budget one. Either way the exception is on the line as a traceback.

**The record itself, which is where to look afterwards.** The same sentence is on the handoff
record, which survives the process that wrote it and stays readable for the diagnosis hour the
store keeps a terminal record:

```sh
docker compose --project-directory . -f docker/docker-compose.yml \
  exec redis redis-cli get 'cortex:handoff:<turn id>'
```

The `state` is `failed` and the `failure` field is the reason. This is the copy to reach for when
the brain has since restarted or the log has rolled. When the store fails the settling write, the
conductor drops the record outright, so the failure that costs you the record is exactly the
failure the log line covers for. These two are deliberately the whole of it: nothing reads the
reason back, and it is not on the residency report, which only ever annotates a serving answer and
so would be silent about the two states whose reason you would actually want.
