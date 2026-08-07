"""The model-host daemon's env surface: which tiers it may run, and how it runs them.

Every artifact path, port, ``-ngl`` and context size the deployment wants lives here, in the
sidecar's own environment, and none of it crosses the control API (ADR-0030 decision 3). The names
are the ones the ADR dictates plus the ones the always-on compose service already used, so a
user's existing ``.env`` keeps working: ``CORTEX_MODEL_FILE_CORTEX``, ``CORTEX_NGL`` and
``CORTEX_CTX_SIZE`` for the resident cortex, ``CORTEX_MODEL_FILE_BRAIN`` / ``CORTEX_NGL_BRAIN`` /
``CORTEX_CTX_SIZE_BRAIN`` for the deep model, and the existing subagent knobs for the GPU-placed
subagent tier.

**A tier with no artifact file is not in the roster at all.** The deep model's pick is still open
(ADR-0004) and the GPU-placed subagent is opt-in, so a deployment that has not named a file for
one gets a daemon that answers 404 for it rather than a tier that spawns a doomed process. The
roster it did build is on ``GET /health``, which is where an operator looks first.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import DEFAULT_CORTEX_MODEL
from cortex_model_manager.spec import ModelSpec, build_roster
from cortex_model_manager.supervisor import DEFAULT_REAP_TIMEOUT_S, DEFAULT_STOP_GRACE_S
from cortex_model_manager.tiers import TierArgs, tier_spec

# The cortex pick ADR-0004's addendum settled, identical to the compose default it replaces.
DEFAULT_CORTEX_FILE = "google/gemma-4-12B-it-qat-q4_0-gguf/gemma-4-12b-it-qat-q4_0.gguf"

# The deep tier's logical id, matching the brain's own CORTEX_MODEL_BRAIN default.
DEFAULT_BRAIN_MODEL = "brain"

# The GPU-placed subagent tier's logical id. It is what CORTEX_SWAP_EVICT_MODELS names, since
# while the deep model is resident it is alone on the GPU (ADR-0030 decision 8).
DEFAULT_SUBAGENT_GPU_MODEL = "subagent-gpu"

# Both subagent-tier families are reasoning models and unbounded thinking is minutes per call
# (ADR-0010), so the hosted subagent tier carries the same server-side reasoning-off pair the CPU
# subagent service does.
_REASONING_OFF = ("--chat-template-kwargs", '{"enable_thinking": false}')

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
    probe_timeout_s: float = Field(default=5.0, gt=0)
    # What answers "how much of the card is free" on GET /health. The NVIDIA container toolkit
    # injects this binary alongside the driver, so the default is right wherever a GPU is
    # reserved and absent (which reads as no card) wherever one is not; a deployment whose image
    # puts it elsewhere names the path. It is bounded by probe_timeout_s, the same deadline the
    # readiness probe gets, both being control-plane reads a swap step waits on.
    nvidia_smi: str = "nvidia-smi"
    log_level: str = "info"

    # The three tiers. The ids must match the brain's (CORTEX_MODEL_CORTEX / CORTEX_MODEL_BRAIN /
    # the evict list), so they carry the same aliases rather than this module's prefix.
    cortex_model: str = Field(default=DEFAULT_CORTEX_MODEL, validation_alias="CORTEX_MODEL_CORTEX")
    cortex_file: str = Field(
        default=DEFAULT_CORTEX_FILE, validation_alias="CORTEX_MODEL_FILE_CORTEX"
    )
    # The multimodal projector that gives the cortex eyes (ADR-0029). Empty (the default)
    # starts the tier text-only, which is what a deployment without vision wants and what CI
    # runs; naming a file adds llama.cpp's --mmproj pair, and the brain then discovers the
    # capability from the running server's /props rather than from a second flag here.
    cortex_mmproj_file: str = Field(default="", validation_alias="CORTEX_MMPROJ_FILE_CORTEX")
    # How many tokens one picture may occupy, and with it how much of a 4K screen survives the
    # downscale. Zero hands the budget back to the model, which declares 266 tokens on the cortex
    # pick and reads 6 to 8 of 47 ground-truth strings off a 4K desktop, inventing most of the
    # rest. 1024 is the default because the maintainer took the measured pair: with the brain
    # asking for a 2048 px capture (CORTEX_BODY_CAPTURE_MAX_EDGE) it reads 36 to 38 of the same 47
    # for about 400 MiB of VRAM, 0.6 s of time to first token, and 744 context tokens a capture
    # (docs/runbooks/llamacpp-gpu.md). A deployment tighter on either sets it back to 0. Ignored
    # without a projector, since it is a budget for pictures and a text-only tier has none.
    cortex_image_max_tokens: int = Field(
        default=1024, ge=0, validation_alias="CORTEX_IMAGE_MAX_TOKENS"
    )
    cortex_ngl: int = Field(default=99, validation_alias="CORTEX_NGL")
    cortex_ctx_size: int = Field(default=16384, gt=0, validation_alias="CORTEX_CTX_SIZE")
    cortex_port: int = Field(default=8080, gt=0, le=65535)

    brain_model: str = Field(default=DEFAULT_BRAIN_MODEL, validation_alias="CORTEX_MODEL_BRAIN")
    brain_file: str = Field(default="", validation_alias="CORTEX_MODEL_FILE_BRAIN")
    brain_ngl: int = Field(default=99, validation_alias="CORTEX_NGL_BRAIN")
    brain_ctx_size: int = Field(default=8192, gt=0, validation_alias="CORTEX_CTX_SIZE_BRAIN")
    brain_port: int = Field(default=8081, gt=0, le=65535)

    subagent_gpu_model: str = Field(
        default=DEFAULT_SUBAGENT_GPU_MODEL, validation_alias="CORTEX_MODEL_SUBAGENT_GPU"
    )
    subagent_gpu_file: str = Field(default="", validation_alias="CORTEX_MODEL_FILE_SUBAGENT_GPU")
    subagent_gpu_ngl: int = Field(default=99, validation_alias="CORTEX_NGL_SUBAGENT_GPU")
    subagent_gpu_ctx_size: int = Field(
        default=8192, gt=0, validation_alias="CORTEX_SUBAGENT_CTX_SIZE"
    )
    subagent_gpu_parallel: int = Field(
        default=2, gt=0, validation_alias="CORTEX_SUBAGENTS_PARALLEL"
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
                extra=self._vision(),
            ),
            TierArgs(
                model=self.brain_model,
                model_path=self._path(self.brain_file),
                port=self.brain_port,
                ngl=self.brain_ngl,
                ctx_size=self.brain_ctx_size,
                parallel=1,
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

    def _image_budget(self) -> tuple[str, ...]:
        """The per-image token budget, with the micro-batch a raised budget forces beside it.

        Zero emits nothing at all, so turning the default off restores an argv the engine's own
        defaults decide, rather than one that names them back at it.
        """
        budget = self.cortex_image_max_tokens
        if not budget:
            return ()
        ubatch = max(budget, _LLAMA_DEFAULT_UBATCH)
        return ("--image-max-tokens", str(budget), "--ubatch-size", str(ubatch))

    def _path(self, file: str) -> str:
        """An artifact path under the read-only mount, or empty for a tier with no file."""
        return f"{self.models_root.rstrip('/')}/{file}" if file else ""
