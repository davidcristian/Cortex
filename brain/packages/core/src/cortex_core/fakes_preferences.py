"""In-memory ``PreferenceStore`` fake: the contract twin of the Redis adapter (``cortex_session``).

Its own module rather than a line in ``fakes.py``, following the ``fakes_session`` split. Like the
other in-memory fakes it does not survive a process restart, which is what the real adapter exists
to fix; this twin only has to be observably interchangeable with it behind the port.
"""

from collections.abc import Mapping

from cortex_core.errors import PreferenceStoreError


class InMemoryPreferenceStore:
    """PreferenceStore held in a dict, for tests and single-process experiments only.

    ``fail_with`` arms the next call to raise, so callers can prove their error paths against the
    same typed error the real adapter raises without reaching for a mock.
    """

    def __init__(self, *, initial: Mapping[str, str] | None = None) -> None:
        self._values: dict[str, str] = dict(initial or {})
        self.fail_with: str | None = None

    def _check(self) -> None:
        if self.fail_with is not None:
            raise PreferenceStoreError(self.fail_with)

    async def all(self) -> Mapping[str, str]:
        """Every set pair, as a snapshot the caller cannot mutate through."""
        self._check()
        return dict(self._values)

    async def set(self, key: str, value: str) -> None:
        """Write one pair; an empty value clears the key, as the port specifies."""
        self._check()
        if value == "":
            self._values.pop(key, None)
            return
        self._values[key] = value
