"""How the brain renders its own log lines, read once at the process entry.

Its own module rather than two lines inside ``__main__``: the entry guard is the one place in this
package coverage cannot reach, so anything with a decision in it belongs beside it rather than in
it. What is left in ``__main__`` is a single call.

The level is not a knob. INFO is required rather than cosmetic here, because the tool
audit trail (``cortex.tools.audit``, ADR-0009/ADR-0013) and the recall trail both log at INFO, so
a deployment that turned the level down would empty a durable record it is obliged to keep, with
nothing reporting it. The rendering is a knob, because who reads these lines is a property of the
deployment rather than of this repo.
"""

import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import DEFAULT_LOG_FORMAT, configure_logging

__all__ = ["LoggingConfig", "configure_from_env"]


class LoggingConfig(BaseSettings):
    """Env-only settings for the brain's own log rendering."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_LOG_")

    # env CORTEX_LOG_FORMAT picks the rendering. The shipped `plain` appends each record's own
    # fields to the line an operator already reads; `packed` writes the whole record as one JSON
    # object for a deployment that collects rather than reads. A name this build does not carry
    # raises here rather than falling back to a rendering nobody asked for.
    format: str = DEFAULT_LOG_FORMAT


def configure_from_env() -> None:
    """Install the brain's root log handler: INFO, rendered the way the env asked for."""
    configure_logging(logging.INFO, style=LoggingConfig().format)
