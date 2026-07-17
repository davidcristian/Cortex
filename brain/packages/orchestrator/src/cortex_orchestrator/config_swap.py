"""Brain-handoff configuration (ADR-0030): env-driven, root-read only.

Its own module per the ``config_tools.py`` / ``config_schedule.py`` split precedent. It holds
the one switch that turns the whole capability on (``CORTEX_ESCALATION``, **off by default**,
so CI and the GPU-less dev loop behave exactly as they did before this landed) plus the
topology and bounds of the swap it enables.

The switch is fail-closed in both directions: with escalation off nothing is built, the
``escalate_to_brain`` built-in is never advertised, and no boot recovery runs; with it on, the
deployment must say which model host serves the swap and where the deep model answers, or boot
fails loudly rather than advertising a handoff that could only ever refuse.
"""

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import (
    DEFAULT_SWAP_DRAIN_TIMEOUT_S,
    DEFAULT_SWAP_LOAD_TIMEOUT_S,
    ResidencyPlan,
)

# The logical id of the deep model (ADR-0004: logical ids, never paths), overridable via
# CORTEX_MODEL_BRAIN exactly as the cortex tier's id is.
DEFAULT_BRAIN_MODEL = "brain"

ModelHostBackendName = Literal["none", "scripted"]


class SwapConfig(BaseSettings):
    """Whether a turn may hand itself to the deep model, and what the swap looks like.

    ``CORTEX_ESCALATION`` (default off) gates everything: the ``escalate_to_brain`` built-in's
    registration, the escalating turn wrapper, the swap conductor, and boot recovery.

    ``CORTEX_MODELHOST_BACKEND`` picks who owns the model processes. ``none`` (the default)
    means nobody does, which is why enabling escalation without setting it is a boot failure.
    ``scripted`` runs the in-core ``ScriptedModelHost``: it tracks residency honestly but starts
    no process, so the whole path (record, drain, scope, deep phase, swap back, recovery) runs
    end to end against whatever inference backend is configured. It is the dev and CI backend,
    named for what it is; the real supervisor sidecar arrives as a further backend value and is
    what makes the swap move actual weights.

    ``CORTEX_MODEL_BRAIN`` and ``CORTEX_BRAIN_ENDPOINT`` are the deep tier's logical id and the
    base URL that serves it (required when escalation is on: a residency scope must be able to
    lease an endpoint for the model it swapped in). ``CORTEX_SWAP_EVICT_MODELS`` names any
    further hosted models a swap must stop first, the GPU-placed subagent tier being the one
    that will need it; while the deep model is resident it is alone on the GPU.
    ``CORTEX_SWAP_DRAIN_TIMEOUT_S`` (60 s) bounds the wait for delegated work to finish before
    anything is evicted, and ``CORTEX_SWAP_LOAD_TIMEOUT_S`` (300 s) bounds the wait for a model
    to report ready after it is started.
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_", validate_by_name=True)

    escalation: bool = False
    modelhost_backend: ModelHostBackendName = "none"
    # The dictated env names break the prefix pattern, hence the explicit aliases.
    brain_model: str = Field(default=DEFAULT_BRAIN_MODEL, validation_alias="CORTEX_MODEL_BRAIN")
    brain_endpoint: str = ""
    evict_models: tuple[str, ...] = Field(default=(), validation_alias="CORTEX_SWAP_EVICT_MODELS")
    swap_drain_timeout_s: float = Field(default=DEFAULT_SWAP_DRAIN_TIMEOUT_S, ge=0)
    swap_load_timeout_s: float = Field(default=DEFAULT_SWAP_LOAD_TIMEOUT_S, ge=0)

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
        return self

    def residency_plan(self, cortex_model: str) -> ResidencyPlan:
        """The core value the manager, the conductor, and boot recovery all read.

        ``cortex_model`` comes from the runtime config (``CORTEX_MODEL_CORTEX``), so the tier
        ids stay declared in one place each and cannot drift between the lease and the swap.
        """
        return ResidencyPlan(
            cortex_model=cortex_model,
            brain_model=self.brain_model,
            evict_models=self.evict_models,
            drain_timeout_s=self.swap_drain_timeout_s,
            load_timeout_s=self.swap_load_timeout_s,
        )
