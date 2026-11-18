"""Boot check: the three settings that name the GPU subagent tier's servers."""

import logging
from urllib.parse import urlsplit

from cortex_orchestrator.config_subagents import SubagentsConfig, endpoint_list
from cortex_orchestrator.config_swap import SwapConfig

_logger = logging.getLogger(__name__)

UNMATCHED_GPU_SERVERS = "the settings that name the GPU subagent servers disagree"


def _host(address: str) -> str:
    """The host name of an address, or an empty string when it has none or does not parse."""
    try:
        return urlsplit(address).hostname or ""
    except ValueError:
        return ""


def hosted_gpu_servers(subagents: SubagentsConfig, swap: SwapConfig) -> int:
    """How many addresses of the default entry's GPU target are on the model host."""
    host = _host(swap.modelhost_endpoint)
    servers = endpoint_list(subagents.gpu_endpoint)
    return sum(1 for server in servers if host and _host(server) == host)


def warn_of_unmatched_gpu_servers(subagents: SubagentsConfig, swap: SwapConfig) -> SubagentsConfig:
    """Log a warning when the server count, the GPU addresses and the evict list disagree."""
    routed = hosted_gpu_servers(subagents, swap)
    evicted = len(swap.evict_models) if swap.escalation else routed
    if (routed or evicted) and not routed == evicted == subagents.gpu_servers:
        _logger.warning(
            UNMATCHED_GPU_SERVERS,
            extra={
                "gpu_servers": subagents.gpu_servers,
                "gpu_endpoints": routed,
                "evict_models": len(swap.evict_models),
                "escalation": swap.escalation,
            },
        )
    return subagents
