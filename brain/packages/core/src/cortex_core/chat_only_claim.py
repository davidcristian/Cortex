"""Close a reply that says a fact is kept only for this chat on a turn memory stores."""

import re

KEPT_BEYOND_CHAT_NOTE = (
    "\n\n(This exchange is stored in memory and can be recalled in later chats too, not only in "
    "this one. Ask to forget it if you do not want it kept.)"
)
KEPT_BEYOND_CHAT_NOTES = {
    "fr": "\n\n(Cet échange est enregistré en mémoire et peut être rappelé aussi dans les "
    "conversations suivantes, pas seulement dans celle-ci. Demandez à l'oublier si vous ne voulez "
    "pas qu'il soit gardé.)",
    "de": "\n\n(Diese Unterhaltung ist gespeichert und kann auch in späteren Chats abgerufen "
    "werden, nicht nur in diesem. Bitten Sie darum, sie zu vergessen, wenn sie nicht gespeichert "
    "bleiben soll.)",
    "es": "\n\n(Este intercambio está guardado en memoria y puede recuperarse también en chats "
    "posteriores, no solo en este. Pide que se olvide si no quieres que se guarde.)",
    "ro": "\n\n(Acest schimb este memorat și poate fi regăsit și în conversațiile următoare, nu "
    "doar în aceasta. Cere să fie uitat dacă nu vrei să fie păstrat.)",
}

_KEEP = (
    r"\b(?:keep|keeping|kept|remember|remembering|remembered|note|noted|hold|holding|retain"
    r"|store|stored|save|saved|track)\b"
)
_CHAT = (
    r"\b(?:for|during|in|throughout|within|until\s+the\s+end\s+of|while|as\s+long\s+as"
    r"|as\s+we\s+(?:continue|go\s+on\s+with))\s+"
    r"(?:the\s+(?:rest|course|length)\s+of\s+)?"
    r"(?:this|our|the)\s+(?:current\s+)?(?:conversation|chat|session)\b(?!['\u2019]s\b)"
)
_CHAT_ONLY = re.compile(rf"{_KEEP}.*?{_CHAT}", re.IGNORECASE)
# "Not just for this chat" or "and in later ones" says the opposite of a limit.
_BEYOND = re.compile(
    r"\bnot\s+(?:just|only)\b|\b(?:beyond|future|later|next|other|every)\b", re.IGNORECASE
)

_KEEP_OTHER = (
    r"\b(?:souvien\w*|souvenir|reten\w*|retien\w*|not[ée]\w*|noterai|gard\w*|mémoris\w*"
    r"|enregistr\w*|conserv\w*|en\s+tête|à\s+l['\u2019]esprit"
    r"|merke\w*|gemerkt|behalt\w*|notier\w*|gespeichert|speicher\w*|festgehalten|vermerkt"
    r"|im\s+(?:Kopf|Hinterkopf|Gedächtnis)"
    r"|record\w*|anot\w*|apunt\w*|guard\w*|memoriz\w*|registr\w*|en\s+cuenta|en\s+mente"
    r"|re[țţt]in\w*|memor\w*|notat\w*|notez|p[ăa]str\w*|salv\w*|[țţt]in\s+minte|minte)\b"
)
_CHAT_NOUN = (
    r"(?:conversation|discussion|échange|session|chat|Gespräch|Unterhaltung|Sitzung|Konversation"
    r"|conversaci[óo]n|charla|sesi[óo]n|intercambio|conversa[țţt]i|discu[țţt]i|sesiun)\w*"
)
_CHAT_OTHER = (
    r"\b(?:pour(?!\s+le\s+chat\b)|pendant|durant|dans|au\s+cours\s+de|tout\s+au\s+long\s+de"
    r"|jusqu['\u2019]\s*à|tant\s+que\s+dure"
    r"|für|während|in|im|bis\s+zum\s+Ende|solange"
    r"|para|durante|en|a\s+lo\s+largo\s+de|hasta\s+el\s+final\s+de|mientras\s+dure"
    r"|pentru|pe\s+(?:tot\s+)?parcursul|pe\s+durata|în\s+timpul|în"
    r"|p[âa]n[ăa]\s+la\s+(?:sf[âa]r[șşs]itul|finalul))\s+"
    r"(?:(?:la\s+suite|le\s+reste|la\s+durée|la\s+fin|den\s+Rest|die\s+Dauer|Laufe|el\s+resto"
    r"|restul|durata)\s+(?:de\s+|d['\u2019]\s*)?)?"
    r"(?:(?:cette|cet|ce|notre|la|le|l['\u2019]|dieses|diesem|dieser|diese|unseres|unserem"
    r"|unserer|unsere|des|dem|der|die|das|esta|este|nuestra|nuestro|el"
    r"|acestei|acestui|această|aceasta|acest)\s*)?"
    rf"{_CHAT_NOUN}"
)
_CHAT_ONLY_OTHER = re.compile(
    rf"{_KEEP_OTHER}.*?{_CHAT_OTHER}|{_CHAT_OTHER}.*?{_KEEP_OTHER}", re.IGNORECASE
)
_BEYOND_OTHER = re.compile(
    r"\b(?:pas\s+(?:seulement|uniquement)|non\s+seulement|au-delà|prochain\w*|futur\w*"
    r"|ultérieur\w*|plus\s+tard|nicht\s+nur|künftig\w*|zukünftig\w*|später\w*|nächst\w*"
    r"|no\s+s[óo]lo|no\s+únicamente|más\s+allá|próxim\w*|posterior\w*|más\s+adelante"
    r"|nu\s+(?:doar|numai)|dincolo|viito\w*|următo\w*|ulterio\w*|mai\s+târziu)\b"
    r"|\b(?:autres?|chaque|toutes?\s+(?:les|nos)|nouvel\w*|ander\w*|jede\w*|alle\w*|neue\w*"
    r"|otr[ao]s?|cada|tod[ao]s\s+(?:las|los|nuestr[ao]s)|nuev[ao]s?|alte|fiecare|toate|nou[ăa])"
    rf"\s+(?:\w+\s+)?{_CHAT_NOUN}",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def _limits(sentence: str) -> bool:
    english = _CHAT_ONLY.search(sentence) is not None and _BEYOND.search(sentence) is None
    other = _CHAT_ONLY_OTHER.search(sentence) is not None and _BEYOND_OTHER.search(sentence) is None
    return english or other


def claims_chat_only(reply: str) -> bool:
    """Whether a statement in ``reply`` says something is kept for this chat and no longer."""
    return any(
        not sentence.rstrip().endswith("?") and _limits(sentence)
        for sentence in _SENTENCE_END.split(reply)
    )
