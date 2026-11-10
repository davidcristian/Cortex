"""Read a reply in French, German, Spanish or Romanian that says something was scheduled."""

import re

from cortex_core.memory_claim_other import stated

_DONE_FR = (
    r"\b(?:j['\u2019]ai|c['\u2019]est|(?:est|sont)(?:\s+maintenant)?)\s+"
    r"(?:bien\s+|aussi\s+|d[ée]j[àa]\s+)?"
)
_SOME_DE = r"(?:(?!(?:nicht|nie|kein\w*)\b)[\w'\u2019:]+\s+){0,6}?"
_ALONE = re.compile(
    rf"{_DONE_FR}(?:programm|planifi)[ée]e?s?\b"
    r"|\b(?:he|hemos|ha\s+sido|est[áa]|queda|qued[óo])\s+programad[oa]s?\b"
    r"|\b(?:am|a\s+fost|e|este)\s+programat[ăa]?\b",
    re.IGNORECASE,
)
_SET = re.compile(
    rf"{_DONE_FR}(?:r[ée]gl|cr[ée]|ajout|enregistr|not|mis)[ée]?e?s?\b"
    rf"|\bich\s+habe\s+{_SOME_DE}(?:eingestellt|erstellt|gestellt|angelegt|hinzugef[üu]gt"
    r"|eingerichtet|gesetzt|notiert|gespeichert|geplant|eingeplant|programmiert)\b"
    rf"|\b(?:ist|sind|wurde|wurden)\s+{_SOME_DE}(?:eingestellt|erstellt|gestellt|angelegt"
    r"|eingerichtet|gesetzt|gespeichert|geplant|eingeplant|programmiert)\b"
    r"|\b(?:he|hemos|ha\s+sido|est[áa]|queda|qued[óo])\s+(?:configurad|cread|añadid|agregad"
    r"|puest|establecid|anotad|guardad|fijad)[oa]s?\b"
    r"|\b(?:am|a\s+fost|e|este)\s+(?:setat|creat|ad[ăa]ugat|pus|notat|salvat|stabilit)[ăa]?\b",
    re.IGNORECASE,
)
_NOUN = re.compile(
    r"\b(?:rappels?|alarmes?|minuteurs?|t[âa]ches?|r[ée]veils?|erinnerung(?:en)?|wecker|timer"
    r"|alarm|aufgaben?|recordatorios?|alarmas?|temporizador(?:es)?|tareas?|avisos?|memento\w*"
    r"|alarm[ăa]|reamintir\w*|temporizator\w*|sarcin\w*)\b",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def claims_scheduled_other(reply: str) -> bool:
    """Whether a statement in ``reply`` says in one of four other languages that it scheduled."""
    for sentence in _SENTENCE_END.split(reply):
        if sentence.rstrip().endswith("?"):
            continue
        named = _NOUN.search(sentence) is not None
        patterns = (_ALONE, _SET) if named else (_ALONE,)
        if any(
            stated(sentence, match) for pattern in patterns for match in pattern.finditer(sentence)
        ):
            return True
    return False
