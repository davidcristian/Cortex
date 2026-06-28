"""`python -m cortex_orchestrator` serves the brain's gRPC seam (env: CORTEX_SEAM_*)."""

import asyncio

from cortex_orchestrator.config import SeamServerConfig
from cortex_orchestrator.server import serve

if __name__ == "__main__":  # pragma: no cover - module entry guard, reachable only via -m
    asyncio.run(serve(SeamServerConfig()))
