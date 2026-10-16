"""`python -m cortex_orchestrator` serves the brain's gRPC interface."""

import sys

from cortex_orchestrator.entry import main

if __name__ == "__main__":  # pragma: no cover - module entry guard, reachable only via -m
    sys.exit(main())
