"""`python -m cortex_orchestrator` serves the brain's gRPC seam.

Env: CORTEX_SEAM_HOST/PORT (bind), CORTEX_REDIS_URL (session state),
CORTEX_MODEL_CORTEX (logical cortex model id), CORTEX_LOG_FORMAT (how a line is
rendered). Wiring: `wiring.run_from_env`, logging: `config_logging.configure_from_env`.
"""

import asyncio

from cortex_orchestrator.config_logging import configure_from_env
from cortex_orchestrator.wiring import run_from_env

if __name__ == "__main__":  # pragma: no cover - module entry guard, reachable only via -m
    # Handler config belongs only at the process entry (libraries never configure logging), and
    # what it installs is the formatter that renders each record's own fields: without one the
    # stdlib prints the message alone and every `extra` this repo attaches is written and dropped.
    configure_from_env()
    asyncio.run(run_from_env())
