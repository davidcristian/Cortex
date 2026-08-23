"""Subagent-delegation configuration (ADR-0010/0012/0018): env-driven, root-read only.

Split from ``config.py`` for the 300-line cap (the ``subagent_builders.py`` precedent) when
ADR-0022 added the seam-confirm and tool-gating settings there; same rules, meaning read exclusively
by the composition root, everything below the edge receives plain values.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import (
    DEFAULT_ADMISSION_WAIT_S,
    DEFAULT_SUBAGENT_MAX_TOKENS,
    DEFAULT_SUBAGENT_RUN_TIMEOUT_S,
    AttemptBounds,
)

SubagentsBackendName = Literal["none", "llamacpp"]

# The logical id of the subagent tier (ADR-0004); deployments override via CORTEX_SUBAGENTS_MODEL.
DEFAULT_SUBAGENT_MODEL = "subagent"

# What the spawn spec advertises for the default entry unless the deployment overrides it
# (CORTEX_SUBAGENTS_MODEL_DESCRIPTION). Trade-off text only. Safety never rides a description
# (ADR-0017 is enforced in the core, whatever this says).
DEFAULT_SUBAGENT_DESCRIPTION = "the injection-robust default; safe for any subtask"

# The soft admission ceiling on the memory of everything admitted at once (ADR-0012), in GB, and
# the hard twin of the CPU subagent container's own `mem_limit`: the scheduler stops admitting at
# this sum and the cgroup is what happens if anything ever admits past it. A module constant
# rather than a literal inside `Field(...)` so the constant scan can read it, which is what ties
# this declaration to the four spellings of it in `docker/docker-compose.subagents.yml` (the
# environment passthrough, the container's memory and swap limits, and the comment that claims
# the twinning, where docker's size suffix takes the same number without its point). Retuning
# here alone would leave that container capped at the old number while the scheduler admitted
# against the new one, which is the failure the resource governance exists to prevent.
DEFAULT_MEM_BUDGET_GB = 8.0

# The CPU half of that pair, named for the same reason and tied the same way: the scheduler admits
# against this sum and the container's own `cpus` cap is set from the same compose variable, so a
# retune here alone would hand the CPU subagent server fewer cores than the admissions it is
# serving were charged against. Nothing catches that at runtime; it reads as a tier that got slow.
DEFAULT_CPU_BUDGET = 4.0

# One subagent's own ask, which the scheduler charges against the budgets above and the placer
# fit-tests the VRAM half of. All three are what `docker/docker-compose.subagents.yml` sets for the
# entry it ships, and they are declared here so a deployment that wires subagents without that file
# charges what the measured stack charges rather than a number nobody took. Each is held to its
# compose spelling by the constant scan (`scripts/crosscheck.py`).
#
# The VRAM ask is measured (ADR-0012 measured-ask addendum): 3.5 GiB sits about 174 MiB above the
# 3338 to 3410 MiB the GPU-placed tier costs at its shipped shape. The memory ask is measured too,
# at about 2.5 GiB RSS for the CPU entry, rounded up so two are admitted under the memory budget;
# it was 2.0 here until the two declarations were tied, which under-charged every spawn by half a
# gigabyte and is the same unsafe direction the VRAM ask was corrected for, admitting onto room the
# container's own cap would then refuse. The CPU ask stays a host-measured placeholder.
DEFAULT_VRAM_GB = 3.5
DEFAULT_CPUS = 2.0
DEFAULT_MEMORY_GB = 3.0


class SubagentRosterEntry(BaseModel):
    """One alternate subagent model: a ``CORTEX_SUBAGENTS_ROSTER__<name>`` JSON value (ADR-0018).

    ``endpoint`` (required, non-empty) is the entry's CPU ``llama-server`` base URL; an empty
    ``gpu_endpoint`` falls back to it (normalized in ``named_roster``, per the interim one-executor
    stance, ADR-0012 deferral). The resource numbers default like the flat fields, off the same
    module constants so the two declarations cannot drift, so an alternate that declares no VRAM
    ask is charged the only GPU subagent tier this repo has measured, which over-charges anything
    smaller and therefore errs toward the CPU; ``description`` is the
    trade-off text the spawn spec advertises verbatim (it informs the cortex's optimization, never
    safety, since ADR-0017 is enforced in the core).
    """

    endpoint: str = Field(min_length=1)
    gpu_endpoint: str = ""
    vram_gb: float = Field(default=DEFAULT_VRAM_GB, gt=0)
    cpus: float = Field(default=DEFAULT_CPUS, gt=0)
    memory_gb: float = Field(default=DEFAULT_MEMORY_GB, gt=0)
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
    ``mem_budget_gb`` are the soft admission ceilings (sum of admitted asks ≤ target). All five
    default to a module constant above rather than to a literal, so `scripts/crosscheck.py` reads
    the declaration and holds every spelling of it in ``docker-compose.subagents.yml`` to this one
    number: retuning either budget here alone used to leave the CPU subagent container capped
    against the old one, and retuning an ask left the shipped stack charging a different number
    from the one a hand-wired deployment charges. ``vram_gb`` and ``memory_gb`` are measured
    (ADR-0012 measured-ask and budget-tie addenda); the CPU ask stays a host-measured placeholder.

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
    vram_gb: float = Field(default=DEFAULT_VRAM_GB, gt=0)
    cpus: float = Field(default=DEFAULT_CPUS, gt=0)
    memory_gb: float = Field(default=DEFAULT_MEMORY_GB, gt=0)
    cpu_budget: float = Field(default=DEFAULT_CPU_BUDGET, gt=0)
    mem_budget_gb: float = Field(default=DEFAULT_MEM_BUDGET_GB, gt=0)
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
    # that is merely slow. Zero means never queue: refuse anything that does not fit right now,
    # which is also the one setting of it the run deadline is not ordered against below.
    admission_wait_s: float = Field(default=DEFAULT_ADMISSION_WAIT_S, ge=0)
    # env CORTEX_SUBAGENTS_MAX_TOKENS is how far any one of a delegated run's completions may
    # decode, and CORTEX_SUBAGENTS_RUN_TIMEOUT_S is the deadline on the whole run, tool dispatches
    # included (ADR-0005 total-cap addendum). Together they are what a stall ceiling cannot be: a
    # subagent in a repetition loop is never silent, so before these it held its admission and its
    # entry's lease for as long as it kept talking. Neither has an off switch, the whole of this
    # bound being that a delegated run cannot be unbounded; a deployment retunes rather than
    # disables. The defaults are measured on the shipped CPU entry (cortex_core.subagents).
    max_tokens: int = Field(default=DEFAULT_SUBAGENT_MAX_TOKENS, ge=1)
    run_timeout_s: float = Field(default=DEFAULT_SUBAGENT_RUN_TIMEOUT_S, gt=0)
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
        it belongs here beside the others: the deployment cannot start describing a subagent
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

    @model_validator(mode="after")
    def _the_run_deadline_must_outlast_the_stall_ceiling(self) -> "SubagentsConfig":
        """Refuse at boot a pair of bounds whose precedence would be the wrong way round.

        Both can fire on one stream, and they say different things: the stall ceiling reports the
        gap between chunks, which is a wedged server, and the run deadline reports the whole, which
        is a model that will not stop. Only the first is worth re-running on another target, so a
        deadline at or under the ceiling would convert every wedge into a truncation and quietly
        delete the CPU re-run this repo schedules for exactly that failure. The ceiling stays
        reachable only while the deadline outlasts it, which is a relation between two of this
        deployment's own numbers and so belongs here beside the other wiring errors.
        """
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
        """Refuse at boot a deadline no queued peer would still be waiting through.

        The pair bounds the two halves of one room: the deadline is how long a run may hold its
        admission, the wait how long the next spawn queues for that admission to come back. At or
        above the wait, a peer gives up while the run in front of it is still inside the time this
        deployment granted it, so a working pool reads as one that refuses spawns under load, under
        a refusal naming the queue rather than the deadline that filled it. Strictly under, the
        neighbours' rule: equality is the peer giving up at the instant the room is released.

        **A zero wait passes**, and is the one number here that must: zero means never queue at
        all, so nothing waits on a running spawn and there is no relation to keep.

        **What it does not promise**, in the shape ``check_tool_call_deadline`` states its own: it
        compares one attempt's deadline, and a task can hold its admission for two. ``_placed``
        re-runs a GPU-placed inference failure on the CPU inside the same admission under a
        deadline armed fresh, so the worst-case hold is twice this number along that one path. The
        shipped pair does not clear the doubled relation and no comparison here can make it, both
        defaults being measured; what is refused is the misordering an operator types.
        """
        if self.admission_wait_s > 0 and self.run_timeout_s >= self.admission_wait_s:
            msg = (
                f"CORTEX_SUBAGENTS_RUN_TIMEOUT_S ({self.run_timeout_s}) must be less than "
                f"CORTEX_SUBAGENTS_ADMISSION_WAIT_S ({self.admission_wait_s}); a run allowed to "
                "hold its admission for at least as long as a peer will queue for that admission "
                "makes a working pool read as one that refuses spawns under load, and the "
                "refusal names the queue rather than the deadline that filled it. Lower the run "
                "deadline, or raise the admission wait above it (docs/runbooks/subagents-cpu.md)"
            )
            raise ValueError(msg)
        return self

    @property
    def attempt_bounds(self) -> AttemptBounds:
        """How far one delegated attempt may go, as the core's value (ADR-0005 total-cap addendum).

        A property rather than a field so the two knobs stay independently settable env vars while
        everything below the composition root receives the one value object they mean together.
        """
        return AttemptBounds(max_tokens=self.max_tokens, timeout_s=self.run_timeout_s)

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
