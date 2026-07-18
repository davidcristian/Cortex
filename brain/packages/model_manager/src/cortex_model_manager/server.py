"""``python -m cortex_model_manager``: wire the supervisor from env and serve its control API.

The sidecar's composition root, the ``cortex_email`` precedent: read settings once, build the
adapters, hand the pure-ish supervisor its two seams, and run. Nothing here holds policy.

The probe client is given a **bounded** timeout, unlike the generation clients the brain dials
llama-server with (which deliberately have no read deadline, since a completion may stream for
minutes). A readiness probe that could hang would hold the per-model lock and therefore stall the
swap step waiting on it, so the control plane and the data plane get opposite timeout policies on
purpose.
"""

import logging

import httpx
import uvicorn
from starlette.applications import Starlette

from cortex_model_manager.api import build_app
from cortex_model_manager.children import AsyncioChildProcesses
from cortex_model_manager.config import ModelHostConfig
from cortex_model_manager.probe import HttpHealthProbe
from cortex_model_manager.supervisor import ModelSupervisor

_logger = logging.getLogger(__name__)


def build_supervisor(config: ModelHostConfig) -> tuple[ModelSupervisor, httpx.AsyncClient]:
    """The supervisor and the probe client it reads readiness through, both wired from env.

    Split out of ``build_model_host`` so all three timing knobs are readable off the objects that
    were handed them: nothing else in this process observes them, so a knob dropped here would
    silently change how long an eviction may take by tens of seconds while the runbook's pairing
    rule went on being reasoned about the configured numbers.
    """
    client = httpx.AsyncClient(timeout=httpx.Timeout(config.probe_timeout_s))
    supervisor = ModelSupervisor(
        config.roster(),
        AsyncioChildProcesses(),
        HttpHealthProbe(client),
        stop_grace_s=config.stop_grace_s,
        reap_timeout_s=config.reap_timeout_s,
    )
    return supervisor, client


def build_model_host(config: ModelHostConfig) -> Starlette:
    """The ASGI app for this deployment's roster, with the probe's client closed on shutdown."""
    supervisor, client = build_supervisor(config)
    _logger.info(
        "model host configured",
        extra={"models": list(supervisor.models), "boot_model": config.cortex_model},
    )
    return build_app(supervisor, boot_model=config.cortex_model, close=client.aclose)


def main() -> None:
    """Serve the control API until the container stops. Config errors fail here, loudly."""
    config = ModelHostConfig()
    app = build_model_host(config)
    uvicorn.run(app, host=config.bind_host, port=config.bind_port, log_level=config.log_level)
