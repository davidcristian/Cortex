"""What a record carries beyond the standard attributes, and how those fields are written down.

Every ``extra=`` this repo attaches rides its ``LogRecord`` as an ordinary attribute,
indistinguishable from the two dozen ``logging`` puts there itself. This module answers the two
pure questions that follow: which attributes are the record's own and which came from a caller,
and what a caller's value looks like once it is printed. ``log_format.py`` is the stdlib adapter
that spends both, and it is the only caller that has to exist.

**Redaction lives here rather than at the call sites** because the whole point of a formatter is
that it prints fields nobody enumerated. A future adapter attaching ``extra={"token": ...}``
reaches an operator's terminal without anyone having reviewed that line, and AGENTS.md bans
secrets in logs outright, so the defence has to sit where the printing happens. It has two halves
because the leak has two shapes:

- A field **named** for a secret is withheld by name, and withheld *visibly*: an absent key and a
  held-back one are different facts, and a reader who cannot tell them apart will go looking for
  the field that was never attached.
- A credential **inside a URL** is withheld by shape, over the whole rendered line rather than
  field by field, because that one arrives in the message and in a traceback at least as often as
  in a field. ``redis://:pw@redis:6379`` is what a connection error prints, and the connection
  URL is how both the session store and the mail bridge are configured.

The name list is a denylist and not an allowlist on purpose. An allowlist would have to be edited
for every new field, which is the invisible-field defect this module exists to end wearing a
different hat: a field nobody had registered would be silently dropped instead of never printed,
and a silent drop is the harder of the two to notice. A denylist errs the other way, toward
printing a name it does not recognize, and it is deliberately blunt about matching: ``token``
withholds a field called ``max_tokens`` too. Withholding a token count costs a reader one number
they can recover from the message; printing a bearer token costs the deployment its seam.
"""

import json
import logging
import re
from collections.abc import Mapping

# What stands in for a value this module will not print. Visible on purpose, per the docstring.
REDACTED = "<redacted>"

# The attributes ``logging`` puts on every record itself, plus the two a ``Formatter`` adds while
# it runs. Anything else on a record was attached by a caller and is what a reader came for.
# Written down rather than derived from a sample record: a Python release that adds an attribute
# then reddens a test here instead of quietly printing a new stdlib field as if a caller had
# attached it, which is the one way this set can go wrong without anyone touching this repo.
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
# credential, there being no ``@`` to end the match.
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


def render_value(value: object) -> str:
    """One field's value, written so the pair it sits in can still be told from the next one.

    Scalars print the way Python prints them, which is what keeps ``capped=True`` reading the way
    the runbooks read it: JSON would spell that boolean ``true`` and quietly invalidate every
    documented reading of a line. Anything else is JSON, compact, so a list of ranked hits arrives
    as the object it is rather than as a Python repr no tool can parse, and arrives without the
    spaces that would scatter it across what look like several fields. A string is quoted exactly
    when it would otherwise run into its neighbour, by carrying whitespace or a quote of its own.
    """
    if isinstance(value, str):
        text = value
    elif value is None or isinstance(value, int | float):
        text = str(value)
    else:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
        )
    return text if _BARE.fullmatch(text) else json.dumps(text, ensure_ascii=False)


def render_fields(fields: Mapping[str, object]) -> str:
    """The fields as ``key=value`` pairs in name order, on one line.

    Name order rather than attachment order, because a reader comparing two lines of the same kind
    wants the same field in the same place, and ``extra`` dicts are written in whatever order the
    call site found convenient.
    """
    return " ".join(f"{key}={render_value(fields[key])}" for key in sorted(fields))
