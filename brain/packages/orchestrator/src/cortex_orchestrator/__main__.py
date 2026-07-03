"""`python -m cortex_orchestrator` serves the brain's gRPC seam.

Env: CORTEX_SEAM_HOST/PORT (bind), CORTEX_REDIS_URL (session state),
CORTEX_MODEL_CORTEX (logical cortex model id). Wiring: `wiring.run_from_env`.
"""

import asyncio
import logging

from cortex_orchestrator.wiring import run_from_env

if __name__ == "__main__":  # pragma: no cover - module entry guard, reachable only via -m
    # Handler config belongs only at the process entry (libraries never configure logging).
    # INFO is required, not cosmetic: the tool audit trail (`cortex.tools.audit`,
    # ADR-0009/ADR-0013) logs at INFO, and without a configured handler Python's last-resort
    # handler drops INFO records. The durable trail would be silently empty in the container.
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_from_env())
