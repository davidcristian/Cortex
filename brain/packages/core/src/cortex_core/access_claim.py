"""Close a reply that says it has no access, or found no file, after a refused file call."""

import re

from cortex_core.untrusted import TaintLedger

UNSEARCHED_FILES_NOTE = (
    "\n\n(No file was searched in this turn, since the message asked only to remember. Name the "
    "file in a new message to have it read.)"
)
UNSEARCHED_FILES_NOTES = {
    "fr": "\n\n(Aucun fichier n'a été cherché ici, car le message demandait seulement de "
    "retenir. Nommez le fichier dans un nouveau message pour le faire lire.)",
    "de": "\n\n(Hier wurde keine Datei durchsucht, da die Nachricht nur ums Merken bat. Nennen "
    "Sie die Datei in einer neuen Nachricht, damit sie gelesen wird.)",
    "es": "\n\n(Aquí no se buscó en ningún archivo, porque el mensaje solo pedía recordar. "
    "Nombra el archivo en un mensaje nuevo para que se lea.)",
    "ro": "\n\n(Nu s-a căutat în niciun fișier aici, pentru că mesajul cerea doar să fie "
    "reținut ceva. Numește fișierul într-un mesaj nou pentru a fi citit.)",
}

_NO_ACCESS = re.compile(
    r"\b(?:(?:don['\u2019]?t|do\s+not|doesn['\u2019]?t|does\s+not)\s+have\s+(?:any\s+)?access"
    r"|(?:can['\u2019]?t|cannot|can\s+not|unable\s+to|not\s+able\s+to)\s+access"
    r"|no\s+access|inaccessible)\b",
    re.IGNORECASE,
)
_NOT_FOUND = re.compile(
    r"\b(?:(?:don|doesn|didn|can|couldn)['\u2019]?t|(?:do|does|did|could)\s+not|cannot|can\s+not"
    r"|unable\s+to|not\s+able\s+to)\s+(?:see|find|locate)\s+"
    r"(?!(?:(?:a|an|the|any|your|my|that|this)\s+)?"
    r"(?:why|how|what|whether|where|when|if|reason|point|need|problem|issue|harm|way)\b)\w",
    re.IGNORECASE,
)
_CONDITION = re.compile(r"\b(?:if|once|when|whether|until)\b", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def _states(pattern: re.Pattern[str], sentence: str) -> bool:
    """Whether ``pattern`` matches ``sentence`` outside a question or a condition."""
    found = pattern.search(sentence)
    return (
        found is not None
        and not sentence.rstrip().endswith("?")
        and _CONDITION.search(sentence[: found.start()]) is None
    )


def claims_no_access(reply: str) -> bool:
    """Whether a sentence of ``reply`` says it has no access to something."""
    return any(_states(_NO_ACCESS, sentence) for sentence in _SENTENCE_END.split(reply))


def claims_not_found(reply: str) -> bool:
    """Whether a sentence of ``reply`` says it did not see, find or locate something."""
    return any(_states(_NOT_FOUND, sentence) for sentence in _SENTENCE_END.split(reply))


def unsearched_files_claim(taint: TaintLedger, reply: str) -> bool:
    """Whether ``reply`` claims no access or no file found on a turn that refused a file call."""
    return taint.sidecar_refused and (claims_no_access(reply) or claims_not_found(reply))
