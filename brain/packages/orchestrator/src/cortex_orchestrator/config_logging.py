"""How the brain renders its own log lines, read once at the process entry."""

import logging
from typing import Annotated

from pydantic import AfterValidator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import DEFAULT_LOG_FORMAT, configure_logging, known_log_format
from cortex_settings import ConfigError, read_settings

__all__ = ["LoggingConfig", "configure_from_env"]


class LoggingConfig(BaseSettings):
    """Env-only settings for the brain's own log rendering."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_LOG_")

    # Only the rendering is configurable. INFO is required rather than cosmetic: the tool
    # audit trail (``cortex.tools.audit``, always on) and the recall trail both write at INFO,
    # so a lower level would empty a durable record with nothing reporting it.
    format: Annotated[str, AfterValidator(known_log_format)] = DEFAULT_LOG_FORMAT


def configure_from_env() -> None:
    """Install the brain's root log handler: INFO, rendered the way the env asked for."""
    try:
        style = read_settings(LoggingConfig).format
    except ConfigError:
        # The refused value is the rendering itself, so the refusal is written in the default.
        configure_logging(logging.INFO)
        raise
    configure_logging(logging.INFO, style=style)
