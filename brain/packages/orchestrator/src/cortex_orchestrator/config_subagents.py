"""Subagent-delegation configuration (ADR-0010/0012/0018): env-driven, root-read only.

Split from ``config.py`` for the 300-line cap (the ``subagent_builders.py`` precedent) when
ADR-0022 added the seam-confirm and tool-gating settings there; same rules, meaning read exclusively
by the composition root, everything below the edge receives plain values.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import DEFAULT_ADMISSION_WAIT_S

SubagentsBackendName = Literal["none", "llamacpp"]

# The logical id of the subagent tier (ADR-0004); deployments override via CORTEX_SUBAGENTS_MODEL.
DEFAULT_SUBAGENT_MODEL = "subagent"

# What the spawn spec advertises for the default entry unless the deployment overrides it
# (CORTEX_SUBAGENTS_MODEL_DESCRIPTION). Trade-off text only. Safety never rides a description
# (ADR-0017 is enforced in the core, whatever this says).
DEFAULT_SUBAGENT_DESCRIPTION = "the injection-robust default; safe for any subtask"


class SubagentRosterEntry(BaseModel):
    """One alternate subagent model: a ``CORTEX_SUBAGENTS_ROSTER__<name>`` JSON value (ADR-0018).

    ``endpoint`` (required, non-empty) is the entry's CPU ``llama-server`` base URL; an empty
    ``gpu_endpoint`` falls back to it (normalized in ``named_roster``, per the interim one-executor
    stance, ADR-0012 deferral). The resource numbers default like the flat fields, so an alternate
    that declares no VRAM ask is charged the only GPU subagent tier this repo has measured, which
    over-charges anything smaller and therefore errs toward the CPU; ``description`` is the
    trade-off text the spawn spec advertises verbatim (it informs the cortex's optimization, never
    safety, since ADR-0017 is enforced in the core).
    """

    endpoint: str = Field(min_length=1)
    gpu_endpoint: str = ""
    vram_gb: float = Field(default=3.5, gt=0)
    cpus: float = Field(default=2.0, gt=0)
    memory_gb: float = Field(default=2.0, gt=0)
    description: str = ""


class SubagentsConfig(BaseSettings):
    """Whether the cortex can delegate to subagents (ADR-0010, ADR-0012, ADR-0018).

    ``none`` (the default) disables delegation. The cortex's tool set has no ``spawn_subagents``
    and the turn path is byte-for-byte the Slice 6 behavior, so CI and the no-GPU dev loop run
    subagent-free. ``llamacpp`` enables GPU-first placement (ADR-0012) and requires both
    ``gpu_endpoint`` (the GPU subagent ``llama-server``, ``-ngl 99``) and ``endpoint`` (the CPU
    overflow ``llama-server``, ``-ngl 0``), each a base URL in ``docker-compose.subagents.yml``.

    ``vram_gb``/``cpus``/``memory_gb`` are one subagent's resource ask (VRAM footprint the placer
    fit-tests, and the per-container ``--cpus``/``--memory`` the scheduler sums); ``cpu_budget``/
    ``mem_budget_gb`` are the soft admission ceilings (sum of admitted asks ≤ target). ``vram_gb``
    is measured: 3.5 GiB since 2026-08-08, sized above the 3338 to 3410 MiB the GPU-placed subagent
    tier costs at its shipped shape (ADR-0012 measured-ask addendum), and it matches the value
    ``docker-compose.subagents.yml`` sets so the two declarations of one number agree. The CPU and
    memory asks stay host-measured placeholders.

    The flat fields above define the roster's **default entry** as the injection-robust ADR-0004
    pick the wiring pins untrusted-content spawns to (ADR-0017); ``model`` names it and
    ``model_description`` is its advertised text. ``CORTEX_SUBAGENTS_ROSTER__<name>`` adds one
    **alternate** model per key (a JSON ``SubagentRosterEntry``), so layered compose overrides
    each contribute their own entry (ADR-0018). A roster key naming the default is rejected, since
    the default's resources come from the flat fields, one source of truth.
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_SUBAGENTS_", env_nested_delimiter="__")

    backend: SubagentsBackendName = "none"
    endpoint: str = ""
    gpu_endpoint: str = ""
    model: str = DEFAULT_SUBAGENT_MODEL
    model_description: str = DEFAULT_SUBAGENT_DESCRIPTION
    vram_gb: float = Field(default=3.5, gt=0)
    cpus: float = Field(default=2.0, gt=0)
    memory_gb: float = Field(default=2.0, gt=0)
    cpu_budget: float = Field(default=4.0, gt=0)
    mem_budget_gb: float = Field(default=8.0, gt=0)
    roster: dict[str, SubagentRosterEntry] = {}
    # env CORTEX_SUBAGENTS_STALL_TIMEOUT_S is how long a delegated stream may send nothing before
    # the adapter gives up on it (ADR-0005 stall-ceiling addendum), bounding the gap between
    # chunks and never the generation. Loose where the resident tier's is tight, because this one
    # covers a CPU server decoding at about 0.35 tok/s: the default is twice the longest whole
    # subtask measured on the shipped default entry, so it fires on a wedge and not on slowness.
    stall_timeout_s: float = Field(default=600.0, gt=0)
    # env CORTEX_SUBAGENTS_ADMISSION_WAIT_S is how long a spawn may sit in the admission queue
    # before it is refused instead of waiting for room forever (ADR-0012 bounded-admission-wait
    # addendum). The default is twice the worst wait a full batch can legitimately produce
    # against the budgets above, so it fires on a pool that is not draining rather than on one
    # that is merely slow. Zero means never queue: refuse anything that does not fit right now.
    admission_wait_s: float = Field(default=DEFAULT_ADMISSION_WAIT_S, ge=0)
    # Constrain a tool-less subagent's reply to the fixed envelope (ADR-0028), killing
    # format-laundering on the weak-model niche. On by default; the raw stream is restored per
    # niche with CORTEX_SUBAGENTS_CONSTRAIN_OUTPUT=false.
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
        """Refuse at boot an entry the scheduler could only ever refuse (ADR-0012 addendum).

        ``ResourceBudgetScheduler.admit`` waits while a charge merely does not fit *right now*,
        but raises when it exceeds the whole budget, since no peer releasing anything could
        admit it. Left to runtime that is a spawn refused on every attempt, discovered only when
        the cortex delegates and visible only inside a subagent result. It is a wiring error, so
        it belongs here with the other two: the deployment cannot start describing a subagent
        the machine it configures may never run. Equality passes (such an entry runs alone).
        """
        for name, entry in self.named_roster.items():
            if entry.cpus > self.cpu_budget or entry.memory_gb > self.mem_budget_gb:
                msg = (
                    f"subagent {name!r} asks for cpus={entry.cpus}, memory_gb={entry.memory_gb}, "
                    f"which exceeds the whole admission budget (cpu_budget={self.cpu_budget}, "
                    f"mem_budget_gb={self.mem_budget_gb}); no spawn of it could ever be admitted"
                )
                raise ValueError(msg)
        return self

    @property
    def named_roster(self) -> dict[str, SubagentRosterEntry]:
        """Every roster entry by name, with the flat-field default first and alternates sorted.

        Empty unless ``backend`` is ``llamacpp`` (the flat endpoints are only validated there).
        The default entry is synthesized from the flat fields; each alternate's empty
        ``gpu_endpoint`` is normalized to its ``endpoint``, so the builders read ready-to-dial
        values. The mapping is keyed (order carries no semantics) but default-first reads
        naturally in logs and tests.
        """
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
