# brain/packages/model_manager (`cortex_model_manager`)

**Purpose.** The real half of the process-lifecycle port (ADR-0030 decision 3): a supervisor daemon
that starts and stops one `llama-server` child per logical model, plus the `ModelHost` adapter the
brain drives it with. One package with two halves that run in **different containers** and never
import each other. The **daemon** runs in the `model-host` sidecar, the container that holds the GPU
device reservation and the read-only models mount, and is the only thing in the system that can
start or kill a model process. The **adapter**, `HttpModelHost`, runs in the CPU-only brain
container and talks to the daemon's HTTP control API; it knows nothing about processes. Killing a
child loses nothing, because every model instance is stateless and disposable (ADR-0005 decision 3),
which is the premise the one hard rule rests on.

## The adapter, on the brain side

`HttpModelHost(endpoint: str, client: httpx.AsyncClient)` is a `ModelHost`: `start`, `stop` and
`status` take a logical model id and nothing else, and `device_memory()`, `control_bounds()` and
`boot_id()` take none. The client is injected, and unlike the generation clients it must have a real
read deadline, since a control call that hung would hang a swap step under no bound at all.

- `start(model)` POSTs `/models/{id}/start`, `stop(model)` POSTs `/models/{id}/stop`, and
  `status(model)` GETs `/models/{id}` and returns the `ModelHostState` the reply names. The id is
  percent-escaped, so it is a name and never a path fragment.
- `device_memory()` GETs `/health` and returns `DeviceMemory(free_mib, total_mib)`, or `None` when
  either figure is missing or is not an integer, which is what a daemon with no card reports. That
  route is chosen because it takes no per-model lock: a swap asks this between an eviction and a
  load, where queueing behind a stop would add that stop's whole grace to the answer.
- `control_bounds()` GETs the same route and returns
  `ControlBounds(probe_timeout_s, stop_grace_s, reap_timeout_s)`, or `None` when any one of the
  three is missing, is not a number, is a bool, or is negative. A partial answer is discarded,
  because a sum missing one term can clear a deadline that the complete sum does not (ADR-0053
  decision 11). The root reads it once at wiring time, and a swap again when the daemon changed.
- `boot_id()` GETs the same route and returns the value the daemon gives its own boot, or `None` for
  a missing, empty or non-string one. It is read at the boot publish and once per handoff before
  anything is evicted, and compared for equality only: a different value means everything the brain
  recorded about what is resident was recorded against a supervisor process that no longer exists
  (ADR-0053 decision 12).
- Every failure crosses as `ModelHostError` with its cause chained, and **nothing is retried here**:
  a transport failure, a 503, a body that will not decode, and an unrecognized state word all mean
  the model host did not answer the question, which is for the swap to interpret.
- One failure crosses more narrowly: a **404 on a per-model route** is the supervisor's
  `UnknownModelError`, so the adapter raises `ModelNotHostedError`, the port's subclass meaning this
  host serves no such id and will not while this daemon runs (ADR-0053 decision 14). A 404 on
  `/health` says the endpoint is wrong rather than the roster short, and a 503 stays broad because a
  process that would not start or stop may answer differently on the next call. A `FAILED` state is
  a normal answer, logged at error level with the sidecar's `detail`, because that exit code is the
  only diagnosis the brain side ever sees.

## The control API, on the sidecar side

`build_app(supervisor, *, boot_model, close=nothing_to_close, device=None)` returns the Starlette
app and `model_host_lifespan(supervisor, boot_model, close)` is its lifespan. `device` is the
`DeviceMemoryProbe` the health route reads the card through. Four routes and no more:

| Route | Meaning |
|---|---|
| `GET /health` | the daemon is up, which boot of it this is, the roster it serves, the three bounds one control call may spend, and how much of the card is free (`{"status": "ok", "boot_id": "0f9c...", "models": [...], "probe_timeout_s": 5.0, "stop_grace_s": 10.0, "reap_timeout_s": 30.0, "device_free_mib": 22484, "device_total_mib": 24463}`). It is the only way to read what a running daemon actually got. All three timing terms are reported, because the brain reads them here at wiring time and refuses to start when its own `CORTEX_MODELHOST_TIMEOUT_S` does not clear their sum (ADR-0053 decision 11), and because a reader given two of them could tune to a compliant-looking sum the third exceeds. `boot_id` is the one field a restart changes. The two device figures are `null` on a daemon that can see no card, and they are what the brain's fit check compares against (ADR-0055 decision 2). |
| `GET /models/{id}` | `{"model", "state", "detail"}`, where `state` is `stopped`, `loading`, `ready` or `failed`. |
| `POST /models/{id}/start` | begin loading it (idempotent), answering the state it replaced. |
| `POST /models/{id}/stop` | end it, returning once the child is reaped (idempotent). |

An id outside the roster is **404** and a supervisor failure is **503**.
[docs/runbooks/model-swap.md](../runbooks/model-swap.md) handles each in a different section. **The
log level follows the status code**, so both refusals share the one searchable sentence
`a model-host request failed`, with the 5xx at `ERROR` and the 4xx at `WARNING`. The refusal's own
words go in the `error` field, raised by the supervisor rather than also printed there.

`DeviceMemoryProbe` is `read() -> DeviceMemory | None`, with two implementations: `NoDeviceMemory`
(always `None`, the default and what a CPU-only stack truthfully has) and
`NvidiaSmiMemory(binary, timeout_s)`, one bounded
`nvidia-smi --query-gpu=memory.free,memory.total --format=csv,noheader,nounits`. The binary comes
from `CORTEX_MODELHOST_NVIDIA_SMI` and the bound from `CORTEX_MODELHOST_PROBE_TIMEOUT_S`. **Every
way it can go wrong produces no reading rather than an exception**: a missing binary (the normal
case where no GPU is reserved), a non-zero exit, a body that will not parse, and **more than one
visible GPU**, where nothing downstream can tell which card a model would load onto.

## The supervisor

`ModelSupervisor(roster, processes, probe, *, stop_grace_s, reap_timeout_s, probe_timeout_s)` sits
over two ports, `ChildProcesses` (`spawn(argv) -> ChildProcess`) and `HealthProbe`
(`serving(url) -> bool`), with `AsyncioChildProcesses` and `HttpHealthProbe` as the real adapters
and `ModelStatus(model, state, detail)` as its answer. `stop_all()` is the shutdown pass. `boot_id`
is a `uuid4().hex` minted per daemon process, which `GET /health` publishes and nothing here reads
back; it is random rather than counted, since a counter would restart at the number a reader
compares against. `control_bounds` returns the `ControlBounds` it was wired with. It is given the
probe's deadline although it spends none of it: that bound belongs to the client behind `probe`, and
a `status` probes inside the same per-model lock a `stop` takes. The defaults are
`DEFAULT_STOP_GRACE_S` (10 s), `DEFAULT_REAP_TIMEOUT_S` (30 s) and `DEFAULT_PROBE_TIMEOUT_S` (5 s),
each overridable by the environment variable of the same name.

## The roster

`ModelHostConfig` (environment only) builds `TierArgs` values, `tier_spec` turns each into a
`ModelSpec(model, port, argv)` through `llama_server_argv`, and `build_roster` indexes them. **Its
defaults are module constants rather than literals inside the `Field(...)` calls** (`DEFAULT_NGL`,
`DEFAULT_CORTEX_CTX_SIZE`, `DEFAULT_BRAIN_CTX_SIZE`, `DEFAULT_SUBAGENT_CTX_SIZE`,
`DEFAULT_SUBAGENT_PARALLEL`, `DEFAULT_IMAGE_MAX_TOKENS`, `DEFAULT_NVIDIA_SMI`, beside
`DEFAULT_CORTEX_FILE` and the two tier ids), because the GPU override states every one of them again
as a substitution default and always sets the variable: the substitution is what a composed
deployment runs and the Python default is what it only appears to run. `scripts/crosscheck.py`
compares the two, so retune both or neither. `RosterError` is a boot-time misconfiguration.
`build_supervisor(config)` wires the supervisor and the probe client it owns, and
`build_model_host(config)` is the composition root that `main()` serves
(`python -m cortex_model_manager`). The settings that change a tier's argv:

- `CORTEX_MODEL_FILE_CORTEX_MMPROJ` (ADR-0029) adds llama.cpp's `--mmproj` pair to the **cortex**
  tier, which is the whole of the vision wiring on this side: the projector loads beside the model
  and the brain discovers the capability from the running server's `/props` rather than from a
  second flag here that could disagree with it. Empty, the default, starts the tier text-only.
- `CORTEX_IMAGE_MAX_TOKENS` decides how much of a screen survives the downscale. A positive value,
  `1024` by default, emits `--image-max-tokens N` **and** `--ubatch-size max(N, 512)`; zero hands
  the budget back to the model and emits neither flag. The default is raised because a 4K desktop is
  otherwise largely illegible, and it is paired with the brain's own
  `CORTEX_BODY_CAPTURE_MAX_EDGE=2048`: half the pair buys about half the reading. One setting for
  two flags is deliberate and measured: a picture is decoded as one non-causal chunk, llama.cpp
  asserts that the micro-batch covers it, and a raised budget without the micro-batch ends
  `llama-server` with SIGSEGV on the first oversized picture rather than answering an error. It is
  conditioned on the projector, so a text-only tier does not pay the micro-batch's VRAM. Costs and
  how to lower them are in [docs/runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md).
- `CORTEX_REASONING_BUDGET`, and `CORTEX_REASONING_BUDGET_BRAIN` for the deep tier, adds llama.cpp's
  `--reasoning-budget N`, which sets how long a thought may be rather than whether one happens.
  `-1`, the default, is the engine's own word for unrestricted and emits **no flag at all**; `0` is
  a real setting (thinking ends at once) and does reach the argv, which is why the sentinel cannot
  be the falsy value the image budget uses. It lives in `_UNRESTRICTED_REASONING`, which
  `scripts/crosscheck.py` reads under its underscore, and it is per tier because llama.cpp accepts
  it per server only, measured. The GPU-placed subagent tier has no setting of its own but does get
  the flag, at a fixed `0` inside `_REASONING_OFF` beside the template argument, which alone was
  measured not to stop the trace under a `response_format` (ADR-0049).
- `--cache-ram` is set per tier and is not a deployment setting. It sizes the prompt cache the
  engine keeps in host RAM for a conversation whose slot has been taken; because the tiers' weights
  are mmapped in the same cgroup, a cache that grows reclaims the GGUF a server reads from. Each
  tier's size is the one it was measured at ([ADR-0059](../adr/ADR-0059-prompt-cache-per-tier.md),
  readings in [prompt cache](../readings/prompt-cache.md)): `8192` on the cortex, where a cached
  conversation costs 1349 MiB and every return was restored at 1.9 s a request; `0` on the deep
  tier, where a conversation costs 3526 MiB and the engine's own ceiling holds two of three; `0` on
  the GPU-placed subagent tier, whose subtasks are one-shot.
- `CORTEX_MODEL_FILE_BRAIN_DRAFT` names the deep tier's multi-token-prediction drafter (ADR-0004
  decision 14), resolved under the models mount like every other artifact. Empty, the default, emits
  nothing. A named file appends `--model-draft PATH --spec-type draft-mtp`, the four items built
  together by `drafter_flags` in `tiers.py`, because the path alone was measured to load the drafter
  and then draft nothing. It reaches the argv through the tier's `extra`, as the projector does,
  rather than through a field of its own on `TierArgs`: `scripts/hostedtiers.py` reads
  `llama_server_argv` as one fixed run of items with exactly one splat. The drafter costs 997 to
  1020 MiB more on the card, which is what `CORTEX_SWAP_BRAIN_VRAM_MIB` grows by and why a
  deployment naming it evicts the GPU subagent tier.

## Invariants

- **A request names a logical id and nothing else.** No artifact path, argv, flag, port or layer
  count can be read out of a body or a query, so the worst a compromised client can do is start and
  stop the tiers the deployment already declared in the daemon's own environment. That is the
  security argument of ADR-0030 decision 3 against a docker socket or a compose-aware controller.
- **The roster is fixed at boot, and a tier with no artifact file is not in it.** The deep tier and
  the GPU-placed subagent are opt-in, so a stock host answers 404 for them. Two tiers sharing a port
  fails at boot.
- **`start` and `stop` are idempotent**, because a swap re-issues either without checking first. A
  start whose spawn fails adds nothing, so a tier that never ran still reads `STOPPED`; it removes
  nothing either, so a tier whose child had already died goes on reporting that child's exit code
  (`FAILED`) rather than being erased by a replacement that could not start.
- **`start` returns long before the model is ready.** The swap's readiness check
  (`await_model_ready`) is the only thing that decides readiness; blocking would bound a
  minutes-long load by an HTTP client's timeout instead of by the plan's own bound.
- **`stop` does not return until the child is dead and reaped.** `swap_in` stops the cortex and
  starts the deep model with nothing in between, so a still-dying cortex holding about 11 GB would
  CUDA-OOM the load. SIGTERM, then SIGKILL after `stop_grace_s`, then a bounded wait for the reap; a
  child that survives even SIGKILL raises `SupervisorError` and **keeps its slot**, because a
  process still holding VRAM must not be reported as gone.
- **`status` reads the process before it reads the probe.** Measured: a child that fails to bind
  dies in about 0.24 s with exit code 1 while the *previous* model keeps answering 200 on that port,
  so a status that only proxied `/health` would report the dead model READY and leave the old
  weights resident, defeating the swap with no error anywhere.
- **One lock per logical model** serializes its three verbs, because a stop racing a start is what
  produces that bind failure, and it is why the probe's deadline is a term of a stop's worst case.
- **The daemon states its own worst case, and the brain refuses to start on a deadline that cannot
  clear it.** `probe_timeout_s + stop_grace_s + reap_timeout_s` must sit strictly under the brain's
  `CORTEX_MODELHOST_TIMEOUT_S` (the shipped 5 + 10 + 30 under 60), or a control call times out on an
  eviction that was still working. The two sides are separate containers' environment, so the rule
  is checked where they meet (ADR-0053 decision 11).
- **The daemon configures the root logger.** `uvicorn.run` configures uvicorn's own loggers and
  leaves root alone, so `main` calls `cortex_core.configure_logging` at `CORTEX_MODELHOST_LOG_LEVEL`
  and `CORTEX_MODELHOST_LOG_FORMAT` (`plain`, or `packed` for one JSON object per line); without it
  every INFO lifecycle record is dropped and no line's `extra` reaches the line. Each message is a
  constant sentence with its tier, pid and port as fields beside it
  ([ADR-0051](../adr/ADR-0051-log-line-rendering.md) decision 5):
  `started a model process model=cortex pid=8 port=8080`.
- **Children inherit the daemon's stdout and stderr and its process group.** No pipe means nothing
  can wedge when llama.cpp's loading log outruns a buffer nobody drains. No new session means a
  container the runtime tears down takes the children with it, so no `llama-server` outlives the
  container holding the GPU. Reaping needs no collector: asyncio's child watcher reaps on its own.
- **The daemon starts the cortex at boot**, so a stack that never escalates behaves as the always-on
  `llama-cortex` service did. A boot start that fails is logged and the API still serves, since
  failing to come up would crash-loop under compose's restart policy and hide it.

## Deployment

The daemon runs as the `model-host` service in `docker/docker-compose.gpu.yml`, which it took over
from the always-on `llama-cortex` service.

- **Its own image, `brain/Dockerfile.modelhost`.** No existing image has both halves: the brain
  image has the workspace but no CUDA and no `llama-server`, and `llama.cpp:server-cuda` has the
  binary and a system `python3` but no pip, no ensurepip and no uv. So the CUDA server image is the
  base, `uv` is copied in as the static binary it is, and the workspace is installed against the
  image's **own** interpreter, the brain image's prebuilt venv pointing at a
  `/usr/local/bin/python3.12` Ubuntu 24.04 does not have. `WORKDIR` is `/srv/brain`, `/app` being
  where the base keeps the binary the supervisor starts. It runs as uid 10001 with the base image's
  entrypoint cleared.
- **The control API is not published.** ADR-0030 says compose network only, and on WSL2 a
  `127.0.0.1` publish is reachable from Windows' own localhost too, so the default publishes only
  the cortex tier's `127.0.0.1:8080`. `docker/docker-compose.modelhost-loopback.yml` is the opt-in
  override for host-side live tests, and it maps the two extra tiers to **different** host ports
  (9081, 9083) because their container ports are already published by `llama-embed` and
  `llama-subagent-qwen`.
- **The compose healthcheck requires that a tier which can serve a turn is READY**, not merely that
  the daemon answers, because `brain` waits on it. It accepts the cortex tier **or** the deep tier,
  because a handoff deliberately stops the cortex. The deep model's load window reads unhealthy.
- **The cgroup caps are per container, so they are per supervisor and not per model.**
  `CORTEX_MODELHOST_{CPUS,MEMORY,MEMSWAP}` cap all three tiers together and are user-tunable
  placeholders. llama.cpp mmaps the GGUF, so mapped model pages count against the memory cap and a
  cap below the artifact size makes a load thrash rather than fail.
- **`stop_grace_period` is 45 s**, above docker's default 10 s, because the shutdown pass stops the
  tiers **one at a time** and a child with a request in flight pays the whole SIGTERM grace.
  Measured: an idle `llama-server` exits in about 0.14 s, while a busy one does not honour SIGTERM
  at all and is killed after the grace, 10.09 s end to end. Three tiers times a 10 s grace plus
  slack is the arithmetic. A child surviving SIGKILL is outside it, the runtime then killing the
  container and its children (measured).

## Testing

The shared `ModelHost` contract suite (`tests/model_host_contract.py`, `ALL_CHECKS`) runs over
**both** implementations in `tests/test_model_host_contract.py`: the core's `ScriptedModelHost`, and
the real `HttpModelHost` talking to a real `ModelSupervisor` through a real Starlette app over
`httpx.ASGITransport`. Only the OS spawn and the health socket are faked. The port's vocabulary
needs three conditions of the world that no verb can create (a model not serving yet, a process
dying unasked, and what the card reports), so each fixture supplies them as settings, and a fourth,
`unhosted`, is an id the host does not serve. Coverage is 100% line and branch, with no process
started and no socket opened.

The `integration`-marked `tests/test_model_host_live.py` (excluded from CI and the coverage check,
run by `just brain-modelhost-live`) covers the real signal escalation against real child processes
and the whole mechanism against a running sidecar at `CORTEX_MODELHOST_ENDPOINT`. **The mechanism is
validated** in Docker on the dev GPU with two small artifacts in place of the tiers, and **tier
scale was validated 2026-08-07** on the 24 GB card; both runs, with their commands, timings and VRAM
readings, are in [runbooks/model-swap.md](../runbooks/model-swap.md), along with the fit check's two
live cases: a real sidecar reporting a card at all, and a call asking a megabyte more than the card
has free being rejected while the same call for exactly what is free really loads.

**Dependencies.** cortex-core (the `ModelHostState` enum, shared by both halves so the four wire
words cannot disagree, `DeviceMemory` for the same reason, and `ModelHostError`), httpx, starlette
and uvicorn (the control API), and pydantic-settings. The brain's composition root
(`cortex_orchestrator.swap_builders`) injects the endpoint and a bounded `httpx.AsyncClient`; the
sidecar's own root is `server.build_model_host`.
