"""The one place a ``llama-server`` command line is assembled."""

from dataclasses import dataclass, field
from typing import Literal

from cortex_model_manager.spec import ModelSpec

_BIND_ALL = "0.0.0.0"  # noqa: S104 - the child serves the compose network, not the host

# The tool-capable chat template, so a hosted tier can call functions natively.
_JINJA = "--jinja"

# llama.cpp's own micro-batch default. A picture is decoded as one non-causal chunk and the
# engine asserts the micro-batch is at least that large, so a per-image budget above this
# number must raise it too: raising the budget alone aborts llama-server with SIGSEGV.
_LLAMA_DEFAULT_UBATCH = 512

# The speculative type a multi-token-prediction drafter is decoded with on this engine build.
# Measured on the deep pick: the drafter file named without this type loads and drafts nothing.
_DRAFT_MTP = "draft-mtp"

# The types a tier's KV cache may be set to: the two docs/readings/kv-cache-types.md has rows for.
KvCacheType = Literal["f16", "q8_0"]

# The engine's own KV cache type. A tier at this type names no flag.
ENGINE_KV_CACHE_TYPE: KvCacheType = "f16"


@dataclass(frozen=True, slots=True)
class TierArgs:
    """One hosted tier as the deployment declares it: a logical id and llama.cpp's settings."""

    model: str
    model_path: str
    port: int
    ngl: int
    ctx_size: int
    parallel: int
    extra: tuple[str, ...] = field(default=())


def llama_server_argv(binary: str, tier: TierArgs) -> tuple[str, ...]:
    """The argv for one tier's ``llama-server``, in the compose file's flag order."""
    return (
        binary,
        "--model",
        tier.model_path,
        "--host",
        _BIND_ALL,
        "--port",
        str(tier.port),
        "-ngl",
        str(tier.ngl),
        "--ctx-size",
        str(tier.ctx_size),
        "--parallel",
        str(tier.parallel),
        _JINJA,
        *tier.extra,
    )


def server_id(model: str, index: int) -> str:
    """The logical id of one server of a tier: the tier's own id, then ``-2``, ``-3`` and so on."""
    return model if index == 0 else f"{model}-{index + 1}"


def tier_spec(binary: str, tier: TierArgs) -> ModelSpec:
    """The roster entry for one tier: its logical id, its fixed port, and its whole argv."""
    return ModelSpec(model=tier.model, port=tier.port, argv=llama_server_argv(binary, tier))


def image_budget_flags(budget: int) -> tuple[str, ...]:
    """The per-image token budget, with the micro-batch a raised budget forces beside it."""
    if not budget:
        return ()
    return (
        "--image-max-tokens",
        str(budget),
        "--ubatch-size",
        str(max(budget, _LLAMA_DEFAULT_UBATCH)),
    )


def drafter_flags(path: str, length: int, model_path: str) -> tuple[str, ...]:
    """A tier's MTP drafter with its speculative type and draft length, or nothing for none."""
    if not path:
        return ()
    flags = ("--model-draft", path, "--spec-type", _DRAFT_MTP, "--spec-draft-n-max", str(length))
    # A drafter that is the tier's own model file is the layer inside it, which the engine
    # drafts with when no drafter file is named.
    return flags[2:] if path == model_path else flags


def cache_flags(cache_type: KvCacheType, *, drafting: bool) -> tuple[str, ...]:
    """A tier's KV cache type, for its drafter's cache too, or nothing at the engine's own type."""
    if cache_type == ENGINE_KV_CACHE_TYPE:
        return ()
    flags = (
        "--cache-type-k",
        cache_type,
        "--cache-type-v",
        cache_type,
        "--cache-type-k-draft",
        cache_type,
        "--cache-type-v-draft",
        cache_type,
    )
    return flags if drafting else flags[:4]


def draft_and_cache_flags(
    drafter_path: str, length: int, model_path: str, cache_type: KvCacheType
) -> tuple[str, ...]:
    """A tier's drafter flags, then the flags of its KV cache type."""
    return (
        *drafter_flags(drafter_path, length, model_path),
        *cache_flags(cache_type, drafting=bool(drafter_path)),
    )
