"""Settings reader every entry point shares (docs/modules/brain-settings.md)."""

from cortex_settings.read import ConfigError, read_settings

__all__ = ["ConfigError", "read_settings"]
