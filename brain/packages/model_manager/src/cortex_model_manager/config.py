"""The model-host daemon's env surface: which tiers it may run, and how it runs them."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import DEFAULT_CORTEX_MODEL, DEFAULT_LOG_FORMAT
from cortex_model_manager.spec import ModelSpec, build_roster
from cortex_model_manager.supervisor import (
    DEFAULT_PROBE_TIMEOUT_S,
    DEFAULT_REAP_TIMEOUT_S,
    DEFAULT_STOP_GRACE_S,
)
from cortex_model_manager.tiers import TierArgs, drafter_flags, image_budget_flags, tier_spec

DEFAULT_CORTEX_FILE = "google/gemma-4-12B-it-qat-q4_0-gguf/gemma-4-12b-it-qat-q4_0.gguf"

DEFAULT_BRAIN_MODEL = "brain"

# The GPU-placed subagent tier. It is what CORTEX_SWAP_EVICT_MODELS names, since while the deep
# model is resident it is alone on the GPU.
DEFAULT_SUBAGENT_GPU_MODEL = "subagent-gpu"

# The tier defaults the compose stack repeats as its own substitution defaults, named here so
# `scripts/crosscheck.py` can compare the two. The two 8192s are separate constants because the
# deep and subagent contexts are sized on different arguments and may move apart.
DEFAULT_NGL = 99
DEFAULT_CORTEX_CTX_SIZE = 16384
DEFAULT_BRAIN_CTX_SIZE = 8192
DEFAULT_SUBAGENT_CTX_SIZE = 8192
DEFAULT_SUBAGENT_PARALLEL = 2
DEFAULT_IMAGE_MAX_TOKENS = 1024
DEFAULT_NVIDIA_SMI = "nvidia-smi"

# Both model families the subagent tier can run are reasoning models, and unbounded thinking is
# minutes per call, so it takes both the template kwarg and the budget flag: the kwarg alone was
# measured to leave the trace running on a request with a `response_format`.
_NO_REASONING_BUDGET = "0"

# `--cache-ram` sizes the prompt cache llama.cpp keeps in host RAM, 8192 MiB per server by
# default. The weights are mmapped inside the same cgroup this container caps at 24 GiB, so a
# growing cache reclaims the mapped GGUF the server reads on every token.
_NO_PROMPT_CACHE = "0"
_CORTEX_PROMPT_CACHE = "8192"

_SUBAGENT_TAIL = (
    "--chat-template-kwargs",
    '{"enable_thinking": false}',
    "--reasoning-budget",
    _NO_REASONING_BUDGET,
    "--cache-ram",
    _NO_PROMPT_CACHE,
)

# llama.cpp's own value for an unbounded reasoning trace, used here as unset because it is also
# the engine default: a deployment that names no budget emits no flag. Zero is a real setting,
# meaning the trace ends at once, which is why the sentinel cannot be a falsy value.
_UNRESTRICTED_REASONING = -1


class ModelHostConfig(BaseSettings):
    """Env-only settings for the supervisor sidecar."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_MODELHOST_", validate_by_name=True)

    bind_host: str = "0.0.0.0"  # noqa: S104 - the compose network reaches it by service name
    bind_port: int = Field(default=9300, gt=0, le=65535)
    llama_bin: str = "/app/llama-server"
    models_root: str = "/models"
    stop_grace_s: float = Field(default=DEFAULT_STOP_GRACE_S, ge=0)
    reap_timeout_s: float = Field(default=DEFAULT_REAP_TIMEOUT_S, ge=0)
    probe_timeout_s: float = Field(default=DEFAULT_PROBE_TIMEOUT_S, gt=0)
    # What answers "how much of the card is free" on GET /health. The NVIDIA container toolkit
    # injects this binary beside the driver, so the default is right wherever a GPU is reserved
    # and absent, which reads as no card, wherever one is not.
    nvidia_smi: str = DEFAULT_NVIDIA_SMI
    log_level: str = "info"
    log_format: str = DEFAULT_LOG_FORMAT

    cortex_model: str = Field(default=DEFAULT_CORTEX_MODEL, validation_alias="CORTEX_MODEL_CORTEX")
    cortex_file: str = Field(
        default=DEFAULT_CORTEX_FILE, validation_alias="CORTEX_MODEL_FILE_CORTEX"
    )
    # The multimodal projector that lets the cortex tier read images. Empty starts the tier
    # text-only, which is how a deployment without vision and CI both run it; naming a file adds
    # llama.cpp's --mmproj pair and the brain discovers the capability from the server's /props.
    cortex_mmproj_file: str = Field(default="", validation_alias="CORTEX_MODEL_FILE_CORTEX_MMPROJ")
    # How many tokens one picture may occupy, and so how much of a 4K screen survives the
    # downscale. Zero hands the budget to the model, which reads 6 to 8 of 47 ground-truth
    # strings off a 4K desktop; 1024 is the default because it reads 36 to 38 of the same 47.
    cortex_image_max_tokens: int = Field(
        default=DEFAULT_IMAGE_MAX_TOKENS, ge=0, validation_alias="CORTEX_IMAGE_MAX_TOKENS"
    )
    cortex_ngl: int = Field(default=DEFAULT_NGL, validation_alias="CORTEX_NGL")
    cortex_ctx_size: int = Field(
        default=DEFAULT_CORTEX_CTX_SIZE, gt=0, validation_alias="CORTEX_CTX_SIZE"
    )
    cortex_port: int = Field(default=8080, gt=0, le=65535)
    # How many tokens this tier may spend on its reasoning trace before the engine ends the
    # trace and starts the reply. Measured on the cortex pick: unrestricted spends 2323 to 2996
    # characters and 10.1 to 12.6 s, 512 spends 2003 and 8.4 s, 128 spends 483 to 536 and 1.7 s.
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
    brain_reasoning_budget: int = Field(
        default=_UNRESTRICTED_REASONING,
        ge=_UNRESTRICTED_REASONING,
        validation_alias="CORTEX_REASONING_BUDGET_BRAIN",
    )
    # The deep tier's multi-token-prediction drafter. Empty starts the tier as before; naming a
    # file decoded at 1.86 to 1.89 times the plain rate for about 1000 MiB more, which this
    # stack's card cannot hold beside the GPU subagent tier.
    brain_draft_file: str = Field(default="", validation_alias="CORTEX_MODEL_FILE_BRAIN_DRAFT")

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
                extra=(
                    "--cache-ram",
                    _CORTEX_PROMPT_CACHE,
                    *self._vision(),
                    *self._reasoning(self.cortex_reasoning_budget),
                ),
            ),
            TierArgs(
                model=self.brain_model,
                model_path=self._path(self.brain_file),
                port=self.brain_port,
                ngl=self.brain_ngl,
                ctx_size=self.brain_ctx_size,
                parallel=1,
                extra=(
                    "--cache-ram",
                    _NO_PROMPT_CACHE,
                    *self._reasoning(self.brain_reasoning_budget),
                    *drafter_flags(self._path(self.brain_draft_file)),
                ),
            ),
            TierArgs(
                model=self.subagent_gpu_model,
                model_path=self._path(self.subagent_gpu_file),
                port=self.subagent_gpu_port,
                ngl=self.subagent_gpu_ngl,
                ctx_size=self.subagent_gpu_ctx_size,
                parallel=self.subagent_gpu_parallel,
                extra=_SUBAGENT_TAIL,
            ),
        )
        return tuple(tier for tier in declared if tier.model_path)

    def roster(self) -> dict[str, ModelSpec]:
        """The fixed set of logical ids this daemon will ever run, keyed by id."""
        return build_roster(tier_spec(self.llama_bin, tier) for tier in self.tiers())

    def _vision(self) -> tuple[str, ...]:
        """The cortex tier's vision tail: the projector, and the budget it is read at."""
        path = self._path(self.cortex_mmproj_file)
        if not path:
            return ()
        return ("--mmproj", path, *image_budget_flags(self.cortex_image_max_tokens))

    def _reasoning(self, budget: int) -> tuple[str, ...]:
        """A tier's reasoning budget as llama.cpp's own flag, or nothing when unrestricted."""
        if budget == _UNRESTRICTED_REASONING:
            return ()
        return ("--reasoning-budget", str(budget))

    def _path(self, file: str) -> str:
        """An artifact path under the read-only mount, or empty for a tier with no file."""
        return f"{self.models_root.rstrip('/')}/{file}" if file else ""
