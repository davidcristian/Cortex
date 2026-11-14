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
COPULAS_OTHER = (
    "est|sont|était|étaient|ist|sind|war|waren|es|son|era|eran|está|están|estaba|estaban"
    "|este|e|sunt|erau"
)
# The same in French, German, Spanish and Romanian, where a possessive can follow the first noun.
STATEMENT_OTHER = _statement(
    r"(?:mon|ma|mes|notre|nos|mein\w{0,2}|unser\w{0,2}|mi|mis|nuestr[oa]s?"
    r"|[\w-]+\s+(?:meu|mea|mei|mele|nostru|noastr[ăa]|no[șşs]tri|noastre))",
    COPULAS_OTHER,
)
# At most eight words of subject, a copula and a value, or in German a copula last, as in
# "las llaves están en el coche" or "dass meine Schwester Vegetarierin ist".
STATED_OTHER = (
    rf"\W*(?:(?!(?:que|qui|dass|c[ăa])\b)[\w'\u2019-]+\s+){{0,8}}?"
    rf"(?:(?:{COPULAS_OTHER}|suis|bin|soy|estoy)\s+{_VALUE_WORD}(?:\s+{_VALUE_WORD}){{0,3}}"
    r"|ist|sind|war|waren|bin)[.!]?"
)
# A possessive, at most six words, then a value holding a digit or an at sign, as in
# "my phone number 0721 555 019".
POSSESSED_VALUE = (
    rf"\W*(?:my|our)\s+(?:[\w'\u2019-]+\s+){{1,6}}?(?=\S*[\d@]){_VALUE_WORD}"
    rf"(?:\s+{_VALUE_WORD}){{0,3}}[.!]?"
)
# The English statement of a present value on one line, with its possessive, fact words and
# value as groups.
FACT_VALUE = (
    rf"\b(?P<owner>my|our|his|her|their)\s+(?P<fact>(?:[\w'\u2019-]+\s+){{1,6}}?)"
    rf"(?:is|are)\s+(?P<value>{_VALUE_WORD}(?:\s+{_VALUE_WORD}){{0,3}}?)[.!]?[ \t]*$"
)
