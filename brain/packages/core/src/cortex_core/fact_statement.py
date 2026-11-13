"""The patterns of a short statement of a fact, such as ``My phone is 0721 555 019.``."""

_VALUE_WORD = r"(?!-(?:\s|$))[^\s,;:?!()\u2013\u2014]+"


def _statement(possessive: str, copulas: str) -> str:
    return (
        rf"\W*{possessive}\s+(?:[\w'\u2019-]+\s+){{0,6}}?(?:{copulas})\s+"
        rf"{_VALUE_WORD}(?:\s+{_VALUE_WORD}){{0,3}}[.!]?"
    )


# A possessive, at most six words, a copula, then a value of at most four words and no second
# clause, as in "My phone is 0721 555 019."
STATEMENT = _statement("(?:my|our|his|her|their)", "is|are|was|were")
# The same in French, German, Spanish and Romanian, where a possessive can follow the first noun.
STATEMENT_OTHER = _statement(
    r"(?:mon|ma|mes|notre|nos|mein\w{0,2}|unser\w{0,2}|mi|mis|nuestr[oa]s?"
    r"|[\w-]+\s+(?:meu|mea|mei|mele|nostru|noastr[ăa]|no[șşs]tri|noastre))",
    "est|sont|était|étaient|ist|sind|war|waren|es|son|era|eran|está|están|estaba|estaban"
    "|este|e|sunt|erau",
)
# The English statement on one line, with its possessive, fact words and value as groups.
FACT_VALUE = (
    rf"\b(?P<owner>my|our|his|her|their)\s+(?P<fact>(?:[\w'\u2019-]+\s+){{1,6}}?)"
    rf"(?:is|are|was|were)\s+(?P<value>{_VALUE_WORD}(?:\s+{_VALUE_WORD}){{0,3}}?)[.!]?[ \t]*$"
)
