"""The orderings between bounds that no single settings class can check for itself."""

import logging

from cortex_orchestrator.config_subagents import SubagentsConfig
from cortex_orchestrator.config_tools import ToolsConfig

__all__ = ["ToolCallDeadlineError", "check_tool_call_deadline", "delegated_call_bounds"]

_logger = logging.getLogger(__name__)

_REFUSED = "one wedged tool dispatch can outlast the delegated run that has to contain it"


class ToolCallDeadlineError(RuntimeError):
    """The bound on one tool call does not fit inside the delegated run that has to contain it."""


def delegated_call_bounds(tools: ToolsConfig) -> int:
    """How many whole call bounds one delegated dispatch can spend, its listing included."""
    # Every walk of the tool set reaches the bound separately: the run's advertisement, the live
    # strip of the tools needing confirmation, and, past one endpoint, the walk that finds which
    # registry owns the name. Then the call itself.
    sidecars = len(tools.named_endpoints)
    walks = 2 if sidecars == 1 else 3
    return walks * sidecars + 1


def check_tool_call_deadline(subagents: SubagentsConfig, tools: ToolsConfig) -> SubagentsConfig:
    """Raise when a tool call may be bounded above the delegated run that has to contain it."""
    if tools.backend != "mcp" or subagents.backend != "llamacpp":
        return subagents
    if _dispatch_cost(tools) < subagents.run_timeout_s:
        _logger.info(
            "the delegated run's deadline outlasts one wedged tool dispatch",
            extra=_pairing(subagents, tools),
        )
        return subagents
    msg = (
        f"CORTEX_TOOLS_CALL_TIMEOUT_S is {tools.call_timeout_s} s and one delegated dispatch can "
        f"spend it {delegated_call_bounds(tools)} times over across "
        f"{len(tools.named_endpoints)} configured sidecar(s), so {_dispatch_cost(tools)} s, while "
        f"CORTEX_SUBAGENTS_RUN_TIMEOUT_S is {subagents.run_timeout_s} s: one wedged tool call can "
        "outlast the whole delegated run that has to contain it, the run's deadline fires first, a "
        "stalled sidecar is reported as a subtask that would not stop talking, and the re-run a "
        "transport failure allows is skipped. Lower the call bound, or raise the run bound above "
        "the dispatch (docs/runbooks/tools-mcp.md)"
    )
    _logger.error(_REFUSED, extra=_pairing(subagents, tools))
    raise ToolCallDeadlineError(msg)


def _dispatch_cost(tools: ToolsConfig) -> float:
    """What one wedged delegated dispatch costs in seconds: the bound times its own multiple."""
    return delegated_call_bounds(tools) * tools.call_timeout_s


def _pairing(subagents: SubagentsConfig, tools: ToolsConfig) -> dict[str, float]:
    """The numbers as record fields, built once so both lines have the same set."""
    return {
        "call_timeout_s": tools.call_timeout_s,
        "call_bounds_per_dispatch": delegated_call_bounds(tools),
        "dispatch_timeout_s": _dispatch_cost(tools),
        "run_timeout_s": subagents.run_timeout_s,
        "sidecars": len(tools.named_endpoints),
    }
