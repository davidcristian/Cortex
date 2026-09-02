"""The model-host daemon's env surface: which tiers it may run, and how it runs them.

Every artifact path, port, ``-ngl`` and context size the deployment wants lives here, in the
sidecar's own environment, and none of it crosses the control API (ADR-0030 decision 3). The names
are the ones the ADR dictates plus the ones the always-on compose service already used, so a
user's existing ``.env`` keeps working: ``CORTEX_MODEL_FILE_CORTEX``, ``CORTEX_NGL`` and
``CORTEX_CTX_SIZE`` for the resident cortex, ``CORTEX_MODEL_FILE_BRAIN`` / ``CORTEX_NGL_BRAIN`` /
``CORTEX_CTX_SIZE_BRAIN`` for the deep model, and the existing subagent knobs for the GPU-placed
subagent tier.

A tier with no artifact file is left out of the roster. The deep model's pick is still open
(ADR-0004) and the GPU-placed subagent is opt-in, so a deployment that has not named a file for
one gets a daemon that answers 404 for it rather than a tier that spawns a process with no model
to load. The roster that was built is on ``GET /health``, which is where an operator looks first.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import DEFAULT_CORTEX_MODEL, DEFAULT_LOG_FORMAT
from cortex_model_manager.spec import ModelSpec, build_roster
from cortex_model_manager.supervisor import (
    DEFAULT_PROBE_TIMEOUT_S,
    DEFAULT_REAP_TIMEOUT_S,
    DEFAULT_STOP_GRACE_S,
)
from cortex_model_manager.tiers import TierArgs, tier_spec

# The cortex pick ADR-0004's addendum settled, identical to the compose default it replaces.
DEFAULT_CORTEX_FILE = "google/gemma-4-12B-it-qat-q4_0-gguf/gemma-4-12b-it-qat-q4_0.gguf"

# The deep tier's logical id, matching the brain's own CORTEX_MODEL_BRAIN default.
DEFAULT_BRAIN_MODEL = "brain"

# The GPU-placed subagent tier's logical id. It is what CORTEX_SWAP_EVICT_MODELS names, since
# while the deep model is resident it is alone on the GPU (ADR-0030 decision 8).
DEFAULT_SUBAGENT_GPU_MODEL = "subagent-gpu"

# The tier defaults the compose stack spells again as its own substitution defaults, named here
# rather than inline in the ``Field(...)`` calls below so `scripts/crosscheck.py` can read them:
# a number a settings field hides is a number the scan cannot compare, and each of these is
# shipped twice. The two 8192s are separate constants on purpose. The deep tier's context and the
# subagent tier's are sized on different arguments and merely happen to be equal today, so one
# name for both would tie two knobs that are free to move apart.
DEFAULT_NGL = 99
DEFAULT_CORTEX_CTX_SIZE = 16384
DEFAULT_BRAIN_CTX_SIZE = 8192
DEFAULT_SUBAGENT_CTX_SIZE = 8192
DEFAULT_SUBAGENT_PARALLEL = 2
DEFAULT_IMAGE_MAX_TOKENS = 1024
DEFAULT_NVIDIA_SMI = "nvidia-smi"

# Both model families the subagent tier can run are reasoning models and unbounded thinking is
# minutes per call (ADR-0010), so the hosted subagent tier carries the same server-side
# reasoning-off pair the CPU subagent service does. It takes both flags (ADR-0005 thinking-lever
# addendum): the template kwarg alone was measured to leave the trace running on a request
# carrying a `response_format`, which is every reply a tool-less subagent decodes into the fixed
# envelope, and the budget is the flag that reaches that shape. The kwarg is still needed, being
# what the template itself reads.
#
# The budget's value is declared here rather than written inside the tuple so
# `scripts/crosscheck.py` can read it: the two compose subagent servers spell this same pair, and a
# number the scan cannot find a declaration for is a number it cannot compare, the same reason
# this module's tier defaults are declared rather than inlined (ADR-0029 cross-language-constant
# addendum).
_NO_REASONING_BUDGET = "0"

_REASONING_OFF = (
    "--chat-template-kwargs",
    '{"enable_thinking": false}',
    "--reasoning-budget",
    _NO_REASONING_BUDGET,
)

# llama.cpp's own value for an unbounded reasoning trace, used here as "unset" because it is also
# the engine's default: a deployment that names no budget emits no flag, so its tier comes up with
# the argv it always did. Zero is a real setting here (the trace ends immediately) rather than an
# absent one, which is why the sentinel cannot be the falsy value the image budget uses.
_UNRESTRICTED_REASONING = -1

# llama.cpp's own micro-batch default. A picture is decoded as one non-causal chunk, and the
# engine asserts the micro-batch is at least as large as that chunk, so a per-image token budget
# above this number must carry the micro-batch up with it. Measured rather than inferred: raising
# the budget alone aborts llama-server with SIGSEGV on the first oversized picture (a GGML_ASSERT
# in llama-context, not an error reply), which takes vision down for the whole session. That is
# why the two ride one knob here instead of two.
_LLAMA_DEFAULT_UBATCH = 512


class ModelHostConfig(BaseSettings):
    """Env-only settings for the supervisor sidecar. Read once, at ``main``.

    The control plane binds ``CORTEX_MODELHOST_BIND_HOST``/``_BIND_PORT`` (the container
    interface, so the brain can reach it by service name). ``CORTEX_MODELHOST_LLAMA_BIN`` is the
    server binary in this image and ``CORTEX_MODELHOST_MODELS_ROOT`` the read-only mount point
    every artifact path is resolved under, both deliberately distinct from the host-side
    ``CORTEX_MODELS_DIR`` that names the bind source.
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_MODELHOST_", validate_by_name=True)

    bind_host: str = "0.0.0.0"  # noqa: S104 - the compose network reaches it by service name
    bind_port: int = Field(default=9300, gt=0, le=65535)
    llama_bin: str = "/app/llama-server"
    models_root: str = "/models"
    stop_grace_s: float = Field(default=DEFAULT_STOP_GRACE_S, ge=0)
    reap_timeout_s: float = Field(default=DEFAULT_REAP_TIMEOUT_S, ge=0)
    probe_timeout_s: float = Field(default=DEFAULT_PROBE_TIMEOUT_S, gt=0)
    # What answers "how much of the card is free" on GET /health. The NVIDIA container toolkit
    # injects this binary alongside the driver, so the default is right wherever a GPU is
    # reserved and absent (which reads as no card) wherever one is not; a deployment whose image
    # puts it elsewhere names the path. It is bounded by probe_timeout_s, the same deadline the
    # readiness probe gets, both being control-plane reads a swap step waits on.
    nvidia_smi: str = DEFAULT_NVIDIA_SMI
    log_level: str = "info"
    # How a line is rendered, the sidecar's own half of the brain's CORTEX_LOG_FORMAT. Under this
    # prefix because it sits beside the level it pairs with and because this container's env is
    # its own: the two processes are configured separately and may be read by different people.
    log_format: str = DEFAULT_LOG_FORMAT

    # The three tiers. The ids must match the brain's (CORTEX_MODEL_CORTEX / CORTEX_MODEL_BRAIN /
    # the evict list), so they carry the same aliases rather than this module's prefix.
    cortex_model: str = Field(default=DEFAULT_CORTEX_MODEL, validation_alias="CORTEX_MODEL_CORTEX")
    cortex_file: str = Field(
        default=DEFAULT_CORTEX_FILE, validation_alias="CORTEX_MODEL_FILE_CORTEX"
    )
    # The multimodal projector that lets the cortex tier read images (ADR-0029). Empty (the
    # default) starts the tier text-only, which is how a deployment without vision and CI both
    # run it; naming a file adds llama.cpp's --mmproj pair, and the brain then discovers the
    # capability from the running server's /props rather than from a second flag here.
    # Renamed from CORTEX_MMPROJ_FILE_CORTEX on 2026-08-30 (ADR-0029 projector-naming addendum):
    # a projector is a model file, so it is spelled in the one family every model artifact this
    # tree names is spelled in, with the tier still the word after the prefix.
    # `scripts/artifactnames.py` finds it by the `_path` call in `_vision` below, this being the
    # artifact that reaches an argv through `extra` rather than through a tier's model_path: every
    # artifact path goes through `_path`, and the gate refuses one joined onto `models_root` by
    # hand (ADR-0029 addendum on the artifact domain being the resolver).
    cortex_mmproj_file: str = Field(default="", validation_alias="CORTEX_MODEL_FILE_CORTEX_MMPROJ")
    # How many tokens one picture may occupy, and with it how much of a 4K screen survives the
    # downscale. Zero hands the budget back to the model, which declares 266 tokens on the cortex
    # pick and reads 6 to 8 of 47 ground-truth strings off a 4K desktop, inventing most of the
    # rest. 1024 is the default because the maintainer took the measured pair: with the brain
    # asking for a 2048 px capture (CORTEX_BODY_CAPTURE_MAX_EDGE) it reads 36 to 38 of the same 47
    # for about 400 MiB of VRAM, 0.6 s of time to first token, and 744 context tokens a capture
    # (docs/runbooks/llamacpp-gpu.md). A deployment tighter on either sets it back to 0. Ignored
    # without a projector, since it is a budget for pictures and a text-only tier has none.
    cortex_image_max_tokens: int = Field(
        default=DEFAULT_IMAGE_MAX_TOKENS, ge=0, validation_alias="CORTEX_IMAGE_MAX_TOKENS"
    )
    cortex_ngl: int = Field(default=DEFAULT_NGL, validation_alias="CORTEX_NGL")
    cortex_ctx_size: int = Field(
        default=DEFAULT_CORTEX_CTX_SIZE, gt=0, validation_alias="CORTEX_CTX_SIZE"
    )
    cortex_port: int = Field(default=8080, gt=0, le=65535)
    # How many tokens this tier may spend on its reasoning trace before the engine ends the trace
    # and starts the reply. The brain could already say whether to reason at all
    # (``CORTEX_REPLY_THINKING``, and the bounds the fold, the title and the recall rank send);
    # this says how long a trace that does happen may be. Measured on the cortex pick, one open
    # question per arm: unrestricted spends 2323 to 2996 characters of trace and 10.1 to 12.6 s
    # before the first word, 512 spends 2003 and 8.4 s, 128 spends 483 to 536 and 1.7 to 2.6 s, and
    # 0 spends none and 0.2 s, with the reply itself the same size in every arm. ``-1`` is the
    # default and emits no flag (docs/runbooks/llamacpp-gpu.md).
    cortex_reasoning_budget: int = Field(
        default=_UNRESTRICTED_REASONING,
        ge=_UNRESTRICTED_REASONING,
        validation_alias="CORTEX_REASONING_BUDGET",
    )

    brain_model: str = Field(default=DEFAULT_BRAIN_MODEL, validation_alias="CORTEX_MODEL_BRAIN")
    brain_file: str = Field(default="", validation_alias="CORTEX_MODEL_FILE_BRAIN")
    brain_ngl: int = Field(default=DEFAULT_NGL, validation_alias="CORTEX_NGL_BRAIN")
    brain_ctx_size: int = Field(
        default=DEFAULT_BRAIN_CTX_SIZE, gt=0, validation_alias="CORTEX_CTX_SIZE_BRAIN"
    )
    brain_port: int = Field(default=8081, gt=0, le=65535)
    # The deep tier's own budget, separate because the two tiers are tuned on opposite arguments:
    # the cortex answers while somebody watches, and the deep model was picked for reaching an
    # answer inside its trace at all (ADR-0004), so a deployment that shortens one has no reason
    # to have shortened the other. It takes the same flag and the same ``-1`` default.
    brain_reasoning_budget: int = Field(
        default=_UNRESTRICTED_REASONING,
        ge=_UNRESTRICTED_REASONING,
        validation_alias="CORTEX_REASONING_BUDGET_BRAIN",
    )

    subagent_gpu_model: str = Field(
        default=DEFAULT_SUBAGENT_GPU_MODEL, validation_alias="CORTEX_MODEL_SUBAGENT_GPU"
    )
    subagent_gpu_file: str = Field(default="", validation_alias="CORTEX_MODEL_FILE_SUBAGENT_GPU")
    subagent_gpu_ngl: int = Field(default=DEFAULT_NGL, validation_alias="CORTEX_NGL_SUBAGENT_GPU")
    subagent_gpu_ctx_size: int = Field(
        default=DEFAULT_SUBAGENT_CTX_SIZE, gt=0, validation_alias="CORTEX_SUBAGENT_CTX_SIZE"
    )
    subagent_gpu_parallel: int = Field(
        default=DEFAULT_SUBAGENT_PARALLEL, gt=0, validation_alias="CORTEX_SUBAGENTS_PARALLEL"
    )
    subagent_gpu_port: int = Field(default=8083, gt=0, le=65535)

    def tiers(self) -> tuple[TierArgs, ...]:
        """Every tier the deployment named a file for, in residency order."""
        declared = (
            TierArgs(
                model=self.cortex_model,
                model_path=self._path(self.cortex_file),
                port=self.cortex_port,
                ngl=self.cortex_ngl,
                ctx_size=self.cortex_ctx_size,
                parallel=1,
                extra=(*self._vision(), *self._reasoning(self.cortex_reasoning_budget)),
            ),
            TierArgs(
                model=self.brain_model,
                model_path=self._path(self.brain_file),
                port=self.brain_port,
                ngl=self.brain_ngl,
                ctx_size=self.brain_ctx_size,
                parallel=1,
                extra=self._reasoning(self.brain_reasoning_budget),
            ),
            TierArgs(
                model=self.subagent_gpu_model,
                model_path=self._path(self.subagent_gpu_file),
                port=self.subagent_gpu_port,
                ngl=self.subagent_gpu_ngl,
                ctx_size=self.subagent_gpu_ctx_size,
                parallel=self.subagent_gpu_parallel,
                extra=_REASONING_OFF,
            ),
        )
        return tuple(tier for tier in declared if tier.model_path)

    def roster(self) -> dict[str, ModelSpec]:
        """The fixed set of logical ids this daemon will ever run, keyed by id."""
        return build_roster(tier_spec(self.llama_bin, tier) for tier in self.tiers())

    def _vision(self) -> tuple[str, ...]:
        """The cortex tier's vision tail: the projector, and the budget it is read at.

        Both hang off the projector, because a tier with no projector has no pictures: naming a
        token budget on a text-only deployment would raise the micro-batch, and with it the VRAM,
        for nothing.
        """
        path = self._path(self.cortex_mmproj_file)
        if not path:
            return ()
        return ("--mmproj", path, *self._image_budget())

    def _reasoning(self, budget: int) -> tuple[str, ...]:
        """A tier's reasoning budget, in llama.cpp's own flag, or nothing at all when unrestricted.

        The subagent tier is deliberately not routed through here: it carries a fixed zero in
        ``_REASONING_OFF`` instead, because that tier runs with reasoning off rather than
        shortened, and a deployment raising the cortex's budget must not raise a subagent's with
        it. This bounds the length of a trace that happens; whether one happens is set per request.
        """
        if budget == _UNRESTRICTED_REASONING:
            return ()
        return ("--reasoning-budget", str(budget))

    def _image_budget(self) -> tuple[str, ...]:
        """The per-image token budget, with the micro-batch a raised budget forces beside it.

        Zero emits nothing at all, so turning the default off leaves the engine on its own
        defaults rather than passing those same values back to it as flags.
        """
        budget = self.cortex_image_max_tokens
        if not budget:
            return ()
        ubatch = max(budget, _LLAMA_DEFAULT_UBATCH)
        return ("--image-max-tokens", str(budget), "--ubatch-size", str(ubatch))

    def _path(self, file: str) -> str:
        """An artifact path under the read-only mount, or empty for a tier with no file."""
        return f"{self.models_root.rstrip('/')}/{file}" if file else ""
