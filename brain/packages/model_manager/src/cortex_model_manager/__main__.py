"""``python -m cortex_model_manager`` runs the model-host supervisor sidecar.

Env: CORTEX_MODELHOST_BIND_HOST/BIND_PORT/LLAMA_BIN/MODELS_ROOT plus the per-tier artifact,
``-ngl`` and context knobs (see ``config.ModelHostConfig``). Wiring: ``server.main``.
"""

from cortex_model_manager.server import main

if __name__ == "__main__":  # pragma: no cover - module entry guard, reachable only via -m
    main()
