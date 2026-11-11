"""Read a reply that says the fact was not saved, for a turn whose exchange memory stores."""

import re

_NOT = (
    r"(?:have\s+not|haven['\u2019]t|has\s+not|hasn['\u2019]t|did\s+not|didn['\u2019]t"
    r"|could\s+not|couldn['\u2019]t|was\s+not\s+able\s+to|wasn['\u2019]t\s+able\s+to"
    r"|was\s+unable\s+to|cannot|can['\u2019]t|will\s+not|won['\u2019]t)"
)
_QUOTE = r"[\"'\u201c\u2018]?"
_ENGLISH = re.compile(
    rf"\bI\s+{_NOT}\s+(?:(?:yet|actually|really|properly)\s+)?{_QUOTE}"
    r"(?:sav(?:e|ed)|stor(?:e|ed)|keep|kept|record(?:ed)?|memori[sz](?:e|ed)|not(?:e|ed))\b"
    rf"|\b(?:was|were|is|are|has|have)(?:\s+not|n['\u2019]t)\s+(?:been\s+)?(?:yet\s+)?{_QUOTE}"
    r"(?:saved|stored|kept|recorded|memori[sz]ed|noted)\b",
    re.IGNORECASE,
)
# Each verb is one the other four languages use for keeping and English does not share.
_OTHER = re.compile(
    r"(?<!\w)(?:pas|nicht|no|nu)\s+(?:[\w'\u2019-]+\s+){0,3}?"
    r"(?:enregistr\w*|gard[ée]\w*|garder|mémoris\w*|sauvegard\w*|reten\w*|retenir|conserv\w*"
    r"|souvenir|gespeichert|speichern|gemerkt|merken|notiert|behalten|festgehalten"
    r"|(?:guard|anot|apunt)(?:ad|ar|é|ó)\w*|memoriz\w*|recordad\w*"
    r"|salvat\w*|salva|re[țţt]inut\w*|memorat\w*|notat\w*|p[ăa]strat\w*)(?!\w)",
    re.IGNORECASE,
)
# A file, a folder or a reminder that was not saved is not the fact.
_OTHER_THING = re.compile(
    r"\b(?:files?|folders?|director(?:y|ies)|documents?|changes|reminders?|schedule|calendar"
    r"|alarms?|drafts?|disk|fichiers?|dossiers?|rappels?|Datei\w*|Ordner\w*|Dokument\w*"
    r"|Erinnerung\w*|archivos?|carpetas?|documentos?|recordatorios?|fi[șşs]ier\w*|dosar\w*"
    r"|memento\w*)\b|\w\.[a-z]{2,5}\b",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
_CLAUSE_END = re.compile(
    r"[,;:]|\s+(?:and|but|so|et|mais|donc|und|aber|y|pero|así\s+que|și|şi|dar)\s+",
    re.IGNORECASE,
)


def _says_unsaved(clause: str) -> bool:
    found = _ENGLISH.search(clause) or _OTHER.search(clause)
    return found is not None and _OTHER_THING.search(clause) is None


def claims_unsaved(reply: str) -> bool:
    """Whether a clause of a statement in ``reply`` says the fact was not saved."""
    return any(
        _says_unsaved(clause)
        for sentence in _SENTENCE_END.split(reply)
        if not sentence.rstrip().endswith("?")
        for clause in _CLAUSE_END.split(sentence)
    )
