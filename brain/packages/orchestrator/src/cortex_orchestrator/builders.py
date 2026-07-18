"""Adapter builders for the composition root: pick each port's adapter from config.

One builder per capability, called only by `wiring.run_from_env` (DI at the edge,
AGENTS.md). Each returns the built dependency together with the coroutine that
releases it, so the root's shutdown path is uniform whatever was picked:

- InferenceBackend -> `EchoInferenceBackend` by default (GPU-less), or the real
  `LlamaCppBackend` over a `SingleResidentModelManager` when CORTEX_INFERENCE_BACKEND
  is `llamacpp` (ADR-0007). The GPU path is opt-in so CI stays inference-free.
- Memory -> `memory_builders.py` (split for the 300-line cap when the recall reranking policy
  arrived): a `MemoryRecaller` over the `PgVectorMemoryStore` + `LlamaCppEmbedder`, with its scope
  and recall-rerank policies, when CORTEX_MEMORY_BACKEND is `pgvector` (ADR-0008). Opt-in so CI and
  the no-GPU dev loop stay DB-free.
- Tools -> the MCP `ToolRegistry` when CORTEX_TOOLS_BACKEND is `mcp` (ADR-0009), else None:
  one lazy `ReconnectingMcpToolRegistry` per configured endpoint (dialed on first use, not at
  startup, hence boot-tolerant), allowlist-filtered, optionally skip-unavailable (degraded-mode +
  boot-tolerance addenda), and aggregated as configured. Shared by the cortex (via the
  composite) and its subagents.
- Subagents -> `subagent_builders.py` (split for the 300-line cap when the ADR-0018 roster
  arrived): the `spawn_subagents` tool over a roster-resolving `SubagentRunner`.
- History window -> `CharBudgetHistoryWindow` over CORTEX_HISTORY_CHAR_BUDGET (ADR-0014),
  on by default (48K chars ≈ 12K of the cortex's 16K-token context); 0 disables it.
- Output guardrail -> `UrlRedactingGuardrail` over CORTEX_OUTPUT_GUARDRAIL (ADR-0015), on by
  default (hardening ships enabled); `off` restores the unguarded stream.
"""

import logging
from collections.abc import Awaitable, Callable, Sequence
from functools import partial

import httpx

from cortex_body_client import GrpcBodyGateway
from cortex_core import (
    DEFAULT_DISPATCH_POLICY,
    AggregateToolRegistry,
    BodyGateway,
    BuiltinTool,
    CharBudgetHistoryWindow,
    Clock,
    CompositeToolRegistry,
    Confirmer,
    DispatchPolicy,
    EchoInferenceBackend,
    EscalateToBrainTool,
    FilteredToolRegistry,
    GatedToolRegistry,
    GetVolumeTool,
    InferenceBackend,
    ModelManager,
    SetVolumeTool,
    SingleResidentModelManager,
    SkipUnavailableToolRegistry,
    SpawnSubagentsTool,
    StrictUrlRedactingGuardrail,
    ToolDispatcher,
    ToolError,
    ToolRegistry,
    UrlRedactingGuardrail,
)
from cortex_inference import LlamaCppBackend
from cortex_orchestrator.config import BodyConfig, InferenceConfig
from cortex_orchestrator.config_tools import ToolsConfig
from cortex_tools import (
    LoggingAuditSink,
    ReconnectingMcpToolRegistry,
    streamable_http_session,
)

# Connect/write/pool time out fast on a dead server; reads have no deadline, since a
# generation may legitimately stream for a long time (the adapter sets no timeout itself).
# Public: `subagent_builders` dials its llama-servers with the same policy (one knob).
LLAMACPP_CONNECT_TIMEOUT_S = 10.0

_logger = logging.getLogger(__name__)


def _report_sidecar_unavailable(name: str, error: ToolError) -> None:
    """The skip-and-report reporter: degradation is a logged warning, never silent."""
    _logger.warning(
        "tool sidecar unavailable; serving without it",
        extra={"sidecar": name, "error": str(error)},
    )


async def noop_aclose() -> None:
    """The closer for a capability that held no resources; shared by every builder module."""
    return


def build_inference_backend(
    config: InferenceConfig, cortex_model: str, *, manager: ModelManager | None = None
) -> tuple[InferenceBackend, Callable[[], Awaitable[None]]]:
    """Pick the backend from config; return it with the coroutine that releases it.

    Returns the no-op closer for Echo (no resources) and the HTTP client's ``aclose`` for
    llama.cpp, so the caller's shutdown path is uniform regardless of which backend ran.
    ``manager`` overrides the single-resident lease with the swapping one when a handoff is
    wired (ADR-0030): the backend must lease through the very object the residency scope
    swaps under, or a swap could preempt a live round.
    """
    if config.backend == "llamacpp":
        client = httpx.AsyncClient(timeout=httpx.Timeout(LLAMACPP_CONNECT_TIMEOUT_S, read=None))
        leases = (
            manager
            if manager is not None
            else SingleResidentModelManager(cortex_model, config.endpoint)
        )
        return LlamaCppBackend(leases, client), client.aclose
    return EchoInferenceBackend(), noop_aclose


def build_tool_registry(
    config: ToolsConfig,
) -> tuple[ToolRegistry | None, Callable[[], Awaitable[None]]]:
    """The raw MCP `ToolRegistry` shared by the cortex and its subagents, or None (ADR-0009).

    ``none`` disables tools. The MCP-less default CI and the no-GPU dev loop run. ``mcp``
    builds one lazy `ReconnectingMcpToolRegistry` per configured endpoint (refinements +
    boot-tolerance addenda): no dial happens here, so a sidecar **down at startup no longer
    fails the build**. It is dialed on first use, per call, and a recovered one rejoins without
    a brain restart. An endpoint with an allowlist is wrapped in `FilteredToolRegistry`, and
    several endpoints merge behind one `AggregateToolRegistry` (first-wins by the config's
    sorted-name order). With `CORTEX_TOOLS_ON_UNAVAILABLE=skip` each endpoint is additionally
    wrapped in `SkipUnavailableToolRegistry` (degraded-mode addendum): an unavailable sidecar
    (dead at listing time *or* down at boot) is logged and served around instead of failing the
    whole tool set. `CORTEX_TOOLS_GATED` names stamp the shared root via `GatedToolRegistry`
    (ADR-0022): gating is declared here in brain-side config, never by a sidecar's own metadata,
    and the subagent wiring's `UngatedToolRegistry` then strips the stamped tools. No session is
    held between calls, so the closer is a no-op; the registry is left un-audited. The cortex
    and each subagent wrap it in their own `ToolDispatcher`.
    """
    if config.backend != "mcp":
        return None, noop_aclose
    registries: list[ToolRegistry] = []
    for name, url in config.named_endpoints.items():
        registry: ToolRegistry = ReconnectingMcpToolRegistry(partial(streamable_http_session, url))
        allow = config.allow.get(name)
        if allow:
            registry = FilteredToolRegistry(registry, allow=allow)
        if config.on_unavailable == "skip":
            registry = SkipUnavailableToolRegistry(
                registry, name=name, report=_report_sidecar_unavailable
            )
        registries.append(registry)
    root = registries[0] if len(registries) == 1 else AggregateToolRegistry(registries)
    if config.gated:
        root = GatedToolRegistry(root, gated=config.gated)
    return root, noop_aclose


def build_output_guardrail(
    mode: str,
) -> UrlRedactingGuardrail | StrictUrlRedactingGuardrail | None:
    """The turn's output guardrail, or None when disabled (ADR-0015).

    `redact` (`CORTEX_OUTPUT_GUARDRAIL`'s default, so hardening is on out of the box) scrubs URLs
    sourced *verbatim* from untrusted tool results out of the reply the user sees, the
    model-independent laundering defense; `strict` (ADR-0015 addendum) redacts every non-user
    URL on a tainted turn; `off` restores the unguarded stream. An untainted/clean turn is
    untouched by any mode (nothing collected, nothing flagged, nothing scrubbed).
    """
    if mode == "strict":
        return StrictUrlRedactingGuardrail()
    return UrlRedactingGuardrail() if mode == "redact" else None


def build_history_window(char_budget: int) -> CharBudgetHistoryWindow | None:
    """The turn's history window, or None when windowing is disabled (ADR-0014).

    A positive budget caps what one turn sends to the model at the newest whole turns
    fitting it; 0 (`CORTEX_HISTORY_CHAR_BUDGET=0`) disables windowing, so the model gets
    the full stored history, the pre-ADR-0014 behavior. Persistence is untouched either way.
    """
    return CharBudgetHistoryWindow(char_budget) if char_budget > 0 else None


async def build_body_gateway(
    config: BodyConfig, *, token: str
) -> tuple[BodyGateway | None, Callable[[], Awaitable[None]]]:
    """Pick the body gateway from config; return it with the coroutine that releases it (ADR-0023).

    ``none`` disables the brain→body direction. The no-body default CI and dev loop run and the
    volume tools are never registered. ``grpc`` opens a channel to the host body's ``BodyService``
    and attaches the shared seam ``token`` (ADR-0016) on every call; the returned closer closes
    the channel. The channel connects lazily, so an unreachable body fails a volume call (a
    recoverable ``is_error`` result), never brain startup. ``capture_timeout_s`` becomes the
    deadline on the one call that can park a host thread (ADR-0029).
    """
    if config.backend != "grpc":
        return None, noop_aclose
    return await GrpcBodyGateway.connect(
        config.endpoint, token=token, capture_timeout_s=config.capture_timeout_s
    )


def build_builtin_tools(
    spawn_tool: SpawnSubagentsTool | None,
    body: BodyGateway | None,
    schedule_tools: Sequence[BuiltinTool] = (),
    *,
    escalation: bool = False,
) -> list[BuiltinTool]:
    """The cortex's built-in set, assembled once by the wiring (ADR-0025 decision 7).

    The bundling that keeps `build_cortex_tools` under the six-argument ceiling as
    capabilities accumulate: delegation (ADR-0010), the volume pair when the body is wired
    (ADR-0023), and the schedule tools (`build_schedule_tools`, ADR-0025). Built-ins are
    cortex-only by construction, so subagents never see any of these (ADR-0013).

    `escalation` (ADR-0030) advertises `escalate_to_brain` only when a handoff can actually be
    run: the wrapper, the conductor, and a model host all exist behind `CORTEX_ESCALATION`.
    Advertising it otherwise would offer the model a tool that could only refuse, the same
    honesty rule that keeps the volume pair out without a body and task scheduling out without
    delegation.
    """
    builtins: list[BuiltinTool] = [spawn_tool] if spawn_tool is not None else []
    if body is not None:
        builtins.append(GetVolumeTool(body))
        builtins.append(SetVolumeTool(body))
    if escalation:
        builtins.append(EscalateToBrainTool())
    builtins.extend(schedule_tools)
    return builtins


def build_cortex_tools(
    tool_registry: ToolRegistry | None,
    builtins: Sequence[BuiltinTool],
    clock: Clock,
    *,
    confirmer: Confirmer | None = None,
    policy: DispatchPolicy = DEFAULT_DISPATCH_POLICY,
) -> ToolDispatcher | None:
    """The cortex's audited dispatcher: the built-in set merged with the MCP tools.

    None when nothing is enabled (the Slice 3 turn path unchanged). `builtins` arrives
    pre-assembled from `build_builtin_tools` (one sequence, not one parameter per
    capability). The `CompositeToolRegistry` gives the built-in tools precedence and
    advertises the MCP tools alongside them; subagents receive the MCP subset without the
    built-ins (depth-1, so a subagent never gets an OS action or a schedule verb, per
    ADR-0013/0023/0025), wired in `build_subagents`, and always `confirmer=None`
    (ADR-0013): only the cortex's dispatcher gets the stream's real confirmer (ADR-0022),
    threaded per stream by the wiring's engine factory. A user gates any built-in by
    naming it in the policy's `gated_names` (`CORTEX_TOOLS_GATED`), the dispatcher's backstop,
    and prices any of them in its `costs` (`CORTEX_TOOLS_COSTS`), which is what the cortex's tool
    loop charges each dispatch against its budget (ADR-0009 cost addendum); the policy's third
    declaration, `salience` (`CORTEX_TOOLS_SALIENCE`), is what refuses a call that loop has
    already made (ADR-0009 salience addendum). This is the dispatcher
    the default `spawn_subagents` price applies to: built-ins are cortex-only, so the
    subagent and ticker dispatchers never advertise it.
    """
    if not builtins and tool_registry is None:
        return None
    registry = CompositeToolRegistry(builtins, remote=tool_registry)
    return ToolDispatcher(
        registry,
        LoggingAuditSink(),
        clock,
        confirmer=confirmer,
        policy=policy,
    )
