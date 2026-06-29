"""`python -m cortex_orchestrator` serves the brain's gRPC seam.

Env: CORTEX_SEAM_HOST/PORT (bind), CORTEX_REDIS_URL (session state),
CORTEX_MODEL_CORTEX (logical cortex model id). Wiring: `wiring.run_from_env`.
"""

import asyncio

from cortex_orchestrator.wiring import run_from_env

if __name__ == "__main__":  # pragma: no cover - module entry guard, reachable only via -m
    asyncio.run(run_from_env())
