"""Adapter builders for the composition root: pick each port's adapter from config.

One builder per capability, called only by `wiring.run_from_env` (DI at the edge,
AGENTS.md). Each returns the built dependency together with the coroutine that
releases it, so the root's shutdown path is uniform whatever was picked:

- InferenceBackend -> `EchoInferenceBackend` by default (GPU-less), or the real
  `LlamaCppBackend` over a `SingleResidentModelManager` when CORTEX_INFERENCE_BACKEND
  is `llamacpp` (ADR-0007). The GPU path is opt-in so CI stays inference-free. It is the one
  builder here that asks a question before it builds: whether this deployment's engine reads a
  per-request trace budget (CORTEX_INFERENCE_TRACE_LEVER, ADR-0005 request-lever addendum), which
  is a property of a binary and so is settled once and handed to the adapter as a bool.
- Memory -> `memory_builders.py` (split for the 300-line cap when the recall reranking policy
  arrived): a `MemoryRecaller` over the `PgVectorMemoryStore` + `LlamaCppEmbedder`, with its scope
  and recall-rerank policies, when CORTEX_MEMORY_BACKEND is `pgvector` (ADR-0008). Opt-in so CI and
  the no-GPU dev loop stay DB-free.
- Tools -> the MCP `ToolRegistry` when CORTEX_TOOLS_BACKEND is `mcp` (ADR-0009), else None:
  one lazy `ReconnectingMcpToolRegistry` per configured endpoint (dialed on first use, not at
  startup, hence boot-tolerant), bounded (bound addendum), allowlist-filtered, optionally
  skip-unavailable (degraded-mode + boot-tolerance addenda), and aggregated as configured.
  Shared by the cortex (via the composite) and its subagents.
- Subagents -> `subagent_builders.py` (split for the 300-line cap when the ADR-0018 roster
  arrived): the `spawn_subagents` tool over a roster-resolving `SubagentRunner`.
- History window -> `window_builders.py` (split for the 300-line cap when the summarizing
  window arrived): a `CharBudgetHistoryWindow` over CORTEX_HISTORY_CHAR_BUDGET, optionally
  wrapped so the turns it drops arrive as a recap.
- Output guardrail -> `UrlRedactingGuardrail` over CORTEX_OUTPUT_GUARDRAIL (ADR-0015), on by
  default (hardening ships enabled); `lookalike` adds the non-ASCII-host ground, `strict` distrusts
  every link on a tainted turn, and `off` restores the unguarded stream.
- Cortex tool set -> `dispatch_builders.py` (split for the 300-line cap as the built-in set
  grew): the built-in tools and the audited `ToolDispatcher` over them, composed from pieces the
  builders above already made rather than reaching anything itself.

What is left here builds an adapter over something outside this process and returns the coroutine
that releases it; the two factories re-exported from `dispatch_builders.py` open nothing, which is
the seam between the modules. The explicit export list below carries those two, so every existing
`from cortex_orchestrator.builders import ...` resolves unchanged.
"""

import logging
from collections.abc import Awaitable, Callable
from functools import partial

import httpx

from cortex_body_client import GrpcBodyGateway
from cortex_core import (
    AggregateToolRegistry,
    BodyGateway,
    BoundedToolRegistry,
    EchoInferenceBackend,
    FilteredToolRegistry,
    GatedToolRegistry,
    InferenceBackend,
    LookalikeUrlRedactingGuardrail,
    ModelManager,
    OutputGuardrail,
    SingleResidentModelManager,
    SkipUnavailableToolRegistry,
    StrictUrlRedactingGuardrail,
    ToolError,
    ToolRegistry,
    UrlRedactingGuardrail,
)
from cortex_inference import (
    TRACE_LEVER_PROBE_TIMEOUT_S,
    LlamaCppBackend,
    reads_a_trace_budget,
)
from cortex_orchestrator.config import InferenceConfig, OutputGuardrailName
from cortex_orchestrator.config_body import BodyConfig
from cortex_orchestrator.config_tools import ToolsConfig
from cortex_orchestrator.dispatch_builders import build_builtin_tools, build_cortex_tools
from cortex_tools import ReconnectingMcpToolRegistry, streamable_http_session

__all__ = [
    "LLAMACPP_CONNECT_TIMEOUT_S",
    "build_body_gateway",
    "build_builtin_tools",
    "build_cortex_tools",
    "build_generation_client",
    "build_inference_backend",
    "build_output_guardrail",
    "build_tool_registry",
    "noop_aclose",
    "resolve_trace_lever",
]

# Connect/write/pool time out fast on a dead server, one knob for every tier: a dead server is
# dead at the same speed everywhere. The read phase is the factory's argument, not this.
LLAMACPP_CONNECT_TIMEOUT_S = 10.0


def build_generation_client(stall_timeout_s: float) -> httpx.AsyncClient:
    """The client a llama-server generation stream rides (ADR-0005 stall-ceiling addendum).

    ``stall_timeout_s`` becomes httpx's READ timeout, which bounds **one socket read** and never
    the request: it detects a stall, so a stream whose chunks keep arriving may run as long as
    the model wants and a wedged one raises instead of waiting forever, which is what the
    founding ``read=None`` did while holding a model lease and a subagent admission with it.
    Consumer backpressure does not trip it, the seam's credit bound suspending the reader
    between reads rather than inside one.

    Sized per tier by the caller, since the worst legitimate silence differs by an order of
    magnitude between them (`CORTEX_INFERENCE_STALL_TIMEOUT_S` against
    `CORTEX_SUBAGENTS_STALL_TIMEOUT_S`); the ADR derives both from measurements.
    """
    return httpx.AsyncClient(
        timeout=httpx.Timeout(LLAMACPP_CONNECT_TIMEOUT_S, read=stall_timeout_s)
    )


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


async def resolve_trace_lever(config: InferenceConfig, cortex_model: str) -> bool:
    """Whether a request to this deployment may carry its own trace budget (ADR-0005).

    Three answers, one per mode, and only one of them touches the network:

    - ``off``: no, and nothing is asked. The request this repo sent before the key existed, and
      the answer for a deployment whose endpoint is a proxy a probe would ask the wrong question.
    - ``on``: yes, on the deployment's word. What an owner who knows their build sets, and what
      a test fixes the answer with.
    - ``auto`` (the default): yes exactly when the engine behind the endpoint says so, asked once
      here rather than per call because the answer is a property of a binary (``lever.py``).

    It is resolved before the backend is built, so the adapter holds a decided ``bool`` and never
    a question: nothing about the lever is asked while a user waits for a turn.
    """
    if config.trace_lever == "off":
        return False
    if config.trace_lever == "on":
        return True
    async with httpx.AsyncClient(timeout=TRACE_LEVER_PROBE_TIMEOUT_S) as client:
        return await reads_a_trace_budget(config.endpoint, cortex_model, client)


async def build_inference_backend(
    config: InferenceConfig, cortex_model: str, *, manager: ModelManager | None = None
) -> tuple[InferenceBackend, Callable[[], Awaitable[None]]]:
    """Pick the backend from config; return it with the coroutine that releases it.

    Returns the no-op closer for Echo (no resources) and the HTTP client's ``aclose`` for
    llama.cpp, so the caller's shutdown path is uniform regardless of which backend ran.
    ``manager`` overrides the single-resident lease with the swapping one when a handoff is
    wired (ADR-0030): the backend must lease through the very object the residency scope
    swaps under, or a swap could preempt a live round. That is also why one client carries the
    deep tier's stall ceiling as well as the cortex's: after a handoff the brain phase streams
    through this very backend object, at a different endpoint.

    It is a coroutine for the one thing on this path that has to ask something outside the
    process: whether this deployment's engine reads a per-request trace budget (ADR-0005
    request-lever addendum). Only the llama.cpp arm asks, and only in ``auto``, so the Echo
    deployment CI runs still opens nothing at all.
    """
    if config.backend == "llamacpp":
        client = build_generation_client(config.stall_timeout_s)
        leases = (
            manager
            if manager is not None
            else SingleResidentModelManager(cortex_model, config.endpoint)
        )
        lever = await resolve_trace_lever(config, cortex_model)
        return LlamaCppBackend(leases, client, trace_lever=lever), client.aclose
    return EchoInferenceBackend(), noop_aclose


def build_tool_registry(
    config: ToolsConfig,
) -> tuple[ToolRegistry | None, Callable[[], Awaitable[None]]]:
    """The raw MCP `ToolRegistry` shared by the cortex and its subagents, or None (ADR-0009).

    ``none`` disables tools. The MCP-less default CI and the no-GPU dev loop run. ``mcp``
    builds one lazy `ReconnectingMcpToolRegistry` per configured endpoint (refinements +
    boot-tolerance addenda): no dial happens here, so a sidecar **down at startup no longer
    fails the build**. It is dialed on first use, per call, and a recovered one rejoins without
    a brain restart. Each is wrapped innermost in a `BoundedToolRegistry` (ADR-0009 bound
    addendum), which is what makes a sidecar that hangs behave like one that refuses: the bound
    (`CORTEX_TOOLS_CALL_TIMEOUT_S`) turns a wedged call into the `ToolError` every layer above
    already knows how to handle, including the skip below. It goes innermost so the bound covers
    the dial and the call and nothing else; the built-in tools, which are deliberately slow, are
    composed elsewhere and never see it. An endpoint with an allowlist is wrapped in
    `FilteredToolRegistry`, and several endpoints merge behind one `AggregateToolRegistry`
    (first-wins by the config's sorted-name order). With `CORTEX_TOOLS_ON_UNAVAILABLE=skip`
    each endpoint is additionally
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
        dialing = ReconnectingMcpToolRegistry(partial(streamable_http_session, url))
        registry: ToolRegistry = BoundedToolRegistry(dialing, timeout_s=config.call_timeout_s)
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


def build_output_guardrail(mode: OutputGuardrailName) -> OutputGuardrail | None:
    """The turn's output guardrail, or None when disabled (ADR-0015).

    `redact` (`CORTEX_OUTPUT_GUARDRAIL`'s default, so hardening is on out of the box) scrubs URLs
    sourced *verbatim* from untrusted tool results out of the reply the user sees, the
    model-independent laundering defense; `lookalike` (ADR-0015 fourteenth addendum) adds every
    URL whose host is not plain ASCII on a tainted turn, the one ground a homoglyph cannot be
    chosen around; `strict` (ADR-0015 addendum) redacts every non-user URL on a tainted turn;
    `off` restores the unguarded stream. An untainted/clean turn is untouched by any mode
    (nothing collected, nothing flagged, nothing scrubbed). The parameter is the config's own
    `Literal`, so a name that is not one of the four is a type error here rather than a silently
    unguarded stream.
    """
    if mode == "strict":
        return StrictUrlRedactingGuardrail()
    if mode == "lookalike":
        return LookalikeUrlRedactingGuardrail()
    return UrlRedactingGuardrail() if mode == "redact" else None


async def build_body_gateway(
    config: BodyConfig, *, token: str
) -> tuple[BodyGateway | None, Callable[[], Awaitable[None]]]:
    """Pick the body gateway from config; return it with the coroutine that releases it (ADR-0023).

    ``none`` disables the brain→body direction. The no-body default CI and dev loop run and the
    volume tools are never registered. ``grpc`` opens a channel to the host body's ``BodyService``
    and attaches the shared seam ``token`` (ADR-0016) on every call; the returned closer closes
    the channel. The channel connects lazily, so an unreachable body fails a volume call (a
    recoverable ``is_error`` result), never brain startup. Both deadlines ride along:
    ``capture_timeout_s`` bounds a capture and ``call_timeout_s`` bounds every other call, so no
    call on this seam is unbounded (ADR-0029's uniform-deadline addendum).
    """
    if config.backend != "grpc":
        return None, noop_aclose
    return await GrpcBodyGateway.connect(
        config.endpoint,
        token=token,
        capture_timeout_s=config.capture_timeout_s,
        call_timeout_s=config.call_timeout_s,
    )
