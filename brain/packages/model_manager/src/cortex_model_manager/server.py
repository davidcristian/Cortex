"""``python -m cortex_model_manager``: wire the supervisor from env and serve its control API.

The sidecar's composition root, the ``cortex_email`` precedent: read settings once, build the
adapters, hand the pure-ish supervisor its two seams, and run. Nothing here holds policy.

The probe client is given a **bounded** timeout, unlike the generation clients the brain dials
llama-server with (which deliberately have no read deadline, since a completion may stream for
minutes). A readiness probe that could hang would hold the per-model lock and therefore stall the
swap step waiting on it, so the control plane and the data plane get opposite timeout policies on
purpose.

``main`` also configures the **root** logger, which is not boilerplate here. ``uvicorn.run``
configures uvicorn's own loggers and leaves root untouched, so without this every lifecycle line
this package logs at INFO is dropped and the one WARNING that escapes goes through logging's
last-resort handler: measured in the image, ``docker logs model-host`` carried llama.cpp's own
stderr and not one daemon line naming which tier was started or stopped, while
``docs/runbooks/model-swap.md`` sends an operator to exactly that log. It configures the
**formatter** as well as the level, so each line's own fields reach that log rather than being
attached to a record the stdlib's default format then prints nothing of.
"""

import logging

import httpx
import uvicorn
from starlette.applications import Starlette

from cortex_core import configure_logging
from cortex_model_manager.api import build_app
from cortex_model_manager.children import AsyncioChildProcesses
from cortex_model_manager.config import ModelHostConfig
from cortex_model_manager.device_memory import NvidiaSmiMemory
from cortex_model_manager.probe import HttpHealthProbe
from cortex_model_manager.supervisor import ModelSupervisor

_logger = logging.getLogger(__name__)


def build_supervisor(config: ModelHostConfig) -> tuple[ModelSupervisor, httpx.AsyncClient]:
    """The supervisor and the probe client it reads readiness through, both wired from env.

    Split out of ``build_model_host`` so all three timing knobs are readable off the objects that
    were handed them: nothing else in this process observes them, so a knob dropped here would
    silently change how long an eviction may take by tens of seconds while the runbook's pairing
    rule went on being reasoned about the configured numbers.

    The probe's deadline is handed over **twice on purpose**: once to the client that spends it,
    and once to the supervisor, which spends none of it and is the only object here that can
    state the whole worst case of its own slowest call. That statement is what ``GET /health``
    publishes and what the brain checks its own control deadline against.
    """
    client = httpx.AsyncClient(timeout=httpx.Timeout(config.probe_timeout_s))
    supervisor = ModelSupervisor(
        config.roster(),
        AsyncioChildProcesses(),
        HttpHealthProbe(client),
        stop_grace_s=config.stop_grace_s,
        reap_timeout_s=config.reap_timeout_s,
        probe_timeout_s=config.probe_timeout_s,
    )
    return supervisor, client


def build_model_host(config: ModelHostConfig) -> Starlette:
    """The ASGI app for this deployment's roster, with the probe's client closed on shutdown.

    The device probe is wired unconditionally, because whether this container can see a card is
    the probe's own question to answer and not something env should assert: on a CPU-only stack
    the binary is simply not in the image, and the seam reports no reading.
    """
    supervisor, client = build_supervisor(config)
    _logger.info(
        "model host configured",
        extra={"models": list(supervisor.models), "boot_model": config.cortex_model},
    )
    return build_app(
        supervisor,
        boot_model=config.cortex_model,
        close=client.aclose,
        device=NvidiaSmiMemory(config.nvidia_smi, config.probe_timeout_s),
    )


def main() -> None:
    """Serve the control API until the container stops. Config errors fail here, loudly."""
    config = ModelHostConfig()
    # Handler config belongs only at a process entry, and this is the sidecar's: the lifecycle
    # trail is the whole diagnosis of a swap that went wrong, so a dropped INFO record is a
    # missing answer rather than missing noise. The formatter is what makes the record's own
    # fields (the tier, its pid, its port) reach that trail rather than being written and dropped.
    configure_logging(config.log_level.upper(), style=config.log_format)
    app = build_model_host(config)
    uvicorn.run(app, host=config.bind_host, port=config.bind_port, log_level=config.log_level)
