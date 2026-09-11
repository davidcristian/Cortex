"""What a reply delivered, judged per subtask shape (ADR-0028 judged-delivery addendum)."""

import re
from collections.abc import Callable
from difflib import SequenceMatcher
from typing import NamedTuple

# The fraction of a body's distinct numeric literals a reply carries before the recall proxy counts
# it an answer. Half, which is the threshold the ADR-0028 addenda judged by hand.
THRESHOLD = 0.5

# How each arbitration may be read. The first of each is the column the ADR-0028 tables are in.
COMMAS = ("charitable", "thousands", "separator")
REFUSALS = ("strict", "charitable")
NAMINGS = ("strict", "charitable")

# A numeric literal whose digit groups a comma joins, and one that ends at any comma.
JOINED = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
PLAIN = re.compile(r"\d+(?:\.\d+)?")

# The reporting period a body states about itself, in the form all four report bodies state it: a
# unit and the word saying which one. `ending` is the clinic body's, a month carrying no number.
PERIOD = re.compile(
    r"\b(week|month|quarter|fortnight)\s+(ending|one|two|three|four|\d+)\b", re.IGNORECASE
)

# One word of a reply, for the charitable naming reading.
WORD = re.compile(r"[a-z0-9]+")

# How many letters of the unit word the charitable naming reading holds a reply to. Four is the
# whole of the shortest unit (`week`) and the length at which the four units part, so it admits
# `weeks` and `Fortnite` as the unit inflected and misspelled and admits no other unit.
STEM = 4

# Three ways a reply names a calendar instance: a month by name, a year of this century or the
# last, and a day of the month written as an ordinal. A month is matched capitalised because `may`
# is also a verb.
MONTH = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b"
)
YEAR = re.compile(r"\b(?:19|20)\d\d\b")
DAY = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\b", re.IGNORECASE)

# The number a body's period word stands for, where the body writes it as a word.
NUMERALS = {"one": "1", "two": "2", "three": "3", "four": "4"}

# The share of their combined letters and digits a reply and its body agree on, as `difflib` counts
# it, at which the reply is the body handed back. Nine tenths is argued from one full sweep in the
# ADR-0028 lapse addendum; it also means a reply a fifth shorter than its body is never a copy.
COPIED = 0.9


class Reading(NamedTuple):
    """Which reading of each arbitration a delivered rate was judged under."""

    comma: str = COMMAS[0]
    refusal: str = REFUSALS[0]
    naming: str = NAMINGS[0]

    def rendered(self) -> str:
        """The one line a report names its columns in."""
        return f"comma {self.comma}, refusal {self.refusal}, naming {self.naming}"


# The reading the ADR-0028 tables' own rows are in, and the one a floor is held under whatever
# columns a reader asked to be shown: a verdict that moved with a flag would be the `--floor` knob
# the control-arm addendum rejected, arriving under another name.
TABLED = Reading()


def reduced(text: str) -> str:
    """``text`` as its letters and digits alone, folded for case."""
    return "".join(character for character in text.casefold() if character.isalnum())


def canonical(number: str) -> str:
    """One numeric literal as the value it names: commas dropped, and leading zeros with them."""
    whole, _, part = number.replace(",", "").partition(".")
    stripped = whole.lstrip("0") or "0"
    return f"{stripped}.{part}" if part else stripped


def literals(text: str, *, joined: bool) -> frozenset[str]:
    """The distinct numbers ``text`` carries, with a comma joining digit groups or ending one."""
    return frozenset(canonical(number) for number in (JOINED if joined else PLAIN).findall(text))


def carries_the_numbers(reply: str, body: str, reading: Reading) -> bool | None:
    """Whether ``reply`` recalls enough of ``body``'s numbers, or ``None`` when it states none.

    The body is read with its digit groups joined, being prose that writes a thousand as `1,000`.
    The reply is read under the comma column, and the charitable one is the better of the two.
    """
    wanted = literals(body, joined=True)
    if not wanted:
        return None
    both = (True, False) if reading.comma == COMMAS[0] else (reading.comma == "thousands",)
    found = max(len(wanted & literals(reply, joined=joined)) for joined in both)
    return found / len(wanted) >= THRESHOLD


def copied(reply: str, body: str) -> bool:
    """Whether ``reply`` is ``body`` handed back, verbatim or nearly, over letters and digits."""
    matcher = SequenceMatcher(None, reduced(reply), reduced(body), autojunk=False)
    return matcher.ratio() >= COPIED


def instances(text: str, unit: str) -> frozenset[str]:
    """The calendar instances ``text`` names, with every numbered period of ``unit`` in it."""
    days = (f"day {canonical(day)}" for day in DAY.findall(text))
    numbered = re.findall(rf"\b{re.escape(unit)}s?\s+(?:of\s+)?(\d+)\b", text, re.IGNORECASE)
    periods = (f"{unit} {canonical(number)}" for number in numbered)
    return frozenset((*MONTH.findall(text), *YEAR.findall(text), *days, *periods))


def invents(reply: str, body: str, unit: str, which: str) -> bool:
    """Whether ``reply`` names an instance ``body`` does not state, its own period's number aside.

    A body's own period number may come back as a day (`the 18th fortnight`), and an instance the
    body states elsewhere may come back as evidence (`week 31`, `August`), so neither is invented.
    """
    own = NUMERALS.get(which, canonical(which))
    stated = instances(body, unit) | {f"day {own}", f"{unit} {own}"}
    return bool(instances(reply, unit) - stated)


def names_the_period(reply: str, body: str, reading: Reading) -> bool | None:
    """Whether ``reply`` names the period ``body`` states and no other, ``None`` if none."""
    stated = PERIOD.search(body)
    if stated is None:
        return None
    unit, which = stated.group(1).casefold(), stated.group(2).casefold()
    if reading.naming == "strict":
        named = reduced(unit + which) in reduced(reply)
    else:
        words = WORD.findall(reply.casefold())
        named = which in words and any(word.startswith(unit[:STEM]) for word in words)
    return named and not invents(reply, body, unit, which)


class Judge(NamedTuple):
    """One subtask shape and the judge declared beside it."""

    shape: str
    reads: Callable[[str, str, Reading], bool | None]
    what: str


# The three shapes this arc sweeps, each with the judge the addenda judged it by. A shape is
# written without its final punctuation because a run is matched to it on its opening.
JUDGES: tuple[Judge, ...] = (
    Judge(
        "Summarize the report below, keeping every detail",
        carries_the_numbers,
        "number recall against the body",
    ),
    Judge(
        "Extract every number from the report below",
        carries_the_numbers,
        "number recall against the body",
    ),
    Judge(
        "What reporting period does the report below cover",
        names_the_period,
        "the body's own reporting period, named back",
    ),
)


def declared(instruction: str) -> Judge | None:
    """The judge declared for the shape ``instruction`` opens with, or ``None`` for any other."""
    opening = reduced(instruction)
    return next((judge for judge in JUDGES if opening.startswith(reduced(judge.shape))), None)


def delivered(
    instruction: str, context: str, output: str, *, ok: bool, reading: Reading
) -> bool | None:
    """Whether one run delivered the answer, or ``None`` when nothing here can judge it."""
    judge = declared(instruction)
    if judge is None:
        return None
    if not ok and reading.refusal == "strict":
        return False
    if copied(output, context):
        return False
    return judge.reads(output, context, reading)
