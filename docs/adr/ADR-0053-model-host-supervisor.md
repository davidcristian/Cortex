# ADR-0053: The model host supervisor

**Status:** Accepted (2026-08-11)

## Context

[ADR-0030](ADR-0030-brain-handoff.md) decision 3 puts model process lifecycle behind the `ModelHost`
port and chooses a supervisor sidecar as its real mechanism: one container holding the GPU
reservation and the read-only models mount, whose daemon starts and stops one `llama-server` child
per logical model. The Docker API from the brain and a compose-driving controller were rejected
there, both for putting host root within reach of the process that runs model-influenced code.

This record decides how that sidecar and its adapter are built: what a status means, how a stop is
bounded, what the control API exposes, how the brain notices the daemon was replaced, and how a tier
the host never had is told apart from a host that failed. The package is `cortex_model_manager`
([brain-model-manager](../modules/brain-model-manager.md)): the daemon (`supervisor.py`, `api.py`,
`server.py`) and the brain's `HttpModelHost` adapter (`adapter.py`) in one package, because the
adapter imports `cortex_core`'s state words and errors and so keeps both sides of the wire on one
vocabulary. They run in different containers and never import each other.

## Decision

### The daemon

1. **A fixed roster from the daemon's own environment.** Each tier (`cortex`, `brain`,
   `subagent-gpu`) is a logical id with a fixed port (`:8080`, `:8081`, `:8083`) and an argv built
   from its `CORTEX_MODEL_FILE_*`, `CORTEX_NGL_*` and `CORTEX_CTX_SIZE_*` settings. Nothing in a
   request can add a model or change an argv, since a request-supplied argv would be code execution
   in the GPU container. A tier with no artifact file is not in the roster, and every verb on it
   answers `404 unknown model`; `build_roster` refuses two tiers on one port at startup. The
   lifespan starts the boot model, the cortex, so a stack that never escalates behaves as a
   single-model server.
2. **A status reads the child's exit code before it probes.** A second `llama-server` on a port an
   existing one still holds dies at once with `couldn't bind HTTP server socket`, while `/health` on
   that port keeps answering from the existing one; a status that only probed would report the dead
   start `READY` and the old weights would serve under the new name. A child that exited unasked is
   `FAILED` with its code in `detail` until the next `start` replaces it. `start` returns once the
   process is spawned, so a loading tier is `LOADING` and the health check is the only readiness
   authority.
3. **`stop` returns only once the child is reaped**, because a swap starts the next model at once
   and a still-dying tier holding its VRAM would make the load run out of memory. SIGTERM, then
   SIGKILL after `CORTEX_MODELHOST_STOP_GRACE_S` (10 s), then a reap limit of
   `CORTEX_MODELHOST_REAP_TIMEOUT_S` (30 s). The grace is not slack: a tier with a request in flight
   (`--parallel 1`) ignores SIGTERM and is killed after the whole grace, so the grace must not be
   tuned down on the strength of an idle stop ([model swap](../readings/model-swap.md)). The
   container's `stop_grace_period` is 45 s, sized for the shutdown pass's sequential stops.
4. **One lock per logical model serializes start, stop and status**, and a status probes inside it
   (`CORTEX_MODELHOST_PROBE_TIMEOUT_S`, 5 s). Probing outside the lock was rejected: it could report
   `READY` for a tier a concurrent stop had already ended. asyncio's child watcher reaps every
   child, so `returncode` is authoritative for one nobody awaited; children share the daemon's
   process group, so killing the daemon ends them; they inherit its stdout and stderr, so a failed
   child's reason is in `docker logs` and the API's `detail` has the exit code.
5. **The daemon configures the root logger** through the shared `configure_logging`, since
   `uvicorn.run` leaves root alone and every lifecycle line was otherwise dropped. The control API's
   refusal line takes its level from the status code (a 4xx asks after a tier this daemon never had,
   a 5xx is a thing it accepts and cannot do), not from being the only record: every brain-side
   caller also logs the sentence, the swap in through the failed handoff's settle line
   ([ADR-0051](ADR-0051-log-line-rendering.md) decisions 7 and 8).

### The control API and the container

6. **Four routes, on the compose network only**: `GET /health`, `GET /models/{model}`, and
   `POST /models/{model}/start` and `/stop`, on `:9300`. The API starts and stops processes in the
   container holding the GPU, and on WSL2 a `127.0.0.1` publish is reachable from Windows' localhost
   too, so the gpu overlay publishes only the cortex's `127.0.0.1:8080`, as the service it replaced
   did. `docker/docker-compose.modelhost-loopback.yml` is the opt-in override for host-side tests;
   it maps the control API and the other two tiers to host ports 9300, 9081 and 9083, because
   `:8081` and `:8083` are already published by `llama-embed` and `llama-subagent-qwen`.
7. **The container is healthy when the cortex tier or the deep tier is `READY`.** A rule about the
   cortex alone marked a working handoff unhealthy for as long as it ran, and the runbook then sent
   the operator to start the cortex onto a card the deep model held. At cold boot the daemon starts
   only the cortex, so the brain's `depends_on: service_healthy` waits on what it always did. The
   deep model's own load window reads unhealthy, because nothing serves then.
8. **The image** (`brain/Dockerfile.modelhost`) builds on `ghcr.io/ggml-org/llama.cpp:server-cuda`,
   copies the static `uv` binary in and installs the workspace against the base's `/usr/bin/python3`
   (the brain image's venv points at an interpreter Ubuntu 24.04 does not have). `WORKDIR` is
   `/srv/brain`, since `/app` holds the `llama-server` the daemon spawns, and the base entrypoint is
   cleared.
9. **cgroup caps are per supervisor, not per model**: the cortex, the deep model and the GPU
   subagent are processes in one cgroup under `CORTEX_MODELHOST_{CPUS,MEMORY,MEMSWAP}`. A per-model
   cap needs a container per model, which needs something that can start containers, which is what
   ADR-0030 rejected. llama.cpp maps the GGUF, so mapped pages count against the memory cap and a
   cap below the artifact size makes a load thrash rather than fail.

### The brain's side of the wire

10. **`HttpModelHost` is selected by `CORTEX_MODELHOST_BACKEND=supervisor`**, which requires
    `CORTEX_MODELHOST_ENDPOINT` or startup fails. `CORTEX_MODELHOST_TIMEOUT_S` (60 s) bounds one
    whole control call, a real deadline, unlike the generation clients' per-read stall ceiling: a
    control call streams nothing. A momentarily unreachable host raises `ModelHostError` with no
    retry, so the swap fails safe and restores. `SwapRuntime.close` releases the control client with
    the store.
11. **The deadline must clear the worst stop, and the brain checks it at startup.** A `stop` can
    take the grace plus the reap limit plus a queued status's probe, so the rule is
    `probe + grace + reap < CORTEX_MODELHOST_TIMEOUT_S` (5 + 10 + 30 = 45 against 60 shipped). The
    daemon publishes all three on `GET /health`; `ControlBounds` holds them, with
    `worst_case_stop_s` their sum and `clears(deadline)` strict. `ModelHost.control_bounds()` reads
    them, and `check_control_deadline` (`swap_builders.py`) refuses startup with
    `ControlDeadlineError` naming every term when an answer does not clear the plan's
    `control_deadline_s`. Only an answered mismatch refuses: an unreachable host is logged at
    warning and a host with no bounds at info, keeping startup's dependency on the sidecar tolerant.
    The environment is static under a container, so one reading answers for the process; a mispaired
    deadline aborts only the evictions of busy tiers, so it is refused up front rather than found in
    a handoff. A test reads both containers' shipped defaults and asserts they clear, since a sum of
    three under a fourth is not a registry coupling.
12. **A boot id tells the brain the daemon was replaced.** `ModelSupervisor` mints `uuid4().hex` at
    construction and `GET /health` returns it; `ModelHost.boot_id()` reads it, and an empty or
    non-string value is no answer. It is compared for equality only: a counter restarts at the
    number the comparison exists to notice, and a restarted sidecar is pid 1 at the same address
    with the same environment. The brain's half, `BootWatch` (`residency_watch.py`), records the
    first value at the boot publish and observes at the top of the swap in, inside the residency
    scope and before anything is evicted. A first answer is a starting point, never a change,
    because converging bounces every evictable tier. A replacement rebuilds residency through
    `converge_residency` and publishes what it saw (refusing the handoff when the cortex cannot be
    settled), then re-reads `control_bounds()` and refuses when the deadline no longer clears. Every
    unanswered question does nothing.
13. **The card is read by the daemon** through `nvidia-smi` behind a `DeviceMemoryProbe`
    (`CORTEX_MODELHOST_NVIDIA_SMI`); the NVIDIA toolkit injects the binary exactly where a GPU is
    reserved. `GET /health` returns `device_free_mib` and `device_total_mib`, and
    `ModelHost.device_memory()` answers `None` for a host that sees no card, including more than one
    visible GPU, since nothing downstream knows which card a model is placed on. Its one caller is
    the fit check of [ADR-0055](ADR-0055-co-residency-and-spill-watch.md).
14. **`ModelNotHostedError(ModelHostError)` is a 404 on a per-model route and nothing else.** A 503
    is a process that would not start or stop, and a 404 on `/health` means the endpoint is wrong.
    It is a subclass, so every existing `except ModelHostError` still catches it and only a caller
    that can act on the difference names it; the name avoids the daemon's own `UnknownModelError`
    and the subagent roster's word. The port's other failures (transport, refusal, undecodable body,
    unknown state word) stay one type, since each means the host did not answer.
15. **Hosting the GPU subagent tier and routing to it are separate settings.** Opting in is three
    together: `CORTEX_MODEL_FILE_SUBAGENT_GPU` puts it in the roster,
    `CORTEX_SUBAGENTS_GPU_ENDPOINT=http://model-host:8083` routes GPU-placed spawns to it, and its
    id in `CORTEX_SWAP_EVICT_MODELS` has a handoff stop it. The endpoint defaults to the CPU
    subagent server, so a deployment with no GPU artifact never routes spawns at a tier that answers
    nothing.

## Consequences

- The fields on `GET /health` (roster, the three bounds, the two device figures, the boot id) are
  JSON keys written by the daemon and the adapter and named as constants by neither, so the shared
  `ModelHost` contract suite, which drives the real adapter against a real supervisor behind a real
  Starlette app, is what ties them together.
- The sidecar holds no secrets, and nothing it exposes leaves the compose network unless the
  loopback override is layered.
- No per-model CPU or RAM cap exists; the caps ship as placeholders a deployment measures.
- The brain notices a replaced daemon only at a handoff or a startup; between them, only the
  baseline residency pass reads the machine ([ADR-0054](ADR-0054-baseline-residency.md)).

## Alternatives rejected

- **A generation counter for the daemon's identity**: it resets to the value the comparison exists
  to catch.
- **Guessing "no such tier" from a message string**: a genuine outage would read as a configuration
  note, the worse direction to be wrong in.
- **Reading every refusal as a missing tier**, for the same reason.
- **Publishing the control API on loopback by default**, as the other sidecars do: it controls the
  processes on the GPU container, and loopback on WSL2 includes Windows.

## Related

[brain-model-manager](../modules/brain-model-manager.md), [model-swap](../runbooks/model-swap.md),
[llamacpp-gpu](../runbooks/llamacpp-gpu.md), [model swap](../readings/model-swap.md),
[ADR-0030](ADR-0030-brain-handoff.md), [ADR-0054](ADR-0054-baseline-residency.md),
[ADR-0012](ADR-0012-resource-governance.md) (the host half of the resource caps),
[ADR-0051](ADR-0051-log-line-rendering.md).
