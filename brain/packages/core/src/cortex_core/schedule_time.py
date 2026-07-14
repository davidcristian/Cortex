"""The display timezone model-facing schedule datetimes render in (ADR-0025 display addendum).

Split out of ``schedule_verbs.py``, which owned the UTC-only ``utc_str`` its siblings shared:
a timezone is policy, not a formatting detail, so it becomes a value the composition root
constructs and injects rather than a constant compiled into the core. The lookup that turns an
IANA key into a concrete zone reads the system tz database, which is an edge concern, so it
lives in ``cortex_orchestrator``; this module knows only the abstract ``tzinfo`` it is handed.
That keeps the core free of ``zoneinfo`` and every test here deterministic. ``UTC_DISPLAY`` is
the default, so an unconfigured deployment renders exactly what v1 rendered.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, tzinfo

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
        a local wall time *and* the offset that disambiguates it, and can always echo an
        explicit ``at`` back. The hop through UTC is load bearing, not a no-op: ``astimezone``
        returns ``self`` unchanged when the input already carries this very zone, which would
        print a *nonexistent* wall time verbatim (03:30+02:00 inside a spring-forward gap)
        while the same instant read back from the store printed the canonical 04:30+03:00.
        Normalizing to the instant first makes one instant render one way everywhere.
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
