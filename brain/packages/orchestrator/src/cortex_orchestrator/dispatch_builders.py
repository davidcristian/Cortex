"""The cortex's own tool set: the built-ins it may call, and the dispatcher it calls through.

Split from `builders.py` for the 300-line cap as the built-in set grew, and re-exported there,
so every existing `from cortex_orchestrator.builders import build_cortex_tools` keeps resolving.
The seam is what each side builds rather than how much of it there is: `builders.py` builds the
adapters that reach something outside this process (the generation client, the MCP sidecars, the
body's channel), each handing back the coroutine that releases it, while this module composes
pieces already built into the set one agent is allowed to call. Nothing here opens a resource, so
nothing here returns a closer.

Both factories are the cortex's alone (ADR-0013): built-ins are never advertised to a subagent,
whose narrower set is wired from the shared MCP registry in `subagent_builders.py`.
"""

from collections.abc import Sequence

from cortex_core import (
    DEFAULT_DISPATCH_POLICY,
    BodyGateway,
    BuiltinTool,
    CaptureBounds,
    CaptureScreenTool,
    Clock,
    CompositeToolRegistry,
    Confirmer,
    DispatchPolicy,
    EscalateToBrainTool,
    GetVolumeTool,
    SetVolumeTool,
    SightedToolRegistry,
    SpawnSubagentsTool,
    ToolDispatcher,
    ToolRegistry,
    VisionProbe,
)
from cortex_tools import LoggingAuditSink


def build_builtin_tools(
    spawn_tool: SpawnSubagentsTool | None,
    body: BodyGateway | None,
    schedule_tools: Sequence[BuiltinTool] = (),
    *,
    escalation: bool = False,
    vision: CaptureBounds | None = None,
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

    `vision` (ADR-0029) is that same rule for `capture_screen`: it needs a body to take the
    picture *and* a model that can see it, so it is advertised only when the composition root
    has confirmed both. Offering it otherwise would spend the whole privacy cost of a screen
    read (the capture taken, the user notified, the turn tainted) on an image nothing can read.
    """
    builtins: list[BuiltinTool] = [spawn_tool] if spawn_tool is not None else []
    if body is not None:
        builtins.append(GetVolumeTool(body))
        builtins.append(SetVolumeTool(body))
        if vision is not None:
            builtins.append(
                CaptureScreenTool(body, max_edge=vision.max_edge, max_bytes=vision.max_bytes)
            )
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
    vision: VisionProbe | None = None,
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

    `vision` (ADR-0029 live-probe addendum) is the running server's own answer to whether the
    model can read a picture, and wrapping the composite in `SightedToolRegistry` is what makes
    `capture_screen` follow it: hidden from the advertisement and refused at the call while the
    answer is no. Absent for `CORTEX_VISION=on|off` (the answer is fixed by the owner) and for
    the deep tier's set (it carries no capture tool to gate), so the wrapper appears exactly
    where the answer is discovered.
    """
    if not builtins and tool_registry is None:
        return None
    registry: ToolRegistry = CompositeToolRegistry(builtins, remote=tool_registry)
    if vision is not None:
        registry = SightedToolRegistry(registry, vision)
    return ToolDispatcher(
        registry,
        LoggingAuditSink(),
        clock,
        confirmer=confirmer,
        policy=policy,
    )
