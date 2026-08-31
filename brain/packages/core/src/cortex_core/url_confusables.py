"""The curated cross-script confusable fold, behind the output guardrail (ADR-0015).

Split from ``url_identity``, which owns the identity and the seven passes around this one, by
responsibility rather than by size. Every other pass there is a resolver's own reading, so the
spelling it folds and the spelling it folds to are the same host; this pass judges what looks
alike, and a confusable host is a different host that renders like the one it imitates. The
lookalike policy reads a host with this pass switched off, because a host built wholly out of
table entries would otherwise fold to plain ASCII and carry no sign of anything, and the pass
living in its own module is what lets ``normalize_url`` be run either way (ADR-0015 fourteenth
addendum).

Deterministic and dependency-free (stdlib only), with no state and no I/O.
"""

# The common single-script confusables: Cyrillic and Greek letters that render identically to an
# ASCII Latin letter, folded to that letter so a homoglyph host (`<cyr>evil.example`) normalizes to
# its plain twin (ADR-0015 fourth addendum). A curated, high-confidence table, deterministic and
# dependency-free, rather than the full UTS-39 confusables set, which ADR-0015's thirteenth
# addendum priced and declined: an attacker chooses the codepoint, so the boundary is the policy
# that reads the host's shape (fourteenth addendum) rather than any table. Folding only ever widens
# a redaction and runs on both sides of the comparison, so its false-positive surface is a
# legitimately Cyrillic or Greek URL, rare in a single-user deployment and already redacted on a
# tainted turn under the lookalike and strict policies. Keys are `\u` escapes so the source stays
# ASCII and each confusable codepoint is explicit.
_CONFUSABLES = str.maketrans(
    {
        # Cyrillic -> Latin, lowercase (a e o p c y x i j s d h l)
        "\u0430": "a",
        "\u0435": "e",
        "\u043e": "o",
        "\u0440": "p",
        "\u0441": "c",
        "\u0443": "y",
        "\u0445": "x",
        "\u0456": "i",
        "\u0458": "j",
        "\u0455": "s",
        "\u0501": "d",
        "\u04bb": "h",
        "\u04cf": "l",
        # Cyrillic -> Latin, the classic uppercase lookalikes (A B E K M H O P C T Y X)
        "\u0410": "A",
        "\u0412": "B",
        "\u0415": "E",
        "\u041a": "K",
        "\u041c": "M",
        "\u041d": "H",
        "\u041e": "O",
        "\u0420": "P",
        "\u0421": "C",
        "\u0422": "T",
        "\u0423": "Y",
        "\u0425": "X",
        # Greek -> Latin (omicron/rho, both cases)
        "\u03bf": "o",
        "\u039f": "O",
        "\u03c1": "p",
        "\u03a1": "P",
    }
)


def fold_confusables(url: str) -> str:
    """Fold the curated cross-script confusable letters to their ASCII twin (``_CONFUSABLES``)."""
    return url.translate(_CONFUSABLES)
