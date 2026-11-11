"""Read a reply in French, German, Spanish or Romanian saying it has no access or no file."""

import re

from cortex_core.memory_claim_other import after_condition

_SOME = r"(?:[\w'\u2019]+\s+){0,4}?"
_NO_ACCESS = re.compile(
    r"(?<!\w)(?:(?:pas|aucun|sans)\s+(?:d['\u2019]\s*)?acc[eè]s"
    r"|ne\s+(?:peux|pourrai|pouvais|pourrais)\s+pas\s+(?:y\s+)?acc[ée]der|inaccessibles?"
    rf"|kein\w*\s+(?:zugriff|zugang)|nicht\s+{_SOME}zugreifen"
    r"|nicht\s+zug[äa]nglich|unzug[äa]nglich"
    r"|no\s+tengo\s+(?:ning[úu]n\s+)?acceso|(?:sin|ning[úu]n)\s+acceso"
    r"|no\s+(?:puedo|pude|podr[ée])\s+acceder|inaccesibles?"
    r"|nu\s+am\s+(?:niciun\s+)?acces|(?:f[ăa]r[ăa]|niciun)\s+acces"
    r"|nu\s+(?:pot|am\s+putut)\s+(?:s[ăa]\s+)?acces\w*|inaccesibil\w*)(?!\w)",
    re.IGNORECASE,
)
_FIND_FR = r"(?:trouv\w*|vu|vois|rep[ée]r\w*|localis\w*)"
_NOT_FOUND = re.compile(
    rf"(?<!\w)(?:ne\s+(?:trouve|vois|retrouve|localise)\s+(?:pas|aucun\w*|rien)"
    rf"|n['\u2019]ai\s+(?:pas|rien|aucun\w*)\s+(?:\w+\s+){{0,2}}?{_FIND_FR}"
    rf"|n['\u2019]ai\s+(?:trouv[ée]|vu|rep[ée]r[ée])\s+(?:aucun\w*|rien)"
    r"|ne\s+(?:peux|parviens|r[ée]ussis)\s+pas\s+(?:[àa]\s+)?(?:\w+\s+)?"
    r"(?:trouver|voir|localiser)"
    rf"|(?:kann|konnte|k[öo]nnte)\s+{_SOME}nicht\s+(?:finden|sehen|entdecken)"
    r"|(?:finde|fand|sehe|sah)\s+(?:\w+\s+){0,3}?(?:keine?\w*|nichts)"
    r"|nicht\s+gefunden|(?:keine?\w*|nichts)\s+(?:\w+\s+)?gefunden"
    r"|no\s+(?:encuentro|encontr[ée]|veo|vi|localizo|localic[ée]"
    r"|(?:puedo|pude|he\s+podido)\s+(?:encontrar|ver|localizar)|he\s+(?:encontrado|visto))"
    r"|nu\s+(?:g[ăa]sesc|v[ăa]d|am\s+g[ăa]sit|am\s+v[ăa]zut"
    r"|(?:pot|am\s+putut)\s+(?:s[ăa]\s+)?(?:g[ăa]si|g[ăa]sesc|vedea|v[ăa]d|localiza|localizez)))"
    r"(?!\w)(?!\s*,?\s*(?:(?:de|d['\u2019]|l['\u2019]|la|le|un|une|den|einen|keinen|el|ning[úu]n"
    r"|ninguna|niciun|nicio)\s*)?(?:pourquoi|comment|int[ée]r[êe]t|raison|probl[eè]me"
    r"|inconv[ée]nient|objection|n[ée]cessit[ée]|que|qu['\u2019]|dass|grund|sinn|problem|warum"
    r"|wieso|weshalb|wie"
    r"|notwendigkeit|anlass|por\s+qu[ée]|c[óo]mo|raz[óo]n|motivo|necesidad|sentido|inconveniente"
    r"|de\s+ce|cum|motiv\w*|rost\w*|nevoi\w*|problem\w*)(?!\w))",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def _states(pattern: re.Pattern[str], sentence: str) -> bool:
    """Whether ``pattern`` matches ``sentence`` outside a question or after a condition."""
    found = pattern.search(sentence)
    return (
        found is not None
        and not sentence.rstrip().endswith("?")
        and not after_condition(sentence, found.start())
    )


def claims_no_access_other(reply: str) -> bool:
    """Whether a sentence of ``reply`` says in another language that it has no access."""
    return any(_states(_NO_ACCESS, sentence) for sentence in _SENTENCE_END.split(reply))


def claims_not_found_other(reply: str) -> bool:
    """Whether a sentence of ``reply`` says in another language it did not find or see something."""
    return any(_states(_NOT_FOUND, sentence) for sentence in _SENTENCE_END.split(reply))
