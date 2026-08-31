"""The display timezone model-facing schedule datetimes render in (ADR-0025 display addendum).

Split out of ``schedule_verbs.py``, which owned the UTC-only ``utc_str`` its siblings shared:
a timezone is policy, not a formatting detail, so it becomes a value the composition root
constructs and injects rather than a constant compiled into the core. The lookup that turns an
IANA key into a concrete zone reads the system tz database, which is an edge concern, so it
lives in ``cortex_orchestrator``; this module reads only the abstract ``tzinfo`` it is handed.
That keeps the core free of ``zoneinfo`` and every test here deterministic. ``UTC_DISPLAY`` is
the default, so an unconfigured deployment renders exactly what v1 rendered.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, tzinfo
from typing import Protocol

UTC_ZONE_NAME = "UTC"


@dataclass(frozen=True, slots=True)
class DisplayZone:
    """One timezone, plus the label the model reads for it in a tool spec.

    The label is carried rather than derived because a zone's own abbreviation is
    seasonal (``EST``/``EDT``) and ambiguous across regions, while the IANA key the user
    configured (``Europe/Bucharest``) names exactly one zone in every season.
    """

    name: str
    tz: tzinfo

    def render(self, moment: datetime) -> str:
        """The one canonical rendering for specs, creation results, and listing lines.

        The offset rides the string (``isoformat`` on an aware datetime), so the model reads
        a local wall time together with the offset that disambiguates it, and can always echo
        an explicit ``at`` back. The hop through UTC is not a no-op: ``astimezone`` returns
        ``self`` unchanged when the input already carries this very zone, which would print a
        nonexistent wall time verbatim (03:30+02:00 inside a spring-forward gap) while the same
        instant read back from the store printed the canonical 04:30+03:00. Normalizing to the
        instant first makes one instant render one way everywhere.
        """
        return moment.astimezone(UTC).astimezone(self.tz).isoformat(timespec="seconds")

    def resolve(self, naive: datetime) -> datetime:
        """Read a naive wall time as this zone's local time, as a UTC instant (the fold policy).

        Once the model is shown local times it writes local times back, and this zone is by
        construction the user's, so a bare wall time has exactly one defensible reading.
        ``fold=0`` (the datetime default) settles the two irregular cases deterministically:
        an ambiguous time (the hour repeated at a fall-back transition) takes the earlier
        offset, and a nonexistent one (the hour skipped going forward) is read with the
        pre-transition offset, landing just past the gap. The result is normalized to UTC
        because every consumer downstream (the store, the codec, the ticker's grid) treats a
        due time as an instant; handing them a gap-local datetime would preserve a wall time
        that never happens. Callers pass naive datetimes only; an ``at`` that carries its own
        offset never reaches here.
        """
        return naive.replace(tzinfo=self.tz).astimezone(UTC)


UTC_DISPLAY = DisplayZone(name=UTC_ZONE_NAME, tz=UTC)
"""The v1 contract as a value: what every deployment renders until ``CORTEX_SCHEDULE_TZ`` says
otherwise."""


class ZoneResolver(Protocol):
    """Turn an IANA key into a ``DisplayZone``, or ``None`` when the key names no known zone.

    A per-rule timezone (ADR-0025 per-rule addendum) is an open set of zones, so unlike the
    single deployment zone it cannot be resolved once at boot: a name reaches the system only as
    model input or as a stored record, and each is where a name becomes a zone. The lookup reads
    the system tz database (the impure edge step the core never takes), so the core depends on
    this abstract resolver and the composition root injects the ``zoneinfo``-backed one.

    ``resolve(name)`` answers the zone ``name`` designates, or ``None`` for no known zone: a
    caller turns ``None`` into a model correction, never an exception, so a bad key costs a round
    trip and not a crash. One-line ``...`` body, the ``ports.py`` convention (contract, no
    behavior).
    """

    def resolve(self, name: str) -> DisplayZone | None: ...


class _UtcOnlyResolver:
    """The core default: it resolves only ``UTC``, since every other key reads the tz database.

    A deployment that offers per-rule zones injects the real resolver; an unconfigured one (and
    every pure-core test) resolves ``UTC`` to the stdlib constant and rejects the rest, so a rule
    can still name the one zone the core carries without a tz-database lookup.
    """

    def resolve(self, name: str) -> DisplayZone | None:
        return UTC_DISPLAY if name == UTC_ZONE_NAME else None


UTC_ONLY_RESOLVER: ZoneResolver = _UtcOnlyResolver()
"""The default ``ZoneResolver``, which resolves UTC and nothing else.

The core has no tz database, so it can answer no other key. The real ``zoneinfo``-backed
resolver is injected at the composition root."""


@dataclass(frozen=True, slots=True)
class ZoneContext:
    """The deployment display zone plus the resolver a per-rule ``in_zone`` is validated against.

    Bundled so a schedule tool that both renders times and resolves a per-rule zone takes one
    collaborator rather than two, staying under the constructor injection ceiling (ADR-0025 per-rule
    addendum, the ``TickerSettings`` bundle's reasoning). ``default`` is the zone a zone-less
    schedule renders in; ``resolver`` turns an ``in_zone`` key into its own zone or a correction.
    """

    default: DisplayZone = UTC_DISPLAY
    resolver: ZoneResolver = UTC_ONLY_RESOLVER


UTC_ZONE_CONTEXT = ZoneContext()
"""The default zone context: UTC render, UTC-only resolver (the unconfigured deployment)."""
