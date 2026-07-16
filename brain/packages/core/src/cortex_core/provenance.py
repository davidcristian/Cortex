"""Structured provenance: *where* a turn's untrusted content came from (ADR-0027 addendum).

The taint bit (ADR-0013) says a turn read untrusted content; a ``Provenance`` says which source
it read, so the fact travels with whatever the turn spawns (the ``TurnStamp``, ADR-0027) instead
of being lost the moment the tool result is fenced. Two consumers are designed for and neither is
built here: a confirmation card that names the source it is warning about (ADR-0022), and
per-provenance eviction of memories derived from one source (ADR-0019).

Every value is **inert data, never authority**. A source string can be attacker-chosen (an email
sender, a fetched locator), so it is bounded and sanitized *here*, in the pure core, at the moment
a ``Provenance`` is constructed: no constructor can hold an unsanitized value, so no adapter can
smuggle one in. ``SourceKind.attested`` then tells a consumer whether the value is one the brain
authored (a registry-advertised tool name, a memory id) or one the content claimed for itself, so
a claimed source is rendered as quoted untrusted text rather than as a trusted label. Nothing the
*model* authored is ever a source: a call name or argument the model chose would put its text on a
display channel the reply-side guardrail never inspects, which is the surface ``ToolStep`` already
refuses to open (``tool_loop``).

Pure data and pure functions: no I/O, no ports, stdlib only, so ``tools.py`` can depend on it.
"""

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

# Angle brackets are dropped outright rather than escaped: the untrusted fence is
# `<untrusted-tool-output id=...>` (ADR-0013), so a value that cannot contain `<` or `>` cannot
# forge a marker, an HTML tag, or any other bracketed structure wherever it is later rendered.
# `Alice <alice@example.com>` still reads correctly with them gone.
_DROPPED_MARKUP = str.maketrans({"<": None, ">": None})


class SourceKind(Enum):
    """What kind of source a ``Provenance`` names, and (via ``attested``) whose word it is.

    ``TOOL`` is the advertised tool untrusted content came through and ``MEMORY`` a recalled
    tainted memory's id: both are strings the brain itself authored. ``SENDER`` (an address the
    content says it came from) and ``URI`` (a locator it says it was fetched from) are the
    content's own claim, admitted so the two can be told apart and matched separately: eviction
    by sender must not sweep a URI, and a card showing a claimed sender must badge it as claimed.
    """

    TOOL = "tool"
    MEMORY = "memory"
    SENDER = "sender"
    URI = "uri"

    @property
    def attested(self) -> bool:
        """Whether the brain authored this kind's value (``True``) or the content claimed it.

        The distinction a consumer needs before it renders or trusts a source: an attested value
        is ours (a registry-advertised name, an id we minted) and reads as a label; a claimed one
        is attacker-choosable and reads as a quotation, however inert it has been made.
        """
        return self in _ATTESTED_KINDS


# Kinds whose value the brain authored. Held next to the enum rather than as a member attribute so
# the enum's values stay the wire-ish strings every other core enum uses.
_ATTESTED_KINDS = frozenset({SourceKind.TOOL, SourceKind.MEMORY})


def _inert(raw: str) -> str:
    """Reduce a raw source string to one bounded, inert line.

    Control and format characters (Unicode category ``C``: NUL, the zero-width set, the BOM, the
    directional marks) are dropped, since they render as nothing yet survive every later pass, so
    a value cannot smuggle invisible content past a reader (the `url_identity` pass, for the same
    reason). Whitespace is exempt from that pass and collapsed instead, one run to one space: a
    newline is a control character too, so dropping it outright would silently *join* the words it
    separated, and collapsing is what removes the blank-line structure a multi-line injected
    instruction block needs without inventing a token. Markup brackets then go, and the result is
    capped at exactly ``MAX_SOURCE_CHARS``, marked when it overflowed. Idempotent by construction
    (single spaces, nothing left to strip, and the cap includes its marker), so sanitizing a
    sanitized value is a no-op.
    """
    stripped = "".join(ch for ch in raw if ch.isspace() or unicodedata.category(ch)[0] != "C")
    collapsed = " ".join(stripped.split()).translate(_DROPPED_MARKUP)
    if len(collapsed) <= MAX_SOURCE_CHARS:
        return collapsed
    return f"{collapsed[: MAX_SOURCE_CHARS - 1]}…"


@dataclass(frozen=True, slots=True)
class Provenance:
    """One source a turn's untrusted content came from: what kind of source, and which one.

    ``value`` is sanitized and bounded at construction (``_inert``), so an instance cannot exist
    carrying raw attacker text, and a value that survives sanitizing empty is rejected outright
    (an unattributable source is a producer bug, not a blank label to store or show). Frozen and
    hashable, and matched exactly on ``(kind, value)``: that is what per-provenance eviction
    compares, so no kind is silently case-folded or otherwise rewritten into another's namespace.
    """

    kind: SourceKind
    value: str

    def __post_init__(self) -> None:
        inert = _inert(self.value)
        if not inert:
            msg = "Provenance.value must survive sanitizing as a non-empty source"
            raise ValueError(msg)
        object.__setattr__(self, "value", inert)


def as_source(kind: SourceKind, raw: str | None) -> Provenance | None:
    """``raw`` as a ``Provenance`` of ``kind``, or ``None`` when there is nothing to attribute.

    The tolerant form for capture sites, which routinely hold an optional locator (a call that
    matched no advertised spec has no tool name to state). Absent or wholly sanitized-away input
    yields no provenance rather than an exception: an unattributed source is the same fail-open
    posture ``UNSTAMPED`` takes for a missing session, and losing one attribution must never fail
    a turn. Construct ``Provenance`` directly where a missing value is a bug.
    """
    if raw is None or not _inert(raw):
        return None
    return Provenance(kind=kind, value=raw)


# The kinds a sidecar may *declare* on a result it returns: the claimed ones only, derived from
# ``attested`` so the two stay in step. An attested kind names a value the brain itself authored, so
# letting a sidecar declare one would let it forge a trusted-looking label; a sidecar may only claim
# a source its own content is entitled to claim about itself (a sender it states, a locator it was
# fetched from), which a consumer then renders as a quotation, never a label.
_DECLARABLE_KINDS = {kind.value: kind for kind in SourceKind if not kind.attested}


def claimed_source(kind: object, value: object) -> Provenance | None:
    """A sidecar's declared source as a *claimed* ``Provenance``, or ``None`` when undeclarable.

    The trust half of the sidecar declaration channel (ADR-0027/0009): a tool result may declare
    the sender or locator its content came from, but that declaration is attacker-influenceable (an
    email's ``From`` is a header its sender wrote, and a hostile sidecar could put anything there),
    so it is admitted only under a claimed ``SourceKind`` and its ``value`` is sanitized and bounded
    by ``Provenance`` exactly like every other source. A ``kind`` that is not a declarable kind's
    string, or a non-``str`` / empty ``value``, is dropped to ``None`` rather than raising: an
    unparseable or attested-forging declaration attributes nothing, never fails the turn, and can
    never downgrade taint, since all it could ever do is add one more claimed, inert annotation.
    """
    if not isinstance(kind, str) or not isinstance(value, str):
        return None
    declared = _DECLARABLE_KINDS.get(kind)
    if declared is None:
        return None
    return as_source(declared, value)
