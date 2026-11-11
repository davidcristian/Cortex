"""Read a reply in French, German, Spanish or Romanian that says something was not found."""

import re

from cortex_core.memory_claim_other import after_condition

_NEGATION = re.compile(
    r"(?<!\w)n['\u2019-](?=\w)|(?<!\w)(?:ne|pas|jamais|rien|aucun\w*|nicht|nie|niemals|kein\w*"
    r"|nichts|no|nunca|jam[áa]s|ning[uú]n\w*|nada|nu|niciun\w*|nicio|nimic|niciodat[ăa])(?!\w)",
    re.IGNORECASE,
)
_FOUND_OR_STORED = re.compile(
    r"(?<!\w)(?:trouv\w*|retrouv\w*|(?:enregistr|m[ée]moris|sauvegard|gard|conserv)(?:é|ée|és|ées)"
    r"|retenu\w*|gefunden|finde|finden|gespeichert|gemerkt|hinterlegt|gesichert|vorhanden"
    r"|auffindbar|encontr\w*|encuentro|hall[ée]|guardad\w*|guard[óé]|guardaba\w*|almacenad\w*"
    r"|registrad\w*|memorizad\w*|g[ăa]s(?:it|esc|i)\w*|salvat\w*|memorat\w*|stocat\w*"
    r"|re[țţt]inut\w*|p[ăa]strat\w*|[îi]nregistrat\w*)(?!\w)",
    re.IGNORECASE,
)
_NO_RECORD = re.compile(
    r"(?<!\w)(?:introuvable|aucune?\s+(?:trace|enregistrement|information)|pas\s+de\s+trace"
    r"|kein\w*\s+(?:eintr[äa]g\w*|hinweis\w*|information\w*|spur)"
    r"|no\s+(?:tengo|ten[íi]a|hay|hab[íi]a)\s+(?:ning[uú]n\w*|constancia|registro\w*)"
    r"|nu\s+(?:am|aveam|exist[ăa])\s+(?:niciun\w*|nicio))(?!\w)",
    re.IGNORECASE,
)
# "Il n'est plus enregistré" and "nu mai este salvat" say the delete held, as "no longer" does.
_HELD = re.compile(
    r"(?<!\w)(?:plus|reste|restent|subsiste\w*|mehr|übrig|ya\s+no|queda|quedan|mai|r[ăa]mas\w*)"
    r"(?!\w)",
    re.IGNORECASE,
)
# "Votre nouveau numéro n'a pas été enregistré" reports a fact of this message, which a forget
# keeps out.
_NEW = re.compile(
    r"(?<!\w)(?:nouve(?:au|lle)|neue\w*|nuev[oa]s?|no(?:u|ua|ul|ile))(?!\w)", re.IGNORECASE
)
_CLAUSE_END = re.compile(r"[,;:]|\b(?:et|mais|und|aber|y|pero|și|şi|dar)\b", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def says_not_stored_other(reply: str) -> bool:
    """Whether a statement in ``reply`` says in one of four other languages it found nothing."""
    for sentence in _SENTENCE_END.split(reply):
        if sentence.rstrip().endswith("?"):
            continue
        ends = [*(found.start() for found in _CLAUSE_END.finditer(sentence)), len(sentence)]
        starts = [0, *(found.end() for found in _CLAUSE_END.finditer(sentence))]
        if any(
            _not_stored(sentence[start:end]) and not after_condition(sentence, end)
            for start, end in zip(starts, ends, strict=True)
        ):
            return True
    return False


def _not_stored(clause: str) -> bool:
    """Whether ``clause`` negates a find or a store, or names no record, and no delete that held."""
    if _HELD.search(clause) or _NEW.search(clause):
        return False
    if _NO_RECORD.search(clause):
        return True
    return _NEGATION.search(clause) is not None and _FOUND_OR_STORED.search(clause) is not None
