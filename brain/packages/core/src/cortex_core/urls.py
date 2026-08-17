r"""The URL *grammar* behind the output guardrail's laundering defense (ADR-0015).

This module *recognizes* a clickable URL in text; ``url_identity`` reduces a match to its canonical
identity, so a link collected from untrusted content and its reproduction in the reply compare
equal however the model rewrote it, ``url_spellings`` holds every way one separator character may
be written, and ``url_holdback`` answers the other half of recognizing one *mid-stream*: what may
still be growing at a buffer's end. The four modules split at the line cap and by responsibility,
as the seventh, the eleventh and the sixteenth addenda landed.

Obfuscation-resistant by construction, and deterministic + dependency-free (stdlib only). The
matcher tolerates a *defanged* scheme (``hxxp://``, ``[://]``, ``[:]``) and every spelling of a
separator character ``url_spellings`` generates (fullwidth, backslash, HTML character reference),
a **slashless authority** where a special scheme carries fewer than two solidi (``https:evil.com``,
which a URL parser resolves to the plain link, admitted only behind a host shape; ADR-0015 eleventh
addendum), a bracketed chunk anywhere in the body (so an encoded defang dot behind a literal closer
like ``evil[&#46;]com`` is consumed whole rather than cutting the match short; ADR-0015 sixth
addendum), and an **encoded separator** (``http[&#58;//]evil.com``, admitted as a bracket chunk that
carries an escape marker; ADR-0015 seventh addendum), a **whitespace-split** host, where the
gap between two dotless labels is the dot (``hxxp://evil dot com``; ADR-0015 twelfth addendum,
which the host anchor reads as a host of its own since the sixteenth), and a **tab** in the body,
which a URL parser removes from its input (``url_removals``; fifteenth addendum).
Recognized schemes are ``http(s)``, ``ftp``,
``mailto``, ``tel``, and ``data:`` (the last only behind a MIME-type anchor, so ``data:the results``
prose stays out; ADR-0015 fifth addendum). What is *not* recognized is never redacted, so the scope
stays deliberately narrow: bare addresses and bare domains stay out, and with them the *unanchored*
whitespace split (``evil dot com`` with no scheme in front of it), whose plain twin ``evil.com`` is
out on the same standing decision. See the ADR for why. Pure state- and I/O-free.

The fragments this module composes are public where ``url_holdback`` spends them, the
``url_spellings`` precedent: the matcher and the hold-back derive from one grammar, so neither can
drift from the other about what a scheme, a host or a gap is.
"""

import re

from cortex_core.url_identity import MAILTO_SCHEME, SPECIAL_SCHEMES, normalize_url
from cortex_core.url_removals import REMOVED_CHARS
from cortex_core.url_spellings import (
    CHUNK_INNER,
    CLOSE_BRACKET,
    COLON_SPELLING,
    DEFANGED_AUTHORITY_SEPS,
    DEFANGED_OPAQUE_SEPS,
    DOT_SPELLING,
    GAP_WHITESPACE,
    OPEN_BRACKET,
    SOLIDUS_SPELLING,
    SPACED_DOT,
)

# The scheme families a URL may open with, plain or *defanged*, keyed by separator shape. Authority
# schemes (`http(s)`, its CTI defang `hxxp(s)`, and `ftp`) take `://`; opaque schemes (`mailto`,
# `tel`) take a bare `:`. Every one is an intentional, clickable exfil / phishing / call vector.
# Bare addresses, bare domains, and every unlisted scheme stay out, as matching each `user@host`,
# `name.py`, or `metadata:` would redact ordinary prose. Longer variants precede their prefixes
# (`https` before `http`) so the alternation prefers the full scheme.
# The authority words are the identity module's `SPECIAL_SCHEMES` plus their CTI defang twins, so
# the scheme a backslash counts as a solidus in is declared once, beside the fold that reads it;
# `mailto` comes from the same module for the same reason, being the one opaque scheme whose
# content the host reader there has to find a domain in.
AUTHORITY_WORDS = (*SPECIAL_SCHEMES, "hxxps", "hxxp")
OPAQUE_WORDS = (MAILTO_SCHEME, "tel")

# What can never belong to a URL in prose: whitespace and the usual prose/markup closers, which
# also bound a Markdown `(url)`/`[url]`. Held once, since the two classes below are the same set
# and the same set less the authority's delimiters, and a class that drifted from its own subset
# would be a bypass nobody could see.
_NON_URL = r"\s<>\"'\)\]\}"

# A character that may belong to a URL body. A bracket `_DEFANG_CHUNK` is matched atomically ahead
# of this, so a defang token's closing bracket does not end the match early. The tab joins them
# though `_NON_URL` excludes every other blank, because a URL parser *removes* it from its input
# before parsing anything (`url_removals`), so a host broken by one is the plain host to the browser
# the user pastes into. Admitted in the body alone: the host classes below keep excluding it, which
# leaves a tab between two labels reading as the split host's gap (ADR-0015 fifteenth addendum).
_URL_CHAR = rf"(?:[^{_NON_URL}]|{REMOVED_CHARS})"

# A character that may belong to an *authority*: a body character that is not one of the three
# delimiters ending it, the backslash included since a special scheme's parser reads that as one.
HOST_CHAR = rf"[^{_NON_URL}/?#\\]"

# A label of a **whitespace-split** host: body characters carrying no dot in any reading. The
# absence is the whole point of the rule below, so it is spelled here rather than assumed.
SPLIT_LABEL = rf"(?:(?!{DOT_SPELLING}){HOST_CHAR})+"

# One gap and the label it separates from the last, which is the unit the split host repeats and
# the unit the host anchor below reads one of to know it is looking at a host at all.
SPLIT_GAP = rf"{SPACED_DOT}{SPLIT_LABEL}"

# A host whose labels are separated by whitespace instead of by a dot (`evil dot com`). Admitted
# only **immediately after the separator** and only when every label is dotless, because defanging
# *replaces* a host's dot and never adds one: a host that already carries a plain dot is finished
# before any gap could be part of it. That single constraint is what keeps the widening off prose,
# and it is why this is a branch of its own rather than one more alternative inside `_BODY`, where
# a `+` loop would re-enter it at every position and read `http://example.com dot the file` as a
# host (measured: it does, which is how the constraint was found). The trailing `_BODY` is what
# carries the rest of a split link's path (`hxxp://evil dot com/pay`), so only the host is split.
_SPLIT_HOST = rf"{SPLIT_LABEL}(?:{SPLIT_GAP})+"

# What a **host** must look like for the separator below to spend fewer than two solidi. The URL
# Standard's special-authority states, which skip a backslash, tolerate a solidus that is missing
# too, so `https:evil.example/pay` and `https:/evil.example/pay` both resolve to the plain link,
# and requiring both solidi let a live spelling anchor nothing at all. Every widening before this
# one constrained the spelling of a separator that was *there*; admitting one that is *absent*
# leaves only what follows to carry the anchor, since `https:` and any non-space run is exactly the
# prose the fullwidth addendum protected (a fullwidth colon and `no slashes here`, which is how a
# sentence names a scheme).
#
# So the anchor asks for a host, and a host is what a dot, a pair of brackets or a gap says it is: a
# *dotted name*, which every registrable domain, IPv4 literal and IDN is, a *bracketed literal
# carrying a colon*, which every IPv6 literal is and nothing else a host can be, or a **split**
# host, whose gap is the same dot spelled with whitespace (ADR-0015 sixteenth addendum). A single
# label (`https:localhost`, `https:scheme`) is declined, and that is the whole false-positive
# budget, spent where prose lives; a bare label is registrable under no public suffix, so declining
# it costs no exfil vector. The gap costs none of that budget back, because a gap carries a **dot
# token** and the space between two English words carries none, which is what keeps
# `https:no slashes here` reading as the sentence it is. The dot counts in any reading the resolver
# has (`DOT_SPELLING`, the IDNA label separators and their references), so the CJK and entity
# classes reach this position too. Consumes nothing, the `_DATA_ANCHOR` precedent below.
_HOST_ANCHOR = (
    rf"(?={HOST_CHAR}*{DOT_SPELLING}{HOST_CHAR}"
    rf"|\[{CHUNK_INNER}*:{CHUNK_INNER}*\]"
    rf"|{SPLIT_LABEL}{SPLIT_GAP})"
)

# The same anchor while its host is still **arriving** at a buffer's end, which is the one shape the
# finished grammar cannot be asked for: `https:evil dot ` is not a host yet and never will be
# without the next delta, so a hold-back wearing the anchor above would release the opening one
# character before it became a match. This asks only for the dotless label and the blank that may
# be opening a gap, and `url_holdback` pairs it with the arriving gap that carries the dot token.
_ARRIVING_HOST_ANCHOR = rf"(?={SPLIT_LABEL}{GAP_WHITESPACE})"

# The matcher's separator, per scheme family: a bare colon in any spelling, plain or defanged, for
# an opaque scheme; for an authority scheme that same colon carrying both solidi, or a defang token
# that spells the whole separator, or a *slashless* authority, which is the opaque separator with at
# most one solidus after it and the host anchor behind it. Composing the per-character alternations
# is what makes every mixture free, an entity colon in front of fullwidth solidi included. The
# complete separators come first, so a plain `://` is read as the separator it is rather than as one
# solidus and a host beginning with the other, and a defanged `[:]//` is not read as a slashless
# `[:]`. Reusing the opaque form is what keeps `http[:]evil.example` from being the spelling nobody
# remembered: a scheme whose authority slashes are gone reads exactly like an opaque URL, right up
# to the host that is the difference. Each family still pairs only with its own separators, so
# `mailto://x` finds no authority to split and `http:foo` finds no host, and the encoded chunk
# `_family` adds below is left as it was, matching with no solidus and no host anchor, since its
# escape marker is already the constraint that keeps it off prose. The anchor is a parameter rather
# than a constant so the hold-back can wear the arriving one at the same position.
OPAQUE_SEP_RE = "|".join((COLON_SPELLING, *(re.escape(s) for s in DEFANGED_OPAQUE_SEPS)))


def _authority_sep(anchor: str) -> str:
    """An authority scheme's separator alternation, with ``anchor`` behind its slashless branch."""
    return "|".join(
        (
            rf"{COLON_SPELLING}{SOLIDUS_SPELLING}{{2}}",
            *(re.escape(s) for s in DEFANGED_AUTHORITY_SEPS),
            rf"(?:{OPAQUE_SEP_RE}){SOLIDUS_SPELLING}?{anchor}",
        )
    )


# The matcher's bracket-delimited chunk in a URL *body*: an opening bracket, a non-empty inner run,
# then a closing bracket. Broader than the refanger's literal `[.]`/`[dot]` so `URL_RE` also eats
# a defang dot whose inner is *encoded* (`[&#46;]`, `[%2e]`) sitting behind a *literal* closing
# bracket: that raw `]`/`)`/`}` (excluded from `_URL_CHAR`) would otherwise end the match before
# `normalize_url`'s decode could expose the token to the refanger (ADR-0015 sixth addendum). Only a
# chunk that *decodes to* `[.]`/`[dot]` folds to a dot; any other (`[0]` in a query, `(a)` in a
# path) is consumed but kept verbatim in the identity, so the widening is symmetric and over-redacts
# a fuller span at worst. The inner is `+` (never empty), so a bare `[]` array-param still ends it.
_DEFANG_CHUNK = rf"{OPEN_BRACKET}{CHUNK_INNER}+{CLOSE_BRACKET}"

# The matcher's bracket chunk at the *separator* position (`http[&#58;//]evil.com`): the same shape,
# but its inner must carry an escape marker (`&` or `%`). That constraint is what keeps the widening
# honest (ADR-0015 seventh addendum). The separator anchors the whole match and so is matched
# before any decoding can run, but it does not follow that the encodings must be enumerated there:
# requiring only the *shape* of an escape leaves `normalize_url`'s decode fixpoint to resolve
# whichever encoding it actually was, so no table of encodings appears in the anchor. The marker is
# load bearing: an unconstrained chunk here would match ordinary prose like `http(s)-only`, which
# strict mode would then redact out of the repo's own docs.
_ENCODED_SEP_CHUNK = rf"{OPEN_BRACKET}{CHUNK_INNER}*[&%]{CHUNK_INNER}*{CLOSE_BRACKET}"


def _family(words: tuple[str, ...], seps: str) -> str:
    """A regex alternation: any of ``words``, then that family's ``seps`` or an encoded chunk."""
    return rf"(?:{'|'.join(words)})(?:{seps}|{_ENCODED_SEP_CHUNK})"


# The `data:` scheme opens an inline `data:<mediatype>[;base64],<data>` URL: a clickable phishing
# page / exfil payload. Unlike the bare-scheme families it is admitted only when the colon is
# followed by a MIME-type shape (`type/subtype`, a `/`-bearing token) or the `,`/`;` that begins the
# data, so prose like `data:the results` (no slash, no immediate `,`/`;`) stays out while a real
# data URL matches (ADR-0015 fifth addendum). Its separator may be defanged (`data[:]`) or encoded
# (`data[&#58;]`) like the other opaque schemes, sharing `_family` so it cannot drift from them;
# identity folds it whole (no `://` authority to split, so the payload lowercases symmetrically,
# harmless for comparison). The lookahead consumes nothing; the body matches from the MIME type.
_DATA_ANCHOR = r"(?=[\w.+-]+/|[;,])"
_DATA_SCHEME = rf"{_family(('data',), OPAQUE_SEP_RE)}{_DATA_ANCHOR}"


# Every scheme opening this grammar recognizes, and the ordinary body that follows one: a run of
# characters that cannot leave the URL, with a bracket chunk consumed atomically. The authority
# family is named on its own because the split host below is a **host** grammar, and only these
# schemes have one; `mailto:`/`tel:`/`data:` reach their content through a colon and no authority.
_AUTHORITY = _family(AUTHORITY_WORDS, _authority_sep(_HOST_ANCHOR))
ARRIVING_AUTHORITY = _family(AUTHORITY_WORDS, _authority_sep(_ARRIVING_HOST_ANCHOR))
_SCHEME = rf"(?:{_AUTHORITY}|{_family(OPAQUE_WORDS, OPAQUE_SEP_RE)}|{_DATA_SCHEME})"
_BODY = rf"(?:{_DEFANG_CHUNK}|{_URL_CHAR})+"

# A clickable link, plain or defanged, anchored at a word boundary (so `sftp://` / `hotel:` are not
# partial-matched) and matched liberally to the first character that cannot belong to one. Defanged,
# encoded, fullwidth and whitespace-split forms are reduced to one identity by `normalize_url`. The
# split host is tried first, so a link spelled that way is read whole rather than truncated at its
# first gap; it fails at the separator on every ordinary URL, which then matches exactly as before.
URL_RE = re.compile(rf"\b(?:{_AUTHORITY}{_SPLIT_HOST}(?:{_BODY})?|{_SCHEME}{_BODY})", re.IGNORECASE)


def extract_urls(text: str) -> frozenset[str]:
    """Every clickable URL in ``text`` (any listed scheme), normalized for identity comparison.

    Both sides of the laundering defense use this one function, with collection from untrusted tool
    results (``TaintLedger.observe``) and the user-message allowlist, so a collected URL and its
    reappearance in a reply always compare equal.
    """
    return frozenset(normalize_url(match.group()) for match in URL_RE.finditer(text))
