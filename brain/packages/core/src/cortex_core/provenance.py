"""Structured provenance: where a turn's untrusted content came from."""

import unicodedata
from dataclasses import dataclass
from enum import Enum

# A source is a short label (an address, a locator, a tool name), never a document, so that
# attacker-chosen text cannot turn a turn's provenance into a way to smuggle prose onto a
# card or into a store.
MAX_SOURCE_CHARS = 96

MAX_TURN_SOURCES = 8

# Angle brackets are dropped rather than escaped: the untrusted fence is written as
# <untrusted-tool-output id=...>, so a value that cannot contain < or > cannot forge a
# marker or any other bracketed structure wherever it is later rendered.
_DROPPED_MARKUP = str.maketrans({"<": None, ">": None})


class SourceKind(Enum):
    """What kind of source a ``Provenance`` names, and who authored its value (``attested``)."""

    TOOL = "tool"
    MEMORY = "memory"
    SENDER = "sender"
    URI = "uri"

    @property
    def attested(self) -> bool:
        """Whether the brain authored this kind's value (``True``) or the content claimed it."""
        return self in _ATTESTED_KINDS


_ATTESTED_KINDS = frozenset({SourceKind.TOOL, SourceKind.MEMORY})


def _inert(raw: str) -> str:
    """Reduce a raw source string to one bounded, inert line."""
    stripped = "".join(ch for ch in raw if ch.isspace() or unicodedata.category(ch)[0] != "C")
    collapsed = " ".join(stripped.split()).translate(_DROPPED_MARKUP)
    if len(collapsed) <= MAX_SOURCE_CHARS:
        return collapsed
    return f"{collapsed[: MAX_SOURCE_CHARS - 1]}…"


@dataclass(frozen=True, slots=True)
class Provenance:
    """One source a turn's untrusted content came from: what kind of source, and which one."""

    kind: SourceKind
    value: str

    def __post_init__(self) -> None:
        inert = _inert(self.value)
        if not inert:
            msg = "Provenance.value must survive sanitizing as a non-empty source"
            raise ValueError(msg)
        object.__setattr__(self, "value", inert)


def as_source(kind: SourceKind, raw: str | None) -> Provenance | None:
    """``raw`` as a ``Provenance`` of ``kind``, or ``None`` when there is nothing to attribute."""
    if raw is None or not _inert(raw):
        return None
    return Provenance(kind=kind, value=raw)


# Derived from `attested` so the two stay in step. An attested kind names a value the brain
# itself wrote, so letting a sidecar declare one would let it forge a trusted-looking label.
_DECLARABLE_KINDS = {kind.value: kind for kind in SourceKind if not kind.attested}


def claimed_source(kind: object, value: object) -> Provenance | None:
    """A sidecar's declared source as a claimed ``Provenance``, or ``None`` when undeclarable."""
    if not isinstance(kind, str) or not isinstance(value, str):
        return None
    declared = _DECLARABLE_KINDS.get(kind)
    if declared is None:
        return None
    return as_source(declared, value)
