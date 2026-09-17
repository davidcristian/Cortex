"""The cortex's own tool set: the built-ins it may call, and the dispatcher it calls through."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

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
    ToolAuditSink,
    ToolDispatcher,
    ToolRegistry,
    VisionProbe,
)
from cortex_orchestrator.config_tools import ToolsConfig
from cortex_tools import JsonLinesAuditSink, LoggingAuditSink, TeeAuditSink


@dataclass(frozen=True, slots=True)
class DispatchSetup:
    """What every `ToolDispatcher` in the process is built with: its policy and its audit trail."""

    policy: DispatchPolicy = DEFAULT_DISPATCH_POLICY
    audit: ToolAuditSink = field(default_factory=LoggingAuditSink)


DEFAULT_DISPATCH_SETUP = DispatchSetup()


def tool_audit_from_config(config: ToolsConfig) -> ToolAuditSink:
    """Map ``CORTEX_TOOLS_AUDIT_FILE`` to the trail every dispatcher records to."""
    line = LoggingAuditSink()
    if not config.audit_file:
        return line
    return TeeAuditSink((line, JsonLinesAuditSink(Path(config.audit_file))))


def build_builtin_tools(
    spawn_tool: SpawnSubagentsTool | None,
    body: BodyGateway | None,
    schedule_tools: Sequence[BuiltinTool] = (),
    *,
    escalation: bool = False,
    vision: CaptureBounds | None = None,
) -> list[BuiltinTool]:
    """The cortex's built-in set, assembled once by the wiring."""
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
    setup: DispatchSetup = DEFAULT_DISPATCH_SETUP,
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
        setup.audit,
        clock,
        confirmer=confirmer,
        policy=setup.policy,
    )
