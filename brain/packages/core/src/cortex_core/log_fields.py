"""What a record carries beyond the standard attributes, and how those fields are written down.

Every ``extra=`` this repo attaches rides its ``LogRecord`` as an ordinary attribute,
indistinguishable from the two dozen ``logging`` puts there itself. This module answers the two
pure questions that follow: which attributes are the record's own and which came from a caller,
and what a caller's value looks like once it is printed. ``log_format.py`` is the stdlib adapter
that spends both, and it is the only caller that has to exist.

Redaction lives here rather than at the call sites because a formatter prints fields nobody
enumerated. A future adapter attaching ``extra={"token": ...}`` reaches an operator's terminal
without anyone having reviewed that line, and AGENTS.md bans secrets in logs outright, so the
defence has to sit where the printing happens. It has two halves because the leak has two shapes:

- A field named for a secret is withheld by name, and withheld visibly: an absent key and a
  held-back one are different facts, and a reader who cannot tell them apart will go looking for
  the field that was never attached.
- A credential inside a URL is withheld by shape, over the whole rendered line, because that one
  arrives in the message and in a traceback at least as often as in a field.
  ``redis://:pw@redis:6379`` is what a connection error prints, and the connection URL is how
  both the session store and the mail bridge are configured. It is also withheld per value,
  before the bound below cuts one, and that order is what makes the defence work rather than
  merely tidy: ``_USERINFO`` is anchored on the ``@`` that ends a userinfo, so a cut falling
  between a URL's ``://`` and that ``@`` leaves the whole-line pass nothing to match and prints
  the credential in full.

The name list is a denylist and not an allowlist on purpose. An allowlist would have to be edited
for every new field, which is the same invisible-field defect this module exists to end: a field
nobody had registered would be dropped with nothing said instead of never printed, and a drop
nobody is told about is the harder of the two to notice. A denylist errs the other way, toward
printing a name it does not recognize, and it is deliberately blunt about matching: ``token``
withholds a field called ``max_tokens`` too. Withholding a token count costs a reader one number
they can recover from the message; printing a bearer token costs the deployment its seam.

One name per work identity is written down beside those two lists because it is the same kind of
fact: what a field is, rather than what it holds. A line that says which work it is about
picks from the fixed vocabulary of five the dispatch stamp carries, the conversation, the turn,
the delegated task, the fired schedule item and the call itself, each spelled the way that stamp
and the tool audit already spell it (ADR-0009 one-vocabulary addendum). It is written down because
it was spelled two ways before it was: the recall trail and the rank's fallbacks named a
conversation ``session`` where six other modules named it ``session_id``, and the schedule ticker
named a fired item ``reminder_id`` where the trail named it ``item_id``, so a grep for one name
missed every line carrying the other with nothing to show that it had. Only the tool audit spends
these names as code,
being the one place that writes the whole vocabulary out as a list; every other site names one
identity inside its own ``extra=`` and keeps the literal an operator greps, and
`scripts/logcouplings.py` is what ties those literals, and the runbooks that quote them, back to
the declarations here.

A bound on how much of a value reaches the line sits here for the same reason the redaction does:
the size of a field nobody enumerated is not something its call site was asked about, and the tool
audit already attaches one the model writes (``arguments`` carries a spawn's whole instruction
verbatim). The bound is spent on the rendered text rather than on the value, because the rendered
text is what the line costs: a string of quotes escapes to twice its length and an emoji to six
times its own, so a bound on the input would not bound the output. Both renderings a value can
take are cut on the way out of ``render_value``, so neither branch has a bound of its own to drift
from the other. The bound runs after both defences above and never before either: a secret-named
field has already lost its value to one short constant no cut can reach inside, and the rendering
being cut has already had its credentials withheld.

A cut structure stops parsing, which is the deliberate choice. The alternative, dropping whole
elements and carrying a count the way the recall trail's ``dropped_omitted`` does, needs somewhere
to put the count, and that sink has somewhere because it owns the whole line: the count is a
sibling field beside the list it describes. This function renders a value it does not own, so a
count would have to go inside the caller's own structure, under a key the caller may already use,
and the shape most at risk is a long string, which has no elements to drop at all. So the rendering
is cut where the bound falls and the marker says how many characters went: a truncated line that
no longer parses fails at whatever reads it, where a truncated list that still parses is read as
the whole of it.

A cut rendering is never bare, which is what stops the marker being read as the value's own text.
A value printed whole is left bare, having no whitespace to run it into the pair beside it and no
quote of its own. The marker carries two spaces, so appending it to a bare rendering would write a
field boundary inside a field, and ``endpoint=http://aaa<cut 9 chars> next=1`` reads as a plausible
whole endpoint followed by two stray tokens, which is the unreported failure this module avoids
everywhere else. So a rendering that will be cut is quoted instead, and every cut rendering
therefore ends mid-syntax, its closing quote or bracket among the characters that did not print.
That is what leaves the marker unambiguous: it only ever follows a rendering that stopped, while a
field whose own text contains those characters carries them inside a quote that closes, which is
where a value's text always lives and where this module never writes.
"""

import json
import logging
import re
from collections.abc import Mapping

# What stands in for a value this module will not print. Visible on purpose, per the docstring.
REDACTED = "<redacted>"

# What stands in for the rest of a value the bound below cut, naming how many characters went.
# Sibling of REDACTED in shape, since both are the formatter speaking rather than the record.
CUT = "<cut {chars} chars>"

# The most characters one rendered value may spend on a line. Measured rather than picked, against
# what the stream an operator reads really does (ADR-0038 bounded-value addendum): a container's
# log driver ends a message at 16 KiB, so a rendered line of 16,383 characters plus its newline is
# the longest that stays one entry, and past that ``--tail`` counts the pieces rather than the
# lines and ``docker compose logs -t`` stamps every 16 KiB piece. The stamps land mid line rather
# than each opening one of their own, a piece boundary carrying no newline: re-measured on the
# ``json-file`` driver, a split message reads back as one line of 16,446 bytes with two timestamps
# in it, while ``--tail 1`` returns only the last piece. This bound is that cliff divided by
# eight, and what that buys is room for seven fields at it rather than eight:
# eight come to 16,384 characters, one past the cliff before a single ``key=``, separator, marker
# or word of the message is counted. Measured through the shipped formatter, with the level and
# logger prefix and a marker on every field, seven cut fields make a line of 14,536 characters and
# eight make one of 16,607. Seven is therefore the headroom, and that it is enough is an argument
# rather than a check: nothing here measures the widest line the tree can build, which is a
# separate open question and not this constant's to answer. The bound does clear the widest value
# the tree attaches today, the recall trail's dropped candidates at the shipped pool of twenty, and
# that clearance is arithmetic rather than a sample (ADR-0038 real-trail addendum): twenty entries
# carrying a 36-character uuid4 id come to 1,101 characters of syntax and id plus twenty float
# reprs, and no Python float renders in more than 24 characters, so the field cannot pass 1,581
# however the cosines fall. Read off lines a live stack really wrote, a whole dropped pool renders
# at 1,465 to 1,473 characters over 466 lines and nothing shipped was cut.
VALUE_CHARS = 2048

# The attributes ``logging`` puts on every record itself, plus the two a ``Formatter`` adds while
# it runs. Anything else on a record was attached by a caller and is what a reader came for.
# Written down rather than derived from a sample record: a Python release that adds an attribute
# then fails a test here instead of printing a new stdlib field as if a caller had attached it,
# which is the one way this set can go wrong without anyone touching this repo.
RESERVED_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)

# The one name each of the five work identities is written under, wherever a line names one.
# Five constants rather than a collection because each is a separate answer that a separate set
# of places must agree with, and because a collection reduces to no single value the constant
# scan could tie a far side to. They are the dispatch stamp's own names, which is the choice: the
# stamp and the audit record are where a work identity is a field rather than a sentence, `_id` is
# what tells the five apart from the readings printed beside them, and the seam's own
# `reminder_id` names a message the body is handed rather than the item the brain fired.
#
# Five and not six: the swap path's `handoff` looked like a sixth identity and was not one, a
# handoff id being the escalating turn's id at the only place that mints one (`handoff.py`), so
# those lines name a turn and say so. A line naming a second instance of one identity qualifies
# the name in front and keeps the family word, `active_turn_id` for the turn already holding the
# swap, so the two are told apart on the line and a grep for the family still reaches both.
SESSION_FIELD = "session_id"
TURN_FIELD = "turn_id"
TASK_FIELD = "task_id"
ITEM_FIELD = "item_id"
CALL_FIELD = "call_id"

# Substrings that make a field name too dangerous to print, matched case-insensitively so
# ``apiKey`` and ``API_KEY`` are the same name. Every concrete secret this deployment holds is
# named for what it is: the seam token, the mail bridge's password, a model host's credential.
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

# The userinfo half of a URL: everything between the scheme's ``://`` and an ``@``. A bare email
# address is untouched, having no scheme in front of it, and so is a URL that carries no
# credential, there being no ``@`` to end the match. The match ends on the ``@``, which is why
# nothing may shorten a rendering before this has run over it: cut the ``@`` away and the same
# credential no longer matches anything.
_USERINFO = re.compile(r"(?<=://)[^/\s@]*@")

# A value that can be printed as it stands: one token, no whitespace to run it into the next
# field and no quote of its own to confuse the one this module would otherwise add.
_BARE = re.compile(r'[^\s"]+')


def is_secret_name(key: str) -> bool:
    """Whether a field name is one whose value no log line may carry."""
    lowered = key.lower()
    return any(marker in lowered for marker in SECRET_NAMES)


def redact_urls(text: str) -> str:
    """Return ``text`` with the credential in every URL replaced, wherever in the line it sits."""
    return _USERINFO.sub(f"{REDACTED}@", text)


def record_fields(record: logging.LogRecord) -> dict[str, object]:
    """The fields a caller attached to ``record``, with every secret-named value withheld."""
    return {
        key: REDACTED if is_secret_name(key) else value
        for key, value in record.__dict__.items()
        if key not in RESERVED_ATTRS
    }


def _bound_value(rendering: str) -> str:
    """``rendering`` with its credentials withheld, then cut to ``VALUE_CHARS`` with a marker.

    The two steps are in this order because the second would otherwise defeat the first.
    ``_USERINFO`` ends its match on the ``@`` that closes a userinfo, so a cut landing anywhere
    between a URL's ``://`` and that ``@`` deletes the one character the pattern is anchored on,
    and the whole-line pass ``log_format`` runs afterwards finds nothing left to match. Withholding
    first also spends the bound on what will actually print rather than on a credential that will
    not, so the count in the marker describes the rendering the reader was given.
    """
    text = redact_urls(rendering)
    if len(text) <= VALUE_CHARS:
        return text
    return text[:VALUE_CHARS] + CUT.format(chars=len(text) - VALUE_CHARS)


def render_value(value: object) -> str:
    """One field's value, written so the pair it sits in can still be told from the next one.

    Scalars print the way Python prints them, which is what keeps ``capped=True`` reading the way
    the runbooks read it: JSON would write that boolean ``true``, invalidating every documented
    reading of a line. Anything else is JSON, compact, so a list of ranked hits arrives
    as the object it is rather than as a Python repr no tool can parse, and arrives without the
    spaces that would scatter it across what look like several fields. A string is quoted exactly
    when it would otherwise run into its neighbour, by carrying whitespace or a quote of its own.

    Every way out passes the bound, so a field is as long as it is allowed to be however it was
    written: the cut is the last thing done to a rendering rather than the first thing done to a
    value, since escaping is what a line actually spends.

    A rendering the bound will cut is quoted rather than left bare. Otherwise the marker's two
    spaces would land in a rendering chosen for carrying none, and the pair could no longer be
    told from the next one.
    """
    if isinstance(value, str):
        text = value
    elif value is None or isinstance(value, int | float):
        text = str(value)
    else:
        return _bound_value(
            json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
            )
        )
    safe = redact_urls(text)
    if _BARE.fullmatch(safe) and len(safe) <= VALUE_CHARS:
        return safe
    return _bound_value(json.dumps(safe, ensure_ascii=False))


def render_fields(fields: Mapping[str, object]) -> str:
    """The fields as ``key=value`` pairs in name order, on one line.

    Name order rather than attachment order, because a reader comparing two lines of the same kind
    wants the same field in the same place, and ``extra`` dicts are written in whatever order the
    call site found convenient.
    """
    return " ".join(f"{key}={render_value(fields[key])}" for key in sorted(fields))
