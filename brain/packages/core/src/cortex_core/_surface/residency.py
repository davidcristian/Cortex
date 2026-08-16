"""Public core names for which model is on the GPU, and the handoff that changes the answer.

One of the area sub-barrels the ``cortex_core`` barrel re-exports wholesale, so the
import path for every name below stays ``cortex_core``. ``__all__`` is what that
wildcard re-exports, and it is this file's contract.
"""

from cortex_core.cadence import MIN_CADENCE_TOKENS, CadenceReading, CadenceWatch
from cortex_core.handoff import EscalationRefs, EscalationSlot, HandoffRecord, HandoffState
from cortex_core.health_gate import await_model_ready
from cortex_core.model import ModelLease, SingleResidentModelManager
from cortex_core.model_host import (
    DEFAULT_HEALTH_POLL_INTERVAL_S,
    DEFAULT_SWAP_DRAIN_TIMEOUT_S,
    DEFAULT_SWAP_LOAD_TIMEOUT_S,
    ControlBounds,
    DeviceMemory,
    ModelHostState,
    ResidencyPlan,
)
from cortex_core.residency import SwappingModelManager
from cortex_core.residency_heal import DEFAULT_TIER_HEAL_INTERVAL_S, TierHealer
from cortex_core.residency_state import (
    RESIDENCY_BOOT_FAILED,
    RESIDENCY_DEEP,
    RESIDENCY_LOADING,
    RESIDENCY_LOST,
    RESIDENCY_RESTORING,
    RESIDENCY_SERVING,
    ResidencyReport,
)
from cortex_core.residency_sweep import sweep_tiers
from cortex_core.residency_tiers import TIERS_MISSING_DETAIL, StandingTiers, TierFault
from cortex_core.swap_conductor import SwapConductor
from cortex_core.swap_notes import (
    ALREADY_ACTIVE_NOTE,
    BRAIN_FAILED_NOTE,
    DRAIN_TIMEOUT_NOTE,
    DRAINING_DETAIL,
    LOADING_DETAIL,
    OPAQUE_TURN_NOTE,
    RESTORE_FAILED_NOTE,
    RESTORING_DETAIL,
    STORE_FAILED_NOTE,
    SWAP_FAILED_NOTE,
    SWAPPING_STATE,
    UNHOSTED_TIER_NOTE,
    WORKING_DETAIL,
)
from cortex_core.swap_recovery import converge_residency, recover_handoffs

__all__ = [
    "ALREADY_ACTIVE_NOTE",
    "BRAIN_FAILED_NOTE",
    "DEFAULT_HEALTH_POLL_INTERVAL_S",
    "DEFAULT_SWAP_DRAIN_TIMEOUT_S",
    "DEFAULT_SWAP_LOAD_TIMEOUT_S",
    "DEFAULT_TIER_HEAL_INTERVAL_S",
    "DRAINING_DETAIL",
    "DRAIN_TIMEOUT_NOTE",
    "LOADING_DETAIL",
    "MIN_CADENCE_TOKENS",
    "OPAQUE_TURN_NOTE",
    "RESIDENCY_BOOT_FAILED",
    "RESIDENCY_DEEP",
    "RESIDENCY_LOADING",
    "RESIDENCY_LOST",
    "RESIDENCY_RESTORING",
    "RESIDENCY_SERVING",
    "RESTORE_FAILED_NOTE",
    "RESTORING_DETAIL",
    "STORE_FAILED_NOTE",
    "SWAPPING_STATE",
    "SWAP_FAILED_NOTE",
    "TIERS_MISSING_DETAIL",
    "UNHOSTED_TIER_NOTE",
    "WORKING_DETAIL",
    "CadenceReading",
    "CadenceWatch",
    "ControlBounds",
    "DeviceMemory",
    "EscalationRefs",
    "EscalationSlot",
    "HandoffRecord",
    "HandoffState",
    "ModelHostState",
    "ModelLease",
    "ResidencyPlan",
    "ResidencyReport",
    "SingleResidentModelManager",
    "StandingTiers",
    "SwapConductor",
    "SwappingModelManager",
    "TierFault",
    "TierHealer",
    "await_model_ready",
    "converge_residency",
    "recover_handoffs",
    "sweep_tiers",
]
