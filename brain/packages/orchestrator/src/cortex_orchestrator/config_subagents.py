"""Subagent-delegation configuration: env-driven, root-read only."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import (
    ATTEMPTS_PER_ADMISSION,
    DEFAULT_ADMISSION_WAIT_S,
    DEFAULT_SUBAGENT_MAX_TOKENS,
    DEFAULT_SUBAGENT_RUN_TIMEOUT_S,
    AttemptBounds,
)

SubagentsBackendName = Literal["none", "llamacpp"]

DEFAULT_SUBAGENT_MODEL = "subagent"

DEFAULT_SUBAGENT_DESCRIPTION = "the injection-robust default; safe for any subtask"

# The soft admission ceilings, and the twins of the CPU subagent container's own limits: the
# scheduler stops admitting at these sums and `docker/docker-compose.subagents.yml` caps the
# container from the same numbers, so retuning one alone caps what the other admits against.
DEFAULT_MEM_BUDGET_GB = 8.0

DEFAULT_CPU_BUDGET = 4.0

# One subagent's own ask. The VRAM figure sits about 174 MiB above the 3338 to 3410 MiB the
# GPU-placed tier costs at its shipped shape, and the memory figure rounds the CPU entry's
# 2.5 GiB RSS up so two are admitted under the budget. The CPU ask is a placeholder.
DEFAULT_VRAM_GB = 3.5
DEFAULT_CPUS = 2.0
DEFAULT_MEMORY_GB = 3.0

# How long a delegated stream may send nothing before the adapter gives up on it. Loose where
# the resident tier's is tight, because a CPU server decodes at about 0.35 tok/s: it is twice
# the longest whole subtask measured there, so it fires on a wedge and not on slowness.
DEFAULT_STALL_TIMEOUT_S = 600.0


class SubagentRosterEntry(BaseModel):
    """One alternate subagent model: a ``CORTEX_SUBAGENTS_ROSTER__<name>`` JSON value."""

    endpoint: str = Field(min_length=1)
    gpu_endpoint: str = ""
    vram_gb: float = Field(default=DEFAULT_VRAM_GB, gt=0)
    cpus: float = Field(default=DEFAULT_CPUS, gt=0)
    memory_gb: float = Field(default=DEFAULT_MEMORY_GB, gt=0)
    description: str = ""


class SubagentsConfig(BaseSettings):
    """Whether the cortex can delegate to subagents."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_SUBAGENTS_", env_nested_delimiter="__")

    backend: SubagentsBackendName = "none"
    endpoint: str = ""
    gpu_endpoint: str = ""
    model: str = DEFAULT_SUBAGENT_MODEL
    model_description: str = DEFAULT_SUBAGENT_DESCRIPTION
    vram_gb: float = Field(default=DEFAULT_VRAM_GB, gt=0)
    cpus: float = Field(default=DEFAULT_CPUS, gt=0)
    memory_gb: float = Field(default=DEFAULT_MEMORY_GB, gt=0)
    cpu_budget: float = Field(default=DEFAULT_CPU_BUDGET, gt=0)
    mem_budget_gb: float = Field(default=DEFAULT_MEM_BUDGET_GB, gt=0)
    roster: dict[str, SubagentRosterEntry] = {}
    stall_timeout_s: float = Field(default=DEFAULT_STALL_TIMEOUT_S, gt=0)
    admission_wait_s: float = Field(default=DEFAULT_ADMISSION_WAIT_S, ge=0)
    max_tokens: int = Field(default=DEFAULT_SUBAGENT_MAX_TOKENS, ge=1)
    run_timeout_s: float = Field(default=DEFAULT_SUBAGENT_RUN_TIMEOUT_S, gt=0)
    constrain_output: bool = True

    @model_validator(mode="after")
    def _llamacpp_needs_both_endpoints(self) -> "SubagentsConfig":
        if self.backend == "llamacpp" and not (self.endpoint and self.gpu_endpoint):
            msg = (
                "CORTEX_SUBAGENTS_ENDPOINT and CORTEX_SUBAGENTS_GPU_ENDPOINT are required when "
                "CORTEX_SUBAGENTS_BACKEND=llamacpp"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _roster_must_not_shadow_the_default(self) -> "SubagentsConfig":
        if self.model in self.roster:
            msg = (
                f"CORTEX_SUBAGENTS_ROSTER__{self.model} collides with CORTEX_SUBAGENTS_MODEL; "
                "the default entry's resources come from the flat fields"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _every_ask_must_fit_the_whole_budget(self) -> "SubagentsConfig":
        """Fail at boot on an entry the scheduler could never admit."""
        for name, entry in self.named_roster.items():
            if entry.cpus > self.cpu_budget or entry.memory_gb > self.mem_budget_gb:
                msg = (
                    f"subagent {name!r} asks for cpus={entry.cpus}, memory_gb={entry.memory_gb}, "
                    f"which exceeds the whole admission budget (cpu_budget={self.cpu_budget}, "
                    f"mem_budget_gb={self.mem_budget_gb}); no spawn of it could ever be admitted"
                )
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _the_run_deadline_must_outlast_the_stall_ceiling(self) -> "SubagentsConfig":
        """Fail at boot on a pair of bounds whose precedence would be the wrong way round."""
        if self.run_timeout_s <= self.stall_timeout_s:
            msg = (
                f"CORTEX_SUBAGENTS_RUN_TIMEOUT_S ({self.run_timeout_s}) must be greater than "
                f"CORTEX_SUBAGENTS_STALL_TIMEOUT_S ({self.stall_timeout_s}); a deadline on the "
                "whole run that does not outlast the ceiling on one silent gap would report every "
                "wedged stream as a run that would not stop, and a wedge is the one failure a "
                "re-run on another target can help"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _the_run_deadline_must_fit_inside_the_queue_for_it(self) -> "SubagentsConfig":
        """Fail at boot on a hold no queued peer would still be waiting through."""
        hold_s = ATTEMPTS_PER_ADMISSION * self.run_timeout_s
        if self.admission_wait_s > 0 and hold_s >= self.admission_wait_s:
            msg = (
                f"CORTEX_SUBAGENTS_RUN_TIMEOUT_S ({self.run_timeout_s}) is spent up to "
                f"{ATTEMPTS_PER_ADMISSION} times inside one admission, so a task can hold its "
                f"room for {hold_s} s, which must be less than "
                f"CORTEX_SUBAGENTS_ADMISSION_WAIT_S ({self.admission_wait_s}); a run allowed to "
                "hold its admission for at least as long as a peer will queue for that admission "
                "makes a working pool read as one that refuses spawns under load, and the "
                "refusal names the queue rather than the deadline that filled it. Lower the run "
                "deadline, or raise the wait above the hold (docs/runbooks/subagents-cpu.md)"
            )
            raise ValueError(msg)
        return self

    @property
    def attempt_bounds(self) -> AttemptBounds:
        """How far one delegated attempt may go, as the core's value."""
        return AttemptBounds(max_tokens=self.max_tokens, timeout_s=self.run_timeout_s)

    @property
    def named_roster(self) -> dict[str, SubagentRosterEntry]:
        """Every roster entry by name, with the flat-field default first and alternates sorted."""
        if self.backend != "llamacpp":
            return {}
        default = SubagentRosterEntry(
            endpoint=self.endpoint,
            gpu_endpoint=self.gpu_endpoint,
            vram_gb=self.vram_gb,
            cpus=self.cpus,
            memory_gb=self.memory_gb,
            description=self.model_description,
        )
        alternates = {
            name: entry.model_copy(update={"gpu_endpoint": entry.gpu_endpoint or entry.endpoint})
            for name, entry in sorted(self.roster.items())
        }
        return {self.model: default} | alternates
