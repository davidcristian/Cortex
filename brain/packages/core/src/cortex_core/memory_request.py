"""Read whether a person's message asks that something not be kept in memory."""

import re

# "Keep me waiting" is an idiom, and so is "keep it to yourself" when it ends its clause or asks
# to share; "or anyone" after it asks not to keep. "Don't note everything, but remember" keeps.
_IDIOM = (
    r"(?!(?:\s+(?:it|this|that|them))?\s+to\s+(?:yourself|yourselves)\b"
    r"(?:\s*(?:[.!?]|$)|\s*[,;:](?!\s*(?:or|nor|and|but|not|never|neither|either|even)\b)"
    r"|(?:\s*,)?\s+(?:and\s+)?(?:tell|share|show|pass|send|spread)\b)"
    r"|\s+(?:me|us|him|her|them|everyone|people)\s+\w+ing\b)"
)
_ALL_BUT = (
    r"(?!\s+(?:everything|it\s+all|all\s+of\s+it)\W+(?:but|just|only)\s+(?:please\s+)?"
    r"(?:remember|note|keep|save|store)\b)"
)
_KEEP = (
    rf"(?:(?:save|store|keep{_IDIOM}|remember|record|memori[sz]e|note"
    rf"|write(?=(?:\s+\w+)?\s+down\b)){_ALL_BUT})"
)
_NOT = r"(?:don['\u2019]?t|do\s+not|never)"
# A clause also starts after a spaced hyphen, an en or em dash or an opening bracket.
_BREAK = r"[,;:]\s*|\s-+\s*|[\u2013\u2014(\[]\s*"
# A request starts a clause, after any adverbs, or follows a conjunction; "I just forget" and
# "people just forget" state a habit.
_SUBJECT = r"(?<!\bI\s)(?<!\bwe\s)(?<!\byou\s)(?<!\bthey\s)"
_OPENS = (
    rf"(?:^\W*|{_BREAK}|{_SUBJECT}\b(?:and|but|so|please|kindly)\s+|\bwhat\s+I\s+meant?\s+is,?\s+)"
    r"(?:(?:please|also|just|then|actually|kindly|I\s+meant?(?:\s+to\s+say)?,?)\s+)*"
)
# After any other word an adverb opens a request only when the message follows the verb:
# "use it once then forget it" asks, "my kids then forget their homework" states a habit.
_LOOSE = rf"{_SUBJECT}\b(?:also|just|then|actually)\s+"
_MESSAGE = r"\W*(?:it|this|that|these|those|them|my|mine|any|anything|everything|what)\b"
_NOT_TO_KEEP = rf"\s+(?:(?:not|never)\s+to|to\s+(?:not|never))\s+(?:ever\s+)?{_KEEP}\b"
_DONT_KEEP = re.compile(
    rf"{_OPENS}(?:{_NOT}|no\s+need\s+to)\s+(?:ever\s+)?{_KEEP}\b"
    rf"|{_LOOSE}{_NOT}\s+(?:ever\s+)?{_KEEP}\b(?={_MESSAGE})|{_OPENS}remember{_NOT_TO_KEEP}"
    r"|\byou\s+(?:didn['\u2019]?t|did\s+not|wouldn['\u2019]?t|would\s+not"
    rf"|(?:don['\u2019]?t|do\s+not)\s+(?:need|have)\s+to)\s+{_KEEP}\b"
    rf"|\b(?:don['\u2019]?t|do\s+not)\s+want\s+you\s+to\s+{_KEEP}\b",
    re.IGNORECASE,
)
# "Keep it nowhere" asks not to keep; "keep it nowhere near the kids" names a place.
_KEEP_NOWHERE = re.compile(
    rf"{_OPENS}(?:save|store|keep|record|note|write|put)\s+(?:(?:it|this|that|them|these|those)\s+)?"
    r"(?:down\s+)?(?:to\s+)?nowhere\b(?!\s+near\b)",
    re.IGNORECASE,
)
_NOT_FOR_MEMORY = re.compile(
    r"\bnot\s+(?:for|in|into|to)\s+your\s+(?:memory|memories|notes)\b|\boff\s+the\s+record\b",
    re.IGNORECASE,
)
# "I'll tell you later whether to save it" puts off the decision, so nothing is kept until then.
_LATER_DECISION = re.compile(
    r"\b(?:I(?:['\u2019]ll|\s+will|['\u2019]m\s+going\s+to|\s+am\s+going\s+to)?|let\s+me)\s+"
    r"(?:\w+\s+)?(?:tell\s+you|let\s+you\s+know|decide|confirm)\b(?:\s+\w+){0,2}?\s+"
    r"(?:whether|if)\s+(?:(?:you\s+(?:should|can|may)|to|I\s+want(?:\s+you)?\s+to)\s+)?"
    rf"{_KEEP}\b",
    re.IGNORECASE,
)
# A negative imperative in French, German, Spanish or Romanian that opens a clause, so a statement
# such as "je ne retiens pas" or "el nu reține" does not match.
_OTHER_OPENS = rf"(?:^\W*|{_BREAK}|\b(?:mais|et|aber|und|doch|pero|y|dar|și|însă|bitte)\s+)"
# An idiom such as "ne garde pas rancune" or "behalt das nicht für dich" follows the negated verb,
# at most one word after it, and keeps the turn; any other object or tail withholds it.
_OTHER_END = (
    r"(?!(?:\s+[\w-]+)?\s+(?:rancune|rencor|răul|alles|contre|pour\s+(?:toi|vous)"
    r"|für\s+(?:dich|euch)|para\s+(?:ti|usted))\b)"
)
_DONT_KEEP_OTHER = re.compile(
    rf"{_OTHER_OPENS}(?:(?:ne\s+(?:l['\u2019]|le\s+|la\s+|les\s+)?|n['\u2019])"
    r"(?:retiens|retenez|note|notez|garde|gardez|enregistre|enregistrez|mémorise|mémorisez)\s+pas"
    r"|(?:ret(?:enez|iens)|not(?:e|ez)|mémoris(?:e|ez))-(?:le|la|les)\s+(?:pas|jamais)"
    r"|(?:merke?\s+(?:es\s+|das\s+|dies\s+|ihn\s+|sie\s+)?dir|merken\s+sie\s+sich)\s+"
    r"(?:\w+\s+){0,2}?nicht"
    r"|(?:speicher|speichere|notier|notiere|behalt|behalte)\s+(?:das|es|dies)\s+nicht"
    r"|nicht\s+(?:merken|speichern|notieren|behalten)"
    r"|no\s+(?:(?:me|te)\s+)?(?:lo\s+|la\s+|los\s+|las\s+)?"
    r"(?:recuerdes|guardes|anotes|apuntes|memorices)"
    rf"|nu(?:-l|-o)?\s+(?:reține|reţine|salva|nota|memora|ține\s+minte))\b{_OTHER_END}",
    re.IGNORECASE,
)
# An imperative to forget in the same four languages, at a clause start: "n'oublie pas",
# "vergiss es nicht", "nu uita" and "uită-te" (look) do not match.
_FORGET_OTHER = re.compile(
    rf"{_OTHER_OPENS}(?:(?:oubli|effac)(?:e|ez)(?!\s+(?:pas|jamais)\b)"
    r"|(?:vergiss|vergessen\s+sie|l(?:ö|oe|o)sch(?:e|en\s+sie)?)"
    r"(?![^,.;:!?]*\b(?:nicht|nie|niemals)\b)"
    r"|(?:olvid|borr)(?:a|e|ad)|olv[ií]da(?:lo|la|los|las|te)|b[oó]rra(?:lo|la|los|las)"
    r"|uit[ăa](?!-te\b)|uita[țţ]i|[șşs]terge(?:[țţ]i)?)\b",
    re.IGNORECASE,
)
# An imperative to remember in the same four languages, at a clause start: "je me souviens",
# "rappelle-moi" and "recuérdale" (a reminder) and "merk dir das nicht" do not match.
_REMEMBER_OTHER = re.compile(
    rf"{_OTHER_OPENS}(?:souviens[-\s]toi|souvenez[-\s]vous|rappelle[-\s]toi|rappelez[-\s]vous"
    r"|ret(?:enez|iens)\s+(?:que|qu['\u2019]|bien|ceci|cela|ça|mon|ma|mes)\b|retiens\s*:"
    r"|(?:ret(?:enez|iens)|not(?:e|ez)|mémoris(?:e|ez))-(?:le|la|les)\b(?!\s+(?:pas|jamais)\b)"
    r"|n['\u2019]oubli(?:e|ez)\s+pas\s+(?:que|qu['\u2019])"
    r"|(?:merke?\s+(?:es\s+|das\s+|dies\s+|ihn\s+|sie\s+)?dir|merken\s+sie\s+sich)\b"
    r"(?!\s+(?:\w+\s+){0,2}?nicht\b)|erinnere?\s+dich|vergiss\s+nicht\W+dass"
    r"|recuerd[ae]\s+(?:que|esto|eso|lo\s+siguiente)\b|recuerd[ae]\s*:|acu[eé]rdate\b"
    r"|no\s+olvides\s+que|ten\s+en\s+cuenta|(?:recu[eé]rd|ap[uú]nt|an[oó]t)a(?:lo|la|los|las)\b"
    r"|[țţt]ine\s+minte|aminte[șşs]te-[țţt]i|re[țţt]ine\s+(?:c[ăa]|asta|acest)\b"
    r"|nu\s+uita\s+c[ăa])",
    re.IGNORECASE,
)
_FORGET_VERB = r"(?:forget|erase|unlearn)"
_FORGET = re.compile(
    rf"{_OPENS}{_FORGET_VERB}\b|{_LOOSE}{_FORGET_VERB}\b(?={_MESSAGE})"
    rf"|\b(?:can|could|would|will)\s+you\s+(?:please\s+)?{_FORGET_VERB}\b"
    rf"|\byou\s+to\s+{_FORGET_VERB}\b"
    rf"|{_OPENS}(?:remember\s+(?:that\s+)?)?you\s+(?:should|must|need\s+to|have\s+to)\s+"
    rf"{_FORGET_VERB}\b(?={_MESSAGE})",
    re.IGNORECASE,
)
# "drop it" must end its clause, since "drop it off at the post office" asks nothing of memory.
_DISCARD = re.compile(
    rf"(?:{_OPENS}|{_LOOSE})(?:get\s+rid\s+of\b(?={_MESSAGE})"
    rf"|stop\s+(?:remembering|saving|storing|keeping|noting)\b(?={_MESSAGE})"
    r"|drop(?=\s+(?:it|this|that|them)\s*(?:[,;.!?]|$)))",
    re.IGNORECASE,
)
_REMOVE = re.compile(
    r"\b(?:delete|erase|remove|wipe|drop|clear|purge)\b.*"
    r"\bfrom\s+(?:your\s+(?:memory|memories|notes)|what\s+you\s+(?:know|remember))\b",
    re.IGNORECASE,
)
# "Keep it in mind for him" keeps a fact for someone else, and "keep him in mind" weighs a person.
_REMEMBER = re.compile(
    rf"{_OPENS}(?:remember(?!{_NOT_TO_KEEP}{_MESSAGE})"
    r"|keep\s+(?:(?:it|this|that|these)\s+)?in\s+mind(?!\s+for\s+(?:him|her|them)\b)"
    rf"|{_NOT}\s+forget"
    r"|note(?=\s+(?:that|this|these|those|it|my|mine|down)\b))\b",
    re.IGNORECASE,
)
# A second clause or sentence can ask for a tool in words the reminder and sound readers miss.
# A comma before a digit and a closing thanks open none.
_SECOND_CLAUSE = re.compile(
    r";|,(?!\d)|[.!?]\s+\S|\b(?:and|et|mais|puis|alors|donc|ou|und|aber|dann|oder|also|pero|luego"
    r"|entonces|(?<!\bil\s)(?<!['\u2019])y|și|şi|si|dar|apoi|sau|iar|deci)\b",
    re.IGNORECASE,
)
_THANKS = re.compile(
    r"[\s,.;!¡]*\b(?:merci(?:\s+beaucoup)?|danke(?:\s+sch(?:ö|oe|o)n)?|vielen\s+dank"
    r"|(?:muchas\s+)?gracias|mul[țţt]umesc(?:\s+frumos)?|mersi)\W*$",
    re.IGNORECASE,
)
# A clause opening with a verb and its object or a time asks for an action ("and give me a shout
# at 9", "and ring at 9"), which no list of reminder or sound words can name. The first word is
# no subject or linking word, a time follows no day word, and a year is no time.
_DAY = (
    r"(?:today|tonight|tomorrow|yesterday|daily|weekly|monthly|yearly|once|twice|every|each|next"
    r"|last|(?:mon|tues|wednes|thurs|fri|satur|sun)days?)"
)
# A time can also come first, after at most two day words: "and tomorrow at 9 ring me".
_TIME_FIRST = (
    rf"(?:(?:(?:{_DAY}|day|morning|afternoon|evening|night)\s+){{0,2}}"
    r"(?:in\s+\d+\s+(?:minutes?|mins?|hours?)"
    r"|(?:at|around|by|before)\s+(?!(?:19|20)\d\d\b)\d[\d:.]*(?:\s*[ap]m)?)\s+)?"
)
_ACTION = re.compile(
    r"(?:^\W*|[,;:]\s*|\b(?:and|so|then|but|plus)\s+)(?:(?:please|also|just|then|now)\s+)*"
    rf"{_TIME_FIRST}"
    r"(?!(?:i|we|you|he|she|it|they|my|our|your|his|her|their|its|the|a|an|this|that|these|those"
    r"|there|here|and|or|but|so|then|plus|yet|because|since|while|if|when|where|which|who|whose"
    r"|in|on|at|for|with|from|to|of|by|about|after|before|during|near|under|over|into|like|as"
    r"|than|until|not|only|even|all|both|half|is|are|was|were|be|been|has|have|had|do|does|did"
    r"|will|would|can|could|should|may|might|must|up|down|off|out|back)\b)"
    rf"(?!{_DAY}\s+(?:at|around|by|before|in)\s)[a-z]+\s+"
    r"(?:(?:up|down|on|off|out|over|back)\s+)?"
    r"(?:(?:(?:at|to|for|with)\s+(?:me|us)|me|us|it|this|that|them|the|my|our|a|an|some)\b"
    r"|(?:at|around|by|before|in)\s+(?!(?:19|20)\d\d\b)\d)"
    r"(?:(?!\b(?:and|so|then|but|plus)\b)[^,;:])*",
    re.IGNORECASE,
)
_THE_MESSAGE = re.compile(_MESSAGE, re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def _asks_not_kept(sentence: str) -> bool:
    """Whether ``sentence`` asks not to keep, forget or remove something it does not ask kept."""
    if _NOT_FOR_MEMORY.search(sentence) or _REMOVE.search(sentence):
        return True
    if _KEEP_NOWHERE.search(sentence) or _LATER_DECISION.search(sentence):
        return True
    if _DONT_KEEP_OTHER.search(sentence) or _FORGET_OTHER.search(sentence):
        return True
    remember = _REMEMBER.search(sentence)
    starts = len(sentence) if remember is None else remember.start()
    # The words after a request to remember are what to keep unless they name the message:
    # "never record calls" is a rule to keep, "don't save this" is not.
    return any(
        match.start() < starts or _THE_MESSAGE.match(sentence, match.end())
        for pattern in (_DONT_KEEP, _FORGET, _DISCARD)
        for match in pattern.finditer(sentence)
    )


def asks_not_kept(query: str) -> bool:
    """Whether a sentence of ``query`` asks not to keep something, or to forget or remove it."""
    return any(_asks_not_kept(sentence) for sentence in _SENTENCE_END.split(query))


def asks_kept(query: str) -> bool:
    """Whether a sentence of ``query`` asks that something be remembered."""
    return any(
        _REMEMBER.search(sentence) or _REMEMBER_OTHER.search(sentence)
        for sentence in _SENTENCE_END.split(query)
    )


def asks_kept_alone(query: str) -> bool:
    """Whether ``query`` asks to remember in English, or in another language with one clause."""
    if any(_REMEMBER.search(sentence) for sentence in _SENTENCE_END.split(query)):
        return True
    other = _REMEMBER_OTHER.search(query)
    if other is None:
        return False
    rest = _THANKS.sub("", query[other.end() :].lstrip(" ,:"))
    return _SECOND_CLAUSE.search(rest) is None


def actions_asked(query: str) -> list[str]:
    """The clauses of ``query`` beside an English request to remember that ask for an action."""
    found: list[str] = []
    for sentence in _SENTENCE_END.split(query):
        request = _REMEMBER.search(sentence)
        if request is None:
            found.extend(match.group() for match in _ACTION.finditer(sentence))
            continue
        found.extend(match.group() for match in _ACTION.finditer(sentence, 0, request.start()))
        found.extend(match.group() for match in _ACTION.finditer(sentence, request.end()))
    return found
