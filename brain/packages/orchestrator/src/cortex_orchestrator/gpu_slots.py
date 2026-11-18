"""Boot check: the GPU slots a deployment names against the spawns its VRAM budget places."""

import logging

from cortex_core import PlacementRequest, PlacementTarget, VramBudgetPlacer
from cortex_orchestrator.config import BrainRuntimeConfig
from cortex_orchestrator.config_subagents import SubagentsConfig, endpoint_list

_logger = logging.getLogger(__name__)

UNPLACED_GPU_SLOTS = "the GPU subagent servers have more slots than the VRAM budget places spawns"


def gpu_slots(subagents: SubagentsConfig) -> int:
    """How many slots the default entry's GPU target has on servers of its own, else zero."""
    servers = endpoint_list(subagents.gpu_endpoint)
    if subagents.backend != "llamacpp" or servers == endpoint_list(subagents.endpoint):
        return 0
    return len(servers) * subagents.gpu_parallel


def placed_at_once(subagents: SubagentsConfig, runtime: BrainRuntimeConfig, spawns: int) -> int:
    """How many of ``spawns`` default-entry spawns the placer puts on the GPU with none released."""
    placer = VramBudgetPlacer(
        soft_cap_gb=runtime.vram_soft_cap_gb, cortex_reservation_gb=runtime.cortex_reservation_gb
    )
    ask = PlacementRequest(subagents.model, subagents.vram_gb, subagents.cpus, subagents.memory_gb)
    return sum(placer.place(ask).target is PlacementTarget.GPU for _ in range(spawns))


def warn_of_unplaced_gpu_slots(
    subagents: SubagentsConfig, runtime: BrainRuntimeConfig
) -> SubagentsConfig:
    """Log a warning when a GPU slot can never be leased, since its server holds memory unused."""
    slots = gpu_slots(subagents)
    placed = placed_at_once(subagents, runtime, slots)
    if placed < slots:
        _logger.warning(
            UNPLACED_GPU_SLOTS,
            extra={
                "gpu_slots": slots,
                "placed_at_once": placed,
                "vram_soft_cap_gb": runtime.vram_soft_cap_gb,
                "cortex_reservation_gb": runtime.cortex_reservation_gb,
                "vram_gb": subagents.vram_gb,
            },
        )
    return subagents
