"""The cortex's own tool set: the built-ins it may call, and the dispatcher it calls through."""

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
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
    ForgetChosenTool,
    ForgetUntrustedTool,
    GetVolumeTool,
    RecordCard,
    ResultNote,
    SetVolumeTool,
    SightedToolRegistry,
    SpawnSubagentsTool,
    ToolAuditSink,
    ToolDispatcher,
    ToolOffer,
    ToolRegistry,
    UntrustedMemoryForget,
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


def build_builtin_tools(  # noqa: PLR0913 -- each optional built-in group is wired on its own
    spawn_tool: SpawnSubagentsTool | None,
    body: BodyGateway | None,
    schedule_tools: Sequence[BuiltinTool] = (),
    *,
    escalation: bool = False,
    vision: CaptureBounds | None = None,
    memory: UntrustedMemoryForget | None = None,
    chosen: ForgetChosenTool | None = None,
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
    if memory is not None:
        builtins.append(ForgetUntrustedTool(memory))
    if chosen is not None:
        builtins.append(chosen)
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
    cards = {tool.spec.name: tool for tool in builtins if isinstance(tool, RecordCard)}
    offers = {tool.spec.name: tool for tool in builtins if isinstance(tool, ToolOffer)}
    notes = {tool.spec.name: tool for tool in builtins if isinstance(tool, ResultNote)}
    # A model can call a built-in by name on a turn whose list left it out, and the dispatcher
    # then has no spec to read, so its name must be in the policy for the card to show.
    confirmed = [tool.spec.name for tool in builtins if tool.spec.confirm_required]
    private = [tool.spec.name for tool in builtins if tool.spec.private_arguments]
    policy = replace(
        setup.policy,
        confirm_names=(*setup.policy.confirm_names, *confirmed),
        private_names=(*setup.policy.private_names, *private),
        record_cards=cards,
        offers=offers,
        notes=notes,
    )
    return ToolDispatcher(registry, setup.audit, clock, confirmer=confirmer, policy=policy)
