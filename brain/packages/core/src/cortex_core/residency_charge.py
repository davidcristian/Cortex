"""The two ends of the handoff window, as the subagent placer sees them."""

from cortex_core.model_host import ResidencyPlan
from cortex_core.ports import SubagentPlacer


def charge_handoff(placer: SubagentPlacer | None, plan: ResidencyPlan) -> None:
    """Tell the placer the deep model holds the card, when the deployment said what it costs."""
    if placer is not None and plan.brain_vram_mib > 0:
        placer.charge_handoff(resident_gb=plan.brain_vram_gb)


def charge_baseline(placer: SubagentPlacer | None) -> None:
    """Tell the placer the cortex holds the card again (idempotent, and a no-op with no placer)."""
    if placer is not None:
        placer.charge_baseline()
