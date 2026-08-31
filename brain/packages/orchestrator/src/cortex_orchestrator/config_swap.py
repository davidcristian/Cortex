"""Brain-handoff configuration: env-driven, root-read only."""

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import (
    DEFAULT_SWAP_DRAIN_TIMEOUT_S,
    DEFAULT_SWAP_LOAD_TIMEOUT_S,
    DEFAULT_TIER_HEAL_INTERVAL_S,
    ResidencyPlan,
)

DEFAULT_BRAIN_MODEL = "brain"

# Must stay above the sidecar's worst stop, which is its SIGTERM grace plus its SIGKILL reap
# bound plus the probe timeout a queued status spends inside it: 5 s + 10 s + 30 s under the
# shipped defaults. Below that, a slow but correct eviction reads as a dead sidecar.
DEFAULT_MODELHOST_TIMEOUT_S = 60.0

ModelHostBackendName = Literal["none", "scripted", "supervisor"]


class SwapConfig(BaseSettings):
    """Whether a turn may hand itself to the deep model, and what the swap looks like."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_", validate_by_name=True)

    escalation: bool = False
    modelhost_backend: ModelHostBackendName = "none"
    modelhost_endpoint: str = ""
    modelhost_timeout_s: float = Field(default=DEFAULT_MODELHOST_TIMEOUT_S, gt=0)
    brain_model: str = Field(default=DEFAULT_BRAIN_MODEL, validation_alias="CORTEX_MODEL_BRAIN")
    brain_endpoint: str = ""
    evict_models: tuple[str, ...] = Field(default=(), validation_alias="CORTEX_SWAP_EVICT_MODELS")
    coresident: bool = Field(default=False, validation_alias="CORTEX_SWAP_CORESIDENT")
    brain_vram_mib: int = Field(default=0, ge=0, validation_alias="CORTEX_SWAP_BRAIN_VRAM_MIB")
    brain_decode_tps: float = Field(
        default=0.0, ge=0, validation_alias="CORTEX_SWAP_BRAIN_DECODE_TPS"
    )
    swap_drain_timeout_s: float = Field(default=DEFAULT_SWAP_DRAIN_TIMEOUT_S, ge=0)
    swap_load_timeout_s: float = Field(default=DEFAULT_SWAP_LOAD_TIMEOUT_S, ge=0)
    swap_tier_heal_s: float = Field(default=DEFAULT_TIER_HEAL_INTERVAL_S, gt=0)

    @model_validator(mode="after")
    def _escalation_needs_a_host_and_an_endpoint(self) -> "SwapConfig":
        if not self.escalation:
            return self
        if self.modelhost_backend == "none":
            msg = (
                "CORTEX_MODELHOST_BACKEND must name a model host when CORTEX_ESCALATION=1: "
                "without one, nothing can evict or load a model, so the escalate tool could "
                "only ever refuse"
            )
            raise ValueError(msg)
        if not self.brain_endpoint:
            msg = "CORTEX_BRAIN_ENDPOINT is required when CORTEX_ESCALATION=1"
            raise ValueError(msg)
        if self.modelhost_backend == "supervisor" and not self.modelhost_endpoint:
            msg = (
                "CORTEX_MODELHOST_ENDPOINT is required when "
                "CORTEX_MODELHOST_BACKEND=supervisor: the adapter would have nowhere to send a "
                "start or a stop, so every swap would fail at its first step"
            )
            raise ValueError(msg)
        return self._coresidency_needs_a_measured_fit()

    def _coresidency_needs_a_measured_fit(self) -> "SwapConfig":
        """Raise for a co-resident deployment that never stated what the deep model costs."""
        if self.coresident and self.modelhost_backend == "supervisor" and not self.brain_vram_mib:
            msg = (
                "CORTEX_SWAP_BRAIN_VRAM_MIB is required when CORTEX_SWAP_CORESIDENT=1: keeping "
                "peers resident through a handoff is a claim about how much of the card is "
                "free, and nothing can check that claim without the deep model's measured cost. "
                "A card that cannot hold the pair does not refuse the load, it pages the "
                "overcommit to system memory and halves the deep model's decode rate "
                "(docs/runbooks/model-swap.md)"
            )
            raise ValueError(msg)
        return self

    def residency_plan(self, cortex_model: str) -> ResidencyPlan:
        """The core value the manager, the conductor, and boot recovery all read."""
        return ResidencyPlan(
            cortex_model=cortex_model,
            brain_model=self.brain_model,
            evict_models=self.evict_models,
            coresident=self.coresident,
            brain_vram_mib=self.brain_vram_mib,
            brain_decode_tps=self.brain_decode_tps,
            drain_timeout_s=self.swap_drain_timeout_s,
            load_timeout_s=self.swap_load_timeout_s,
            control_deadline_s=self.modelhost_timeout_s,
        )
