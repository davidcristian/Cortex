"""The cortex's own tool set: the built-ins it may call, and the dispatcher it calls through."""

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
    """The cortex's built-in set, assembled once by the wiring (ADR-0025 decision 7)."""
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
    """The cortex's audited dispatcher: the built-in set merged with the MCP tools."""
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
