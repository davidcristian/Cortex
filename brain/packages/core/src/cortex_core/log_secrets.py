"""Which field names mark a secret, and how those values are removed from a log record."""

from collections.abc import Mapping, Sequence
from functools import partial
from typing import cast

REDACTED = "<redacted>"

SECRET_NAMES = (
    "apikey",
    "api_key",
    "authorization",
    "cookie",
    "credential",
    "passwd",
    "password",
    "secret",
    "token",
)


def is_secret_name(key: str) -> bool:
    """Whether a field name marks a secret value."""
    lowered = key.lower()
    return any(marker in lowered for marker in SECRET_NAMES)


def withhold_secrets(value: object) -> object:
    """``value`` with the value under every secret-named string key replaced, at any depth."""
    try:
        return _withheld(value, set())
    except RecursionError:
        return REDACTED


def _withheld(value: object, open_ids: set[int]) -> object:
    """``value`` with its secret-named keys withheld; ``open_ids`` is the containers above it."""
    identity = id(value)
    if identity in open_ids:
        return value
    if isinstance(value, Mapping):
        walk = partial(_withheld_mapping, cast("Mapping[object, object]", value))
    elif isinstance(value, list | tuple):
        walk = partial(_withheld_sequence, cast("Sequence[object]", value))
    else:
        return value
    open_ids.add(identity)
    try:
        return walk(open_ids)
    finally:
        open_ids.discard(identity)


def _withheld_mapping(mapping: Mapping[object, object], open_ids: set[int]) -> object:
    """``mapping``, or a dict copy of it with every secret-named key's value withheld."""
    kept = {
        key: REDACTED if isinstance(key, str) and is_secret_name(key) else _withheld(item, open_ids)
        for key, item in mapping.items()
    }
    if all(kept[key] is item for key, item in mapping.items()):
        return mapping
    return kept


def _withheld_sequence(items: Sequence[object], open_ids: set[int]) -> object:
    """``items``, or a copy of it of the same kind with every nested secret withheld."""
    kept = [_withheld(item, open_ids) for item in items]
    if all(new is old for new, old in zip(kept, items, strict=True)):
        return items
    return tuple(kept) if isinstance(items, tuple) else kept
