"""The curated cross-script *confusable* fold, behind the output guardrail (ADR-0015)."""

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
