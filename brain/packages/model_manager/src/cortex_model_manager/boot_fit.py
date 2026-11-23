"""After the boot pass: read the card once every boot tier serves, and warn when it is short."""

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass

from cortex_core import ModelHostState
from cortex_model_manager.device_memory import DeviceMemoryProbe
from cortex_model_manager.restarts import DEFAULT_STABLE_AFTER_S
from cortex_model_manager.supervisor import ModelSupervisor

# The free memory every reading of the 24 GB card keeps at its highest point, with the desktop's
# apps beside it (docs/readings/model-baseline.md, "Budget").
BOOT_FREE_FLOOR_MIB = 1536

BOOT_FIT_POLL_S = 2.0

_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class BootFit:
    """The free memory the boot tiers must leave, and how often and how long to wait for them."""

    floor_mib: int = BOOT_FREE_FLOOR_MIB
    poll_s: float = BOOT_FIT_POLL_S
    bound_s: float = DEFAULT_STABLE_AFTER_S

    async def watch(
        self, supervisor: ModelSupervisor, boot_models: Sequence[str], card: DeviceMemoryProbe
    ) -> None:
        """Wait until every boot tier is ready, then compare the card's free memory to the floor."""
        served = tuple(model for model in boot_models if model in supervisor.models)
        try:
            async with asyncio.timeout(self.bound_s):
                while not await _all_ready(supervisor, served):  # noqa: ASYNC110 -- a probe, no event
                    await asyncio.sleep(self.poll_s)
        except TimeoutError:
            _logger.info(
                "not every boot tier was ready in time, so the card was not read for fit",
                extra={"bound_s": self.bound_s},
            )
            return
        memory = await card.read()
        if memory is None:
            return
        fields = {
            "free_mib": memory.free_mib,
            "total_mib": memory.total_mib,
            "floor_mib": self.floor_mib,
            "contexts": " ".join(f"{m}={supervisor.roster[m].ctx_size}" for m in served),
        }
        if memory.free_mib < self.floor_mib:
            _logger.warning(
                "the tiers started at boot leave the card less free memory than its floor",
                extra=fields,
            )
            return
        _logger.info("the tiers started at boot leave the card its free floor", extra=fields)


async def _all_ready(supervisor: ModelSupervisor, models: Sequence[str]) -> bool:
    """Whether each of ``models`` answers ready now."""
    for model in models:
        if (await supervisor.status(model)).state is not ModelHostState.READY:
            return False
    return True
