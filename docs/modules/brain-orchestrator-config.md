# brain/packages/orchestrator: configuration

The environment the brain process reads, and the boot checks that compare one setting against
another. The service these values wire up is in [brain-orchestrator.md](brain-orchestrator.md).

## Configuration

Every class is pydantic-settings, read only by the composition root; explicit constructor arguments
beat the environment, and anything invalid fails at boot. Each class declares its own fields, so
what follows is the prefix, the defaults other parts depend on, and the validation.

- `SeamServerConfig`, prefix `CORTEX_SEAM_`: `host: str = DEFAULT_SEAM_HOST`
  (`127.0.0.1`, `CORTEX_SEAM_HOST`; the compose stack sets `0.0.0.0` so the published port can
  reach the server), `port: int = DEFAULT_SEAM_PORT` (50051, `CORTEX_SEAM_PORT`) and a
  `bind_address` property. The body dials `CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:50051`),
  and `DEFAULT_SEAM_PORT` is module-level so `scripts/crosscheck.py` can compare it with every
  other place the port appears. `token` (`CORTEX_SEAM_TOKEN`, ADR-0016) is the shared secret: set,
  every RPC must present matching `x-cortex-seam-token` metadata. `converse_buffer: int = 256`
  bounds how many `ServerEvent`s one stream buffers unread, and `confirm_timeout_s: float = 120.0`
  (ADR-0022) how long a confirmable call waits for the user.
- `BrainRuntimeConfig` has no prefix of its own. `redis_url` (`CORTEX_REDIS_URL`) and
  `cortex_model` (`CORTEX_MODEL_CORTEX`, default `cortex`, a logical id per ADR-0004) are the two
  addresses; `test_wiring` drives every reader of the second over a renamed tier (ADR-0068
  decision 9). `vram_soft_cap_gb: float = 14.0` and `cortex_reservation_gb: float = 8.6` are the
  GPU budget the `SubagentPlacer` fit-tests against, re-measured 2026-08-07: the shipped tier peaks
  at 8573 MiB above the desktop's own floor, leaving 5.4 GiB of subagent headroom (ADR-0012
  decision 14). `history_char_budget: int = 48000` (`0` turns windowing off),
  `history_summary: bool = True` (ADR-0038 decision 20; a fold decodes 61 to 163 tokens and costs
  2.9 s to 6.2 s) and `history_recap_min_chars: int = 2000`, clamped to the budget by the builder,
  size the history one turn sends. `output_guardrail = "redact"` (ADR-0015) is one of `redact`,
  `lookalike` (every non-ASCII host on a tainted turn, measured at 0 of the Tranco top 1,000 hosts
  and 1,441 of the top million), `strict` and `off`, and `generate_titles: bool = False` opts into
  brain-generated switcher titles (ADR-0021 decision 9).
- `InferenceConfig`, prefix `CORTEX_INFERENCE_` (ADR-0007): `backend: "echo" | "llamacpp" =
  "echo"`, echo being the GPU-less default for CI and dev, with `endpoint` required for the other.
  `vision: VisionMode = DEFAULT_VISION_MODE` (`"auto"`; `CORTEX_VISION`, a bare name rather than
  the prefix, ADR-0029) decides whether `capture_screen` is advertised, `auto` probing the running
  server, while `trace_lever = "auto"` (ADR-0049) decides whether a request may include
  `GenerationBounds.trace_tokens`
  as llama.cpp's `reasoning_budget_tokens`: it is settled once at wiring, being a property of the
  binary rather than of the running child. `stall_timeout_s: float = 120.0` (ADR-0005 decision 7)
  is how long this tier's stream may send nothing, a gap between chunks rather than a cap on the
  generation, sized from the worst measured time to first token (17.5 s contended).
- `MemoryConfig`, prefix `CORTEX_MEMORY_` (ADR-0008): a `pgvector` backend needs a DSN and an
  embedder endpoint, and the DSN's authority must be one the Postgres driver can read
  (`authority_is_readable`, `dsn.py`, ADR-0051 decision 11); both refusals raise
  `MemoryConfigError` rather than `ValueError`, Pydantic otherwise rendering the DSN. `scope`,
  `on_tainted` (ADR-0019) and `recall` pick core policies through `recall_policy_from_config` and
  `recall_audit_from_config`. `recall` defaults to `judge` (ADR-0038 decision 7), which costs
  0.877 s on its own and 0.515 s of a recalling turn's time to first token and is the only value
  under which a recall may return nothing; `recall_half_life_days` (30), `recall_recency_weight`
  (0.3), `recall_dedup_threshold` (0.98), `recall_pool_factor` (4) and `recall_mmr_lambda` (0.5)
  tune the rest.
- `ToolsConfig`, prefix `CORTEX_TOOLS_` with nested delimiter `__` (`config_tools.py`, ADR-0009):
  endpoints come either as the singular `CORTEX_TOOLS_ENDPOINT` or as per-sidecar
  `CORTEX_TOOLS_ENDPOINTS__<name>`, never mixed, with optional `CORTEX_TOOLS_ALLOW__<name>`
  allowlists that must each name a configured endpoint; `named_endpoints` sorts them so aggregate
  precedence is deterministic. `on_unavailable` picks the dead-sidecar policy, `call_timeout_s =
  DEFAULT_TOOL_CALL_TIMEOUT_S` (decision 10) bounds one sidecar call, and `audit_file`
  (decision 18) names a JSON-lines file every dispatcher also appends to. Four declarations travel
  together as `dispatch_policy`, so none can reach one dispatcher and miss another: `costs` (built
  in is `spawn_subagents` at `DEFAULT_SPAWN_COST`, `MAX_TOOL_DISPATCHES // 4`; a price outside
  `1..MAX_TOOL_DISPATCHES` fails at boot), `salience` with `salience_limit` (below 1 fails at
  boot), `gated` (defaulting to `(ESCALATE_TOOL_NAME, "send_email")`, ADR-0022) and `gate_reasons`
  (ADR-0030 decision 1). The built-in prices and reasons merge **under** the user's, a nested-dict
  env key otherwise replacing the whole mapping.
- `ReplyBoundsConfig`, prefix `CORTEX_REPLY_` (`config_reply.py`, ADR-0048):
  `CORTEX_REPLY_MAX_TOKENS` (0, no cap), `CORTEX_REPLY_THINKING` (true) and
  `CORTEX_REPLY_TRACE_TOKENS` (unset, the tier's own `--reasoning-budget` deciding), with
  `bounds()` reducing the unset set to `None` so the request stays byte-identical. The root hands
  one value to both `TurnEngine` and `BrainPhase`, so one turn keeps one bound across a handoff; a
  deployment wanting the tiers bounded differently leaves it unset and sets the server flags
  `CORTEX_REASONING_BUDGET` and `CORTEX_REASONING_BUDGET_BRAIN`. **The count is not derived from
  the switch** here, uniquely: a user's reply renders its trace as the thinking status the overlay
  shows (ADR-0020), so zero is a real setting and not the sentinel for unset.
- `LoggingConfig`, prefix `CORTEX_LOG_` (`config_logging.py`, ADR-0051 decision 1):
  `CORTEX_LOG_FORMAT` (`plain`, or `packed` for one JSON object per line), read by
  `configure_from_env()`, which `__main__` calls and which raises `UnknownLogFormatError` on an
  unknown rendering. The level is not a setting: the tool audit and recall trails both log at
  `INFO`, and turning the level down would silently empty a record the brain must keep.
- `SwapConfig`, prefix `CORTEX_` (`config_swap.py`, ADR-0030): `escalation` enables the capability
  and `modelhost_backend` says who owns the model processes, `supervisor` being the real
  `HttpModelHost` over `CORTEX_MODELHOST_ENDPOINT`
  ([brain-model-manager.md](brain-model-manager.md)). `modelhost_timeout_s` (60 s) bounds one
  control call and must stay above the sidecar's own worst `stop`; `evict_models` names further
  hosted tiers a swap stops first and restarts after, and `coresident` (off) leaves them serving
  and skips the drain, asserting that the card holds the pair
  ([co-residency](../readings/co-residency.md)); `brain_vram_mib` (0) is the free device memory the
  deep tier needs, compared against the host's reading immediately before the load, and
  `brain_decode_tps` (0.0) the rate the deep phase judges a real completion against (ADR-0055
  decisions 4 and 5); `swap_drain_timeout_s` (60 s), `swap_load_timeout_s` (300 s) and
  `swap_tier_heal_s` (30 s, pacing the check of every evicted tier, ADR-0054 decisions 3 and 4)
  are the timings. Escalation without a model host or a brain endpoint fails at boot, as does
  co-residency on the `supervisor` host with no measured VRAM figure; the decode figure guards no
  decision and is not required. `residency_plan(cortex_model)` is the one `ResidencyPlan` the
  manager, the conductor and boot recovery read.
- `SubagentsConfig`, prefix `CORTEX_SUBAGENTS_` (ADR-0010, ADR-0012, ADR-0018): a `llamacpp`
  backend needs both `endpoint` (the CPU overflow `llama-server`) and `gpu_endpoint`. One
  subagent's ask and the pool's ceilings all default to a module constant rather than a literal
  inside `Field(...)`, so `scripts/crosscheck.py` can compare the declaration with every place
  `docker/docker-compose.subagents.yml` and the roster override write it; `vram_gb` is the measured
  3.5 GiB, above the 3338 to 3410 MiB the GPU-placed tier costs, so one spawn fits the headroom and
  the next overflows, and `memory_gb` the measured 3.0, about 2.5 GiB of RSS rounded up so two are
  admitted (ADR-0012 decision 14). The flat fields define the roster's default entry and each
  `CORTEX_SUBAGENTS_ROSTER__<name>` adds one alternate as a JSON `SubagentRosterEntry`, whose
  missing asks fall back to the shipped ones. `stall_timeout_s: float = 600.0` is the pool's own
  silence ceiling, covering a CPU call's time to first token on a tier decoding at 0.18 to
  1.35 tok/s; `admission_wait_s: float = 7200.0` (decision 11) is how long a spawn may queue for
  room, three run deadlines, clearing twice the 1624.6 s the last spawn of a full batch was
  measured waiting when an entry's admitted pair runs one after the other (893.2 s when it
  overlaps); and `max_tokens: int = 1024` with `run_timeout_s: float = 2400.0` (ADR-0048) are the
  generation cap each completion takes and the deadline on the whole run, tool dispatches included.
  Construction enforces three orderings: `run_timeout_s` strictly above `stall_timeout_s`, strictly
  under `admission_wait_s` compared as `ATTEMPTS_PER_ADMISSION` whole deadlines, and strictly above
  a whole delegated dispatch, the last checked by `check_tool_call_deadline`. `max_tokens` against
  `run_timeout_s` is deliberately not checked, a count converting into a time only through a decode
  rate that moves by a factor of seven with the host's load. `attempt_bounds` is the pair as the
  core's `AttemptBounds`, and `named_roster` the ready-to-dial mapping; every entry must fit the
  budget or construction fails.
- `BodyConfig`, prefix `CORTEX_BODY_` (`config_body.py`, ADR-0023): a `grpc` backend needs an
  `endpoint`, the host body's bind (`host.docker.internal:50151` from the dockerized brain), and
  `CORTEX_SEAM_TOKEN` authenticates the dial. `capture_max_edge: int =
  DEFAULT_CAPTURE_MAX_EDGE` (2048) and `max_image_bytes: int = MAX_IMAGE_BYTES` (6 MiB) are what
  the brain asks the body for **and** holds the reply to, the body clamping both and an older body
  ignoring both; the edge default sits above the body's own 1600 because the pixels are only worth
  sending when the model host's `CORTEX_IMAGE_MAX_TOKENS` gives the encoder somewhere to put them,
  and `0` still means the body's own default. `capture_timeout_s` (10.0) and `call_timeout_s` (5.0)
  are imported from `cortex_body_client`, so no call to the body is unbounded. All four are bounded
  so a misconfiguration fails at boot: the edge `ge=0, le=8192`, the byte cap `gt=0, le=6291456`
  (it may tighten the domain ceiling, never loosen it), and both deadlines `gt=0`.
- `ScheduleConfig`, prefix `CORTEX_SCHEDULE_` (`config_schedule.py`, ADR-0025): `backend:
  ScheduleBackendName = DEFAULT_SCHEDULE_BACKEND` (`"none"`, with no store, no built-ins, no ticker
  and benignly empty reminder RPCs), plus the positive `poll_s` (5.0), `lease_s` (300.0, keep it
  above the slowest expected task), `claim_limit` (8) and `max_active` (32). `tz: str = "UTC"` is
  the IANA key model-facing schedule times render in (ADR-0065 decision 1), validated at boot and
  resolved by `display_zone()` through the one `zoneinfo`-backed `ZoneInfoResolver` the codec also
  decodes stored zones with. The store dials `CORTEX_REDIS_URL`.

Four of these defaults are module constants rather than literals inside a `Field(...)`
(`DEFAULT_CAPTURE_MAX_EDGE`, `DEFAULT_VISION_MODE`, `DEFAULT_SALIENCE`,
`DEFAULT_SCHEDULE_BACKEND`), because a compose file ships each one again as a substitution default
and `scripts/crosscheck.py` can only compare a restatement with a declaration it can read.

## Boot checks that span two settings classes

- `delegated_call_bounds(tools) -> int` (`bounds.py`, ADR-0047 decision 3) is how many whole
  `CORTEX_TOOLS_CALL_TIMEOUT_S` bounds one delegated dispatch can spend: `walks * sidecars + 1`,
  where `walks` is 2 at one endpoint and 3 above it. It is an upper bound, each walk costing one
  bound per wedged sidecar it lists. Measured against the real composition, a delegated dispatch
  spends the bound twice at one endpoint and four times at two.
- `check_tool_call_deadline(subagents, tools)` refuses a deployment whose whole delegated dispatch
  does not sit strictly under `CORTEX_SUBAGENTS_RUN_TIMEOUT_S`, raising `ToolCallDeadlineError`
  naming both settings, both values, the multiple and the product. It applies only when tools are
  `mcp` and delegation is `llamacpp`, and both outcomes log the same five fields, the pass at info
  and the refusal at error. The config is handed straight back, so the root checks on the way
  through, before any adapter is built.
- `check_control_deadline(swap)` asks the model host for its own `ControlBounds` and raises
  `ControlDeadlineError` when `CORTEX_MODELHOST_TIMEOUT_S` does not strictly clear their sum,
  releasing what the runtime already holds first. Only an answered mismatch refuses: a host that
  cannot be asked is logged at warning and let through, and one reporting no bounds is the scripted
  host, which stops no process.

**Dependencies.** pydantic and pydantic-settings, plus the constants each class imports from
`cortex_core` and `cortex_body_client` rather than restating.
