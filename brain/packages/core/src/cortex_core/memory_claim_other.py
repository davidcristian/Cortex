"""Read a reply in French, German, Spanish or Romanian that says something was noted or kept."""

import re

_KEPT_FR = r"(?:not[ée]|enregistr[ée]|m[ée]moris[ée]|retenu|pris\s+note)\w*"
_PRONOUN_FR = r"(?:le\s+|la\s+|les\s+|l['\u2019])?"
_SOME_DE = r"(?:(?!(?:nicht|nie|kein\w*)\b)[\w'\u2019]+\s+){0,4}?"
_CLAIM = re.compile(
    rf"\bc['\u2019]est\s+(?:bien\s+|aussi\s+)?{_KEPT_FR}"
    rf"|\bj['\u2019]ai\s+(?:bien\s+|aussi\s+|d[ée]j[àa]\s+)?{_KEPT_FR}"
    rf"|\bje\s+(?:l['\u2019]|les\s+)ai\s+(?:bien\s+)?{_KEPT_FR}"
    rf"|(?<!\bque\s)\bje\s+{_PRONOUN_FR}(?:retiens|retiendrai|note|noterai|m[ée]moriserai"
    r"|enregistrerai)\b"
    rf"|\bje\s+(?:m['\u2019]en\s+souviendrai|vais\s+(?:m['\u2019]en\s+souvenir"
    rf"|{_PRONOUN_FR}(?:noter|retenir|m[ée]moriser|enregistrer)))\b"
    r"|\b(?:ist|sind|wurde)\s+(?:jetzt\s+|schon\s+|nun\s+)?(?:notiert|gespeichert|vermerkt|gemerkt)\b"
    rf"|\bich\s+(?:habe\s+{_SOME_DE}(?:notiert|gespeichert|vermerkt|gemerkt|aufgeschrieben)"
    rf"|werde\s+{_SOME_DE}(?:merken|notieren|speichern|aufschreiben)"
    r"|merke?\s+(?:es\s+|das\s+)?mir(?![^,.;:!?]*\b(?:schlecht|gut|schwer|leicht)\b)"
    r"|notiere|speichere)\b"
    r"|\b(?:merke?|notiere|speichere)\s+ich\b"
    r"|(?<!\bque\s)\b(?:lo|la|los|las)\s+(?:he\s+)?(?:anotad|apuntad|guardad|memorizad|registrad)"
    r"[oa]s?\b|\b(?:recordar[ée]|guardar[ée]|anotar[ée]|apunto|anoto|tendr[ée]\s+en\s+cuenta"
    r"|tengo\s+en\s+cuenta|tomo\s+nota)\b"
    r"|\b(?:he|queda)\s+(?:anotado|apuntado|guardado|memorizado|registrado|tomado\s+nota)\b"
    r"|\bam\s+(?:notat|re[țţt]inut|salvat|memorat|[îi]nregistrat)\b|\b(?:e|este)\s+notat\b"
    r"|\bvoi\s+(?:[țţt]ine\s+minte|re[țţt]ine|nota|salva|memora)\b"
    r"|\bo\s+s[ăa]\s+(?:[țţt]in\s+minte|re[țţt]in|notez|salvez)\b|\bre[țţt]in\b",
    re.IGNORECASE,
)
_OPENING = re.compile(
    r"^\W*(?:(?:d['\u2019]accord|ok|okay|parfait|alles\s+klar|gut|vale|perfecto|entendido|bine"
    r"|perfect)\W+)?(?:notée?s?|notiert|vermerkt|gespeichert|anotado|apuntado|guardado|notat"
    r"|re[țţt]inut|salvat)\b",
    re.IGNORECASE,
)
_CONDITION = re.compile(
    r"(?<!\w)(?:si|s['\u2019]ils?|quand|wenn|falls|sofern|sobald|cuando|dac[ăa]|c[âa]nd)(?!\w)",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    r"(?<!\w)n['\u2019-](?=\w)"
    r"|(?<!\w)(?:pas|jamais|rien|nicht|nie|niemals|kein\w*|no|nunca|nada|nu|nimic|niciodat[ăa])"
    r"(?!\w)",
    re.IGNORECASE,
)
_CLAUSE_END = re.compile(r"[,;:]|\b(?:et|mais|und|aber|y|pero|și|şi|dar)\b", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def claims_kept_other(reply: str) -> bool:
    """Whether a statement in ``reply`` says in one of four other languages that it kept a fact."""
    if _OPENING.search(reply.lstrip().partition("\n")[0]):
        return True
    return any(
        _stated(sentence, match)
        for sentence in _SENTENCE_END.split(reply)
        if not sentence.rstrip().endswith("?")
        for match in _CLAIM.finditer(sentence)
    )


def _stated(sentence: str, match: re.Match[str]) -> bool:
    """Whether ``match`` follows no condition in ``sentence`` and its clause holds no negation."""
    if _CONDITION.search(sentence, 0, match.start()):
        return False
    starts = [found.end() for found in _CLAUSE_END.finditer(sentence, 0, match.start())]
    after = _CLAUSE_END.search(sentence, match.end())
    end = len(sentence) if after is None else after.start()
    return _NEGATION.search(sentence, starts[-1] if starts else 0, end) is None
