"""Structured provenance: *where* a turn's untrusted content came from (ADR-0027 addendum)."""

import unicodedata
from dataclasses import dataclass
from enum import Enum

# A source is a short label (an address, a locator, a tool name), never a document: one line, hard
# capped, so attacker-chosen text cannot grow a turn's provenance into a channel for smuggling
# prose onto a card or into a store. The overflow marker matches `sessions._one_line`.
MAX_SOURCE_CHARS = 96

# How many distinct sources one turn keeps (`TaintLedger`). A turn reads a handful of things; the
# cap is what stops a flood of results (or, later, a mail search's every sender) from accumulating
# without bound. First come first kept, so the earliest real source survives a later flood.
MAX_TURN_SOURCES = 8

_DROPPED_MARKUP = str.maketrans({"<": None, ">": None})


class SourceKind(Enum):
    """What kind of source a ``Provenance`` names, and (via ``attested``) whose word it is."""

    TOOL = "tool"
    MEMORY = "memory"
    SENDER = "sender"
    URI = "uri"

    @property
    def attested(self) -> bool:
        """Whether the brain authored this kind's value (``True``) or the content claimed it."""
        return self in _ATTESTED_KINDS


# Kinds whose value the brain authored. Held next to the enum rather than as a member attribute so
# the enum's values stay the wire-ish strings every other core enum uses.
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
