"""The one place a ``llama-server`` command line is assembled (ADR-0005, ADR-0030 decision 3)."""

from dataclasses import dataclass, field

from cortex_model_manager.spec import ModelSpec

_BIND_ALL = "0.0.0.0"  # noqa: S104 - the child serves the compose network, not the host

# Tool-capable chat template, so a hosted tier can native-function-call (ADR-0009).
_JINJA = "--jinja"


@dataclass(frozen=True, slots=True)
class TierArgs:
    """One hosted tier as the deployment declares it: a logical id and llama.cpp's knobs."""

    model: str
    model_path: str
    port: int
    ngl: int
    ctx_size: int
    parallel: int
    extra: tuple[str, ...] = field(default=())


def llama_server_argv(binary: str, tier: TierArgs) -> tuple[str, ...]:
    """The argv for one tier's ``llama-server``, in the compose file's flag order.

    The context size is always explicit: llama.cpp's own default (262144) pre-allocates a KV
    cache that blows any VRAM envelope, which is why the compose file always passed one too.
    """
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
