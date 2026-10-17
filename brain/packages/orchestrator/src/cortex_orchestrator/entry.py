"""The brain's process entry: serve, or log a refused setting as one line and exit 1."""

import asyncio
import logging
from collections.abc import Callable, Coroutine

from cortex_orchestrator.config_logging import configure_from_env
from cortex_orchestrator.wiring import run_from_env
from cortex_settings import ConfigError

__all__ = ["main"]

_logger = logging.getLogger(__name__)


def main(
    serve: Callable[[], Coroutine[object, object, None]] = run_from_env,
    configure: Callable[[], None] = configure_from_env,
) -> int:
    """Serve the brain until shutdown and return the process exit status."""
    try:
        configure()
        asyncio.run(serve())
    except ConfigError as exc:
        # One rendered line is the whole report; the traceback adds nothing the reason lacks.
        _logger.error("setting refused", extra={"reason": str(exc)})  # noqa: TRY400
        return 1
    return 0
