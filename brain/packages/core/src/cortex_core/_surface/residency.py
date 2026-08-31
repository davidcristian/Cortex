"""Public core names for which model is resident on the GPU and the handoff that swaps it.

Re-exported wholesale by the ``cortex_core`` barrel, so the import path for every name below
stays ``cortex_core``. ``__all__`` is this file's contract.
"""

from cortex_core.cadence import (
    MIN_CADENCE_TOKENS,
    NO_CADENCE_TERMS,
    CadenceReading,
    CadenceTerms,
    CadenceWatch,
)
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
from cortex_core.residency_pace import (
    DEFAULT_SPILL_DWELL_S,
    SPILLED_PACE_DETAIL,
    HandoffPace,
)
from cortex_core.residency_regain import heal_standing_residency, regain_residency
from cortex_core.residency_state import (
    RESIDENCY_BOOT_FAILED,
    RESIDENCY_DEEP,
    RESIDENCY_LOADING,
    RESIDENCY_LOST,
    RESIDENCY_RESTORING,
    RESIDENCY_SERVING,
    ResidencyReport,
    with_note,
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
from cortex_core.swap_reasons import DRAIN_TIMEOUT_REASON, STRANDED_REASON, TORN_DOWN_REASON
from cortex_core.swap_recovery import converge_residency, recover_handoffs

__all__ = [
    "ALREADY_ACTIVE_NOTE",
    "BRAIN_FAILED_NOTE",
    "DEFAULT_HEALTH_POLL_INTERVAL_S",
    "DEFAULT_SPILL_DWELL_S",
    "DEFAULT_SWAP_DRAIN_TIMEOUT_S",
    "DEFAULT_SWAP_LOAD_TIMEOUT_S",
    "DEFAULT_TIER_HEAL_INTERVAL_S",
    "DRAINING_DETAIL",
    "DRAIN_TIMEOUT_NOTE",
    "DRAIN_TIMEOUT_REASON",
    "LOADING_DETAIL",
    "MIN_CADENCE_TOKENS",
    "NO_CADENCE_TERMS",
    "OPAQUE_TURN_NOTE",
    "RESIDENCY_BOOT_FAILED",
    "RESIDENCY_DEEP",
    "RESIDENCY_LOADING",
    "RESIDENCY_LOST",
    "RESIDENCY_RESTORING",
    "RESIDENCY_SERVING",
    "RESTORE_FAILED_NOTE",
    "RESTORING_DETAIL",
    "SPILLED_PACE_DETAIL",
    "STORE_FAILED_NOTE",
    "STRANDED_REASON",
    "SWAPPING_STATE",
    "SWAP_FAILED_NOTE",
    "TIERS_MISSING_DETAIL",
    "TORN_DOWN_REASON",
    "UNHOSTED_TIER_NOTE",
    "WORKING_DETAIL",
    "CadenceReading",
    "CadenceTerms",
    "CadenceWatch",
    "ControlBounds",
    "DeviceMemory",
    "EscalationRefs",
    "EscalationSlot",
    "HandoffPace",
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
    "heal_standing_residency",
    "recover_handoffs",
    "regain_residency",
    "sweep_tiers",
    "with_note",
]
