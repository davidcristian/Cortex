"""Which log levels the model host accepts."""

from uvicorn.config import LOG_LEVELS


def known_log_level(name: str) -> str:
    """``name`` in lower case when uvicorn names that level, or an error listing those it does."""
    level = name.lower()
    if level not in LOG_LEVELS:
        msg = f"unknown log level {name!r}; the model host logs at {list(LOG_LEVELS)}"
        raise ValueError(msg)
    return level
