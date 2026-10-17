"""``python -m cortex_model_manager`` runs the model-host supervisor sidecar."""

import sys

from cortex_model_manager.server import main

if __name__ == "__main__":  # pragma: no cover - module entry guard, reachable only via -m
    sys.exit(main())
