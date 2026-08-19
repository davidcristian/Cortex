"""`python -m cortex_orchestrator` serves the brain's gRPC interface."""

import asyncio

from cortex_orchestrator.config_logging import configure_from_env
from cortex_orchestrator.wiring import run_from_env

if __name__ == "__main__":  # pragma: no cover - module entry guard, reachable only via -m
    # Installs the formatter that renders each record's own fields. Without it the stdlib
    # prints the message alone and every ``extra`` this repo attaches is dropped.
    configure_from_env()
    asyncio.run(run_from_env())
