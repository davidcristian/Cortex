"""Read a settings class, turning a refused value into an error naming its variable."""

from pydantic import ValidationError
from pydantic_core import ErrorDetails
from pydantic_settings import BaseSettings, SettingsError

__all__ = ["ConfigError", "read_settings"]


class ConfigError(Exception):
    """A setting is refused, in words naming its variable and never its value."""


def read_settings[T: BaseSettings](cls: type[T]) -> T:
    """Read ``cls`` from the environment, raising ``ConfigError`` for a value it refuses."""
    try:
        return cls()
    except SettingsError as exc:
        field = str(exc).partition('field "')[2].partition('"')[0]
        msg = f"{_variable(cls, field)} is not valid JSON"
        raise ConfigError(msg) from exc
    except ValidationError as exc:
        # ``from None``: a ValidationError's own text includes the input value.
        msg = "; ".join(_describe(cls, error) for error in exc.errors())
        raise ConfigError(msg) from None


def _describe(cls: type[BaseSettings], error: ErrorDetails) -> str:
    reason = error["msg"].removeprefix("Value error, ")
    value = error["input"]
    # Built-in messages state the rule broken; only a validator's own message may quote the input.
    if error["type"] == "value_error" and isinstance(value, str) and value:
        reason = reason.replace(value, "<value>")
    loc = error["loc"]
    return f"{_variable(cls, str(loc[0]))}: {reason}" if loc else reason


def _variable(cls: type[BaseSettings], key: str) -> str:
    field = cls.model_fields.get(key)
    if field is None:
        # Pydantic reports an aliased field by its alias, which is already the variable.
        return key
    if isinstance(field.validation_alias, str):
        return field.validation_alias
    return f"{cls.model_config.get('env_prefix', '')}{key}".upper()
