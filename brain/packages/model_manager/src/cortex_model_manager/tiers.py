"""The one place a ``llama-server`` command line is assembled."""

from dataclasses import dataclass, field

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


def drafter_flags(path: str) -> tuple[str, ...]:
    """A tier's MTP drafter and the speculative type it drafts with, or nothing for no drafter."""
    if not path:
        return ()
    return ("--model-draft", path, "--spec-type", _DRAFT_MTP)
