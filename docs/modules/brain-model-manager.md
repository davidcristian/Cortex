# brain/packages/model_manager (`cortex_model_manager`)

**Purpose.** The real half of the process-lifecycle port (ADR-0030 decision 3): a small
supervisor daemon that starts and stops one `llama-server` child per logical model, plus the
`ModelHost` adapter the brain drives it with. One package with two halves, because the ADR names
one; they run in **different containers** and never import each other:

- the **daemon** runs in the `model-host` sidecar (the container that holds the GPU device
  reservation and the read-only models mount) and is the only thing in the system that can
  spawn or kill a model process;
- the **adapter** (`HttpModelHost`) runs in the CPU-only brain container and speaks the daemon's
  HTTP control API. It holds no process knowledge at all.

Killing a child loses nothing by construction, which is ADR-0005 decision 3 made literal and the
one hard rule's whole premise: every model instance is stateless and disposable.

## Public contract

Everything importable from `cortex_model_manager` (`__all__` is the API).

**The adapter (brain side).** `HttpModelHost(endpoint: str, client: httpx.AsyncClient)` is a
`ModelHost`: `start`/`stop`/`status`, taking a logical model id and nothing else, plus
`device_memory()`, `control_bounds()` and `boot_id()`, which take none.

- `start(model)` POSTs `/models/{id}/start`, `stop(model)` POSTs `/models/{id}/stop`, and
  `status(model)` GETs `/models/{id}` and returns the `ModelHostState` the body names. The id is
  percent-escaped, so an id is a name and never a path fragment.
- `device_memory()` GETs `/health` and returns `DeviceMemory(free_mib, total_mib)`, or `None`
  when either figure is missing or is not an integer, which is what a daemon with no card
  reports and also what one too old to carry the fields says. Deliberately that route: it takes
  no per-model lock, and a swap asks this between an eviction and a load, where queueing behind
  a stop would add that stop's whole grace to the answer.
- `control_bounds()` GETs the same `/health` and returns `ControlBounds(probe_timeout_s,
  stop_grace_s, reap_timeout_s)`, or `None` when any one of the three is missing, is not a
  number, is a bool, or is negative. Read once at wiring time by the brain's composition root,
  never inside a swap: these are the sidecar's env and cannot change under a running container.
  A partial answer is no answer, because a sum missing a term would clear a deadline the whole
  rule fails (ADR-0030's deadline-pairing addendum). It is read a second time, off the same route,
  when a swap finds the daemon replaced: a restart is the only event that can change either side
  of that pairing under a brain that never restarted.
- `boot_id()` GETs the same `/health` once more and returns the value the daemon names its own
  boot with, or `None` when the body carries none, an empty one, or something that is not a
  string. Read at the boot publish and once per handoff before anything is evicted, and compared
  for equality only: a different value means every belief the brain holds about what is resident
  was formed against a supervisor process that no longer exists (ADR-0030's host-generation
  addendum).
- Every failure crosses as `ModelHostError` with its cause chained, and **nothing is retried
  here**: a transport failure, a 404, a 503, a body that will not decode, and a state word this
  version does not know all mean "the model host did not answer the question", which is for the
  swap to interpret (`residency_moves` catches exactly `ModelHostError`).
- A `FAILED` state is a normal answer and is logged at error level with the sidecar's `detail`,
  because that exit code is the only diagnosis the brain side ever sees.
- The client is injected, and unlike the generation clients it must carry a real read deadline: a
  control call that hung would hang a swap step under no bound at all.

**The control API (sidecar side).**
`build_app(supervisor, *, boot_model, close=nothing_to_close, device=None)` returns the Starlette
app; `model_host_lifespan(supervisor, boot_model, close)` is its lifespan. `device` is the
`DeviceMemoryProbe` the health route reads the card through, defaulting to `NoDeviceMemory`, which
answers that this daemon has none. Four routes and no more:

| Route | Meaning |
|---|---|
| `GET /health` | the daemon is up, which boot of it this is, the roster it serves, the three bounds one control call may spend, and how much of the card is free (`{"status": "ok", "boot_id": "0f9c...", "models": [...], "probe_timeout_s": 5.0, "stop_grace_s": 10.0, "reap_timeout_s": 30.0, "device_free_mib": 22484, "device_total_mib": 24463}`). An operator's first question, and the only way to read what a running daemon actually got. All three timing terms, because the brain reads them here at wiring time and refuses to serve when its own `CORTEX_MODELHOST_TIMEOUT_S` does not clear their sum (ADR-0030's deadline-pairing addendum), and because a reader given two of them can tune to a compliant-looking sum the third carries past that deadline. `boot_id` is the one field a restart changes: everything else on this body is identical across one, so it is what tells a brain that its beliefs about the GPU were formed against a daemon that is gone (ADR-0030's host-generation addendum). The two device figures are `null` on a daemon that can see no card, and they are what the brain's fit check compares against (ADR-0030's fit-check addendum). |
| `GET /models/{id}` | `{"model", "state", "detail"}`, `state` being `stopped`/`loading`/`ready`/`failed`. |
| `POST /models/{id}/start` | begin loading it (idempotent), answering the state it left behind. |
| `POST /models/{id}/stop` | end it, returning once the child is reaped (idempotent). |

An id outside the roster is **404**; a supervisor failure is **503**. Both become
`ModelHostError`, but the runbook sends them to different halves of itself.

**The device seam.** `DeviceMemoryProbe` is `read() -> DeviceMemory | None`, with two
implementations: `NoDeviceMemory` (always `None`, the default and what a CPU-only stack truthfully
has) and `NvidiaSmiMemory(binary, timeout_s)`, one bounded
`nvidia-smi --query-gpu=memory.free,memory.total --format=csv,noheader,nounits`. The binary comes
from `CORTEX_MODELHOST_NVIDIA_SMI` and the bound from `CORTEX_MODELHOST_PROBE_TIMEOUT_S`, both
control-plane reads a swap step waits on. **Every way it can go wrong is "no reading", never an
exception**: a missing binary (the normal case where no GPU is reserved, since the container
toolkit injects it alongside the driver), a non-zero exit, a body that will not parse, and **more
than one visible GPU**, because nothing downstream knows which card a model would land on, so this
declines to pick a row.

**The supervisor.** `ModelSupervisor(roster, processes, probe, *, stop_grace_s, reap_timeout_s,
probe_timeout_s)` over the two seams `ChildProcesses` (`spawn(argv) -> ChildProcess`) and
`HealthProbe` (`serving(url) -> bool`), with `AsyncioChildProcesses` and `HttpHealthProbe` as the
real adapters and `ModelStatus(model, state, detail)` as its answer. `stop_all()` is the shutdown
sweep, `boot_id` is a `uuid4().hex` minted per instance and therefore per daemon process, which
`GET /health` publishes and nothing in this process reads back (it certifies the child table this
object holds: random rather than counted, since a counter in a process that restarted begins again
at the number a reader compares to notice the restart), and `control_bounds` is the core
`ControlBounds(probe_timeout_s, stop_grace_s, reap_timeout_s)` it was wired with, which the same
route reports. It is handed the probe's deadline
although it spends none of it: that bound belongs to the client behind `probe`, and a `status`
probes inside the same per-model lock a `stop` takes, so this is the one object that can state the
whole worst case of its own slowest call. The defaults are `DEFAULT_STOP_GRACE_S` (10 s),
`DEFAULT_REAP_TIMEOUT_S` (30 s) and `DEFAULT_PROBE_TIMEOUT_S` (5 s), each overridable by the env
of the same name.

**The roster.** `ModelHostConfig` (env-only) builds `TierArgs` values, `tier_spec` turns each into
a `ModelSpec(model, port, argv)` via `llama_server_argv`, and `build_roster` indexes them.
`CORTEX_MMPROJ_FILE_CORTEX` (ADR-0029) adds llama.cpp's `--mmproj` pair to the **cortex** tier's
argv, which is the whole of the vision wiring on this side: the projector loads beside the model,
and the brain then discovers the capability from the running server's `/props` rather than from a
second flag here that could disagree with it. Empty (the default) starts the tier text-only. The
projector ships under the same read-only models mount, so no extra bind is needed.
`CORTEX_IMAGE_MAX_TOKENS` rides beside it and decides how much of a screen survives the downscale:
a positive value, `1024` by default, emits `--image-max-tokens N` **and** `--ubatch-size
max(N, 512)`, and zero hands the budget back to the model, emitting neither flag. The default is
raised rather than left to the model because a 4K desktop is otherwise largely illegible, and it is
paired with the brain's own `CORTEX_BODY_CAPTURE_MAX_EDGE=2048`: half the pair buys about half the
reading. One knob for two flags is deliberate
and measured: a picture is decoded as one non-causal chunk, llama.cpp asserts the micro-batch
covers it, and a raised budget without the micro-batch aborts `llama-server` with SIGSEGV on the
first oversized picture rather than answering an error. It hangs off the projector for the same
reason the projector hangs off its file: a text-only tier has no pictures, so it must not pay the
micro-batch's VRAM. What the default costs, how to refund it, and the failure boundary it still
leaves are in [docs/runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md).
`RosterError` is a boot-time misconfiguration. `build_supervisor(config)` wires the supervisor and
the probe client it owns (the three timing knobs are read off those two objects by a gated test,
because nothing else in the process observes them), `build_model_host(config)` is the composition
root, and `main()` serves it (`python -m cortex_model_manager`).

## Invariants

- **A request carries a logical id and nothing else.** No artifact path, argv, flag, port or layer
  count is readable from a body or a query, so the worst a compromised client can do is start and
  stop the tiers the deployment already declared in the daemon's own env. This is the security
  argument of decision 3: a docker socket or a compose-aware controller would hand the same client
  host-root, where a child-process supervisor's blast radius is its own container.
- **The roster is fixed at boot, and a tier with no artifact file is not in it.** No deep-model
  pick exists yet (ADR-0004) and the GPU-placed subagent is opt-in, so a stock host answers 404 for
  them rather than spawning a doomed process. Two tiers sharing a port is refused at boot.
- **`start` and `stop` are idempotent**, because a swap re-issues either without checking first.
  A start whose spawn fails adds nothing, so a tier that never ran still reads `STOPPED`; it also
  removes nothing, so a tier whose child had already died goes on reporting that child's exit code
  (`FAILED`) rather than being erased by the replacement that could not start. The spawn failure
  itself is what the `start` answers with, and the next successful start replaces the corpse.
- **`start` returns long before the model is ready.** It is a spawn and nothing more; the swap's
  health gate (`await_model_ready`) is the only thing that decides readiness. Blocking would put a
  minutes-long load at the mercy of an HTTP client's timeout instead of the plan's bound.
- **`stop` does not return until the child is dead and reaped.** `swap_in` stops the cortex and
  starts the deep model with nothing in between, so a still-dying cortex holding ~11 GB would
  CUDA-OOM the load. SIGTERM, then SIGKILL after `stop_grace_s`, then a bounded wait for the reap;
  a child that survives even SIGKILL raises `SupervisorError` and **keeps its slot**, because a
  process still holding VRAM must not be reported as gone.
- **`status` reads the process before it trusts the probe.** Measured: a child that fails to bind
  dies in ~0.24 s with exit code 1 while the *previous* model keeps answering 200 on that port, so
  a status that proxied `/health` alone would call the dead model READY and leave the old weights
  resident, silently defeating the swap. A child that exited unasked is `FAILED` (with its code in
  `detail`) until the next `start`, which replaces it.
- **One lock per logical model** serializes its three verbs, because a stop racing a start is what
  produces that bind failure. It is also why the probe's deadline is a term of a stop's worst case:
  a `status` holds that lock while it probes, and the compose healthcheck asks for one every 30 s
  on exactly the tier a handoff evicts first.
- **The daemon states its own worst case, and the brain refuses a deadline that cannot clear it.**
  `probe_timeout_s + stop_grace_s + reap_timeout_s` must sit strictly under the brain's
  `CORTEX_MODELHOST_TIMEOUT_S` (the shipped 5 + 10 + 30 under 60), or a control call times out on
  an eviction that was still working. The two sides are separate containers' env, so the rule is
  checked where they meet: `GET /health` reports all three, and the brain's composition root reads
  them once at boot and refuses to serve when the sum does not clear (ADR-0030's deadline-pairing
  addendum, `docs/runbooks/model-swap.md`).
- **The daemon configures the root logger, and every line names its subject.** `uvicorn.run`
  configures uvicorn's own loggers and leaves root alone, so `main` calls `logging.basicConfig` at
  `CORTEX_MODELHOST_LOG_LEVEL`; without it every INFO lifecycle record is dropped and the one
  WARNING that escapes goes through logging's last-resort handler. A plain stdlib formatter renders
  no `extra`, so each line carries its tier, pid and port **in the message** as well as in `extra`
  (the `LoggingAuditSink` pattern), because `docker logs model-host` is where the runbook sends an
  operator mid swap.
- **Children inherit the daemon's stdout/stderr and its process group.** No pipe means nothing can
  wedge when llama.cpp's loading log outruns a buffer nobody drains, and `docker logs model-host`
  shows the daemon and every child together. No new session means a container the runtime tears
  down takes the children with it, so no `llama-server` can outlive the container holding the GPU.
  Reaping needs no collector: asyncio's child watcher reaps on its own, which is what makes
  `returncode` authoritative for a child nobody awaited.
- **The daemon starts the cortex at boot**, so a stack that never escalates behaves as the
  always-on `llama-cortex` service did, and the argv it uses is asserted flag-for-flag against
  that service's `command` block.
- **A boot start that fails is logged and the API still serves.** Failing to come up would
  crash-loop under compose's restart policy and hide the cause.

## Deployment

The daemon runs as the `model-host` service in `docker/docker-compose.gpu.yml`, which it took over
from the always-on `llama-cortex` service: that service could not be stopped and started by a swap,
which is the whole point of decision 3. The consequences worth knowing before changing it:

- **Its own image, `brain/Dockerfile.modelhost`.** No existing image has both halves: the brain
  image has the workspace but no CUDA and no `llama-server`, and `llama.cpp:server-cuda` has the
  binary and a system `python3` but no pip, no ensurepip and no uv. So the CUDA server image is the
  base, `uv` is copied in as the static binary it is, and the workspace is installed against the
  image's **own** interpreter. Transplanting the brain image's prebuilt venv does not work: it
  points at `/usr/local/bin/python3.12`, which Ubuntu 24.04 does not have. `WORKDIR` is `/srv/brain`
  and not `/app`, because `/app` is where the base keeps the binary the supervisor spawns. Runs as
  uid 10001, and the base image's `llama-server` entrypoint is cleared.
- **The brain image still ships this package** (it imports `HttpModelHost`) and therefore ships the
  daemon's modules too, which nothing there runs. That costs nothing and breaks no argument: the
  blast radius of decision 3 is about the GPU reservation, the models mount, and the `llama-server`
  binary, none of which the brain container has.
- **The control API is not published.** ADR-0030 says compose-network-only, and on WSL2 a
  `127.0.0.1` publish is reachable from Windows' own localhost as well, so the default publishes
  only the cortex tier's `127.0.0.1:8080` (exactly as the old service did, keeping
  `just brain-inference-live` and the GPU runbook unchanged).
  `docker/docker-compose.modelhost-loopback.yml` is the opt-in override for host-side live tests,
  and it maps the two extra tiers to **different** host ports (9081, 9083) because their container
  ports are already published by `llama-embed` and `llama-subagent-qwen`.
- **The compose healthcheck asserts a tier that can serve a turn is READY**, not merely that the
  daemon answers, because `brain` gates on it: a control API answering while the cortex is still
  loading would let the brain serve a turn that fails at the backend. It accepts the cortex tier
  **or** the deep tier, because a handoff deliberately stops the cortex, and asserting the cortex
  alone marked a working escalation unhealthy for its whole duration. At cold boot only the cortex
  is started, so `depends_on` gates on exactly what it did before. The deep model's load window
  still reads unhealthy (nothing is serving then), which the runbook states as expected.
- **The cgroup caps are per container, so they are per supervisor and not per model.** ADR-0012
  asked for `--cpus`/`--memory`/`--memory-swap` on two `llama-server` sidecars; ADR-0030 collapsed
  the GPU one in here, so the cortex, the deep model and the GPU subagent are processes in ONE
  cgroup and no per-model CPU or RAM cap exists (`CORTEX_MODELHOST_{CPUS,MEMORY,MEMSWAP}` cap all
  three collectively). The values are user-tunable placeholders; note that llama.cpp mmaps the
  GGUF, so mapped model pages count against the memory cap and a cap below the artifact size makes
  a load thrash rather than fail.
- **`stop_grace_period` is 45 s**, above docker's default 10 s, because the shutdown sweep stops
  the tiers **one at a time** and a child with a request in flight pays the whole SIGTERM grace
  (measured: an idle `llama-server` exits in ~0.14 s, a busy one does not honour SIGTERM at all and
  is killed after the grace, 10.09 s end to end). Three tiers times a 10 s grace plus slack is the
  arithmetic. A child that survives even SIGKILL is deliberately outside it: the runtime then kills
  the container, which takes its children with it (measured), so nothing leaks either way and the
  period only buys the clean path.

## Testing

- The shared `ModelHost` contract suite (`tests/model_host_contract.py`, `ALL_CHECKS`) runs over
  **both** implementations (`tests/test_model_host_contract.py`): the core's `ScriptedModelHost`,
  and the real `HttpModelHost` talking to a real `ModelSupervisor` through a real Starlette app over
  `httpx.ASGITransport`. Only the OS spawn and the health socket are faked. The port's vocabulary
  needs three conditions of the world no verb can create (a model not serving yet, a process dying
  unasked, and what the card reports), so each fixture supplies them as knobs: that is the honest
  widening of the contract, since "`start` only begins loading" is unobservable in an
  implementation where nothing can be mid-load, and neither implementation may invent a GPU.
- 100% line + branch, with no process spawned and no socket opened. Every distrust-green mutation
  is recorded with its **measured** package-wide failure count in the suites' own docstrings.
- `integration`-marked live tests (`tests/test_model_host_live.py`, excluded from CI and the
  coverage gate, run by `just brain-modelhost-live`): the real signal escalation against real child
  processes (a `sleep`, and one that traps SIGTERM), and the whole mechanism against a running
  sidecar at `CORTEX_MODELHOST_ENDPOINT`. **The mechanism is validated**, agent-side in Docker on
  the dev GPU with two small artifacts standing in for the tiers: real processes started,
  health-gated, evicted, swapped, killed under the daemon, and restarted over their own corpses,
  with the exact commands, timings and VRAM readings in
  [runbooks/model-swap.md](../runbooks/model-swap.md). The fit check has its own two live cases,
  added 2026-08-07 and run on the 24 GB card: that a real sidecar reports a card at all (which no
  gated test can reach, the brain container having none), and that one call refuses a megabyte more
  than the card has free while the same call for exactly what is free goes through and really
  loads. **Tier scale was validated 2026-08-07** on that card and is written up in the same
  runbook; the earlier mechanism runs were on an 8 GB dev GPU that could not hold the real cortex
  beside a deep model.

## Dependencies

cortex-core (the `ModelHostState` enum, shared by both halves so the wire's four words cannot
drift, `DeviceMemory` for the same reason, and `ModelHostError` for the adapter), httpx (the control client and the health probe),
starlette + uvicorn (the control API), pydantic-settings (the env surface). The brain's composition
root (`cortex_orchestrator.swap_builders`) injects the endpoint and a bounded `httpx.AsyncClient`;
the sidecar's own root is `server.build_model_host`.
