"""Shared PreferenceStore behavior checks. Every implementation must pass all of them.

Driven by the parametrized contract test (in-memory fake + fakeredis-backed Redis adapter).
The two must be observably interchangeable behind the port (ports-before-adapters).
"""

from cortex_core import PreferenceStore


async def check_unset_record_reads_empty(store: PreferenceStore) -> None:
    """A store nobody has written to answers an empty mapping, never an error."""
    assert dict(await store.all()) == {}


async def check_pairs_round_trip(store: PreferenceStore) -> None:
    """Written pairs read back verbatim, and the store keeps them apart by key."""
    await store.set("overlay.theme", "midnight")
    await store.set("overlay.mark", "foam")
    assert dict(await store.all()) == {"overlay.theme": "midnight", "overlay.mark": "foam"}


async def check_last_write_wins(store: PreferenceStore) -> None:
    """Setting the same key again replaces the value: the record is a value, not a log."""
    await store.set("overlay.mark", "sheen")
    await store.set("overlay.mark", "ping")
    assert dict(await store.all()) == {"overlay.mark": "ping"}


async def check_empty_value_clears_the_key(store: PreferenceStore) -> None:
    """An empty value REMOVES the key, so a reader falls back to its own default.

    The distinction that matters: cleared is absent, not present-and-empty. A reader that sees
    the key at all would apply "" as a choice and resolve it to a default it never chose.
    """
    await store.set("overlay.theme", "daylight")
    await store.set("overlay.theme", "")
    assert dict(await store.all()) == {}


async def check_clearing_an_unset_key_is_a_no_op(store: PreferenceStore) -> None:
    """Clearing what was never set is silent, so a reset needs no read first."""
    await store.set("overlay.nothing", "")
    assert dict(await store.all()) == {}


async def check_values_are_opaque(store: PreferenceStore) -> None:
    """The store never parses a value: JSON, spaces and unicode all survive byte for byte.

    This is what keeps a new preference off the seam. If any implementation started
    interpreting values, a future setting richer than a bare name would silently corrupt.
    """
    payload = '{"hue": 210, "label": "café ☕"}'
    await store.set("overlay.future", payload)
    assert dict(await store.all())["overlay.future"] == payload


async def check_snapshot_does_not_alias_the_store(store: PreferenceStore) -> None:
    """Mutating a returned mapping cannot reach back into the store."""
    await store.set("overlay.theme", "midnight")
    snapshot = dict(await store.all())
    snapshot["overlay.theme"] = "tampered"
    assert dict(await store.all()) == {"overlay.theme": "midnight"}


ALL_CHECKS = (
    check_unset_record_reads_empty,
    check_pairs_round_trip,
    check_last_write_wins,
    check_empty_value_clears_the_key,
    check_clearing_an_unset_key_is_a_no_op,
    check_values_are_opaque,
    check_snapshot_does_not_alias_the_store,
)
