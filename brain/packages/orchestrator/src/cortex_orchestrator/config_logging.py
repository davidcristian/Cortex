"""How the brain renders its own log lines, read once at the process entry."""

import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import DEFAULT_LOG_FORMAT, configure_logging

__all__ = ["LoggingConfig", "configure_from_env"]


class LoggingConfig(BaseSettings):
    """Env-only settings for the brain's own log rendering."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_LOG_")

    # Only the rendering is configurable. INFO is required rather than cosmetic: the tool
    # audit trail (``cortex.tools.audit``, always on) and the recall trail both write at INFO,
    # so a lower level would empty a durable record with nothing reporting it.
    format: str = DEFAULT_LOG_FORMAT


def configure_from_env() -> None:
    """Install the brain's root log handler: INFO, rendered the way the env asked for."""
    configure_logging(logging.INFO, style=LoggingConfig().format)
