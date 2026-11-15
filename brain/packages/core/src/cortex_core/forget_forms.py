"""The words the forget card reads for each form: a row per form, a cell per language."""

LANGUAGES = ("en", "fr", "de", "es", "ro")

ALL, ONLY, ALSO, EXCEPT, ALL_BUT = "all", "only", "also", "except", "all but"
OWNER, AND, BUT, NOT, PLACE, RELATIVE = "the or my", "and", "but", "not", "on or of", "that"

# A word two languages share is written in each cell, and every reader reads a row whole.
FORMS: dict[str, tuple[str, str, str, str, str]] = {
    ALL: (
        "all every everywhere everything",
        "partout tout toute tous toutes",
        "überall alle jede jeden jedes",
        "todas",
        "",
    ),
    ONLY: ("only just", "", "", "", ""),
    ALSO: ("too also plus", "aussi également", "auch ebenfalls", "", ""),
    EXCEPT: (
        "except excluding",
        "sauf hormis excepté",
        "außer ausgenommen",
        "excepto salvo",
        "exceptând",
    ),
    ALL_BUT: ("but", "", "", "", ""),
    OWNER: (
        "the my",
        "le la les l mon ma mes",
        "der die das den mein meine meinen",
        "la",
        "",
    ),
    AND: ("and or", "et ou", "und oder", "y o", "și şi sau"),
    BUT: ("but yet", "mais", "aber", "pero", "dar"),
    NOT: ("not t never", "pas ne jamais", "nicht nie", "no nunca", "nu"),
    PLACE: (
        "on of for from in at",
        "de du sur pour dans en",
        "auf von vom für in",
        "de del en para",
        "de pe",
    ),
    RELATIVE: ("that which where", "que qu qui dont où", "", "que donde", "care"),
}

_ARTICLE = "a row the message says stays, named with its article as `dulapul` is for `dulap`"
_UNASKED = "read, it lists a row no clause asks for when another adds or keeps one"
_NO_ALL_BUT = "the word for but after a word for all does not mean except, which has its own row"
# Why a cell is empty or leaves out the plain translation of an English word.
UNREAD: dict[tuple[str, str], str] = {
    (ALL, "de"): "`alles` is a Dutch word too",
    (ALL, "es"): "`todo`, `toda` and `todos` are Portuguese words too, and `todo` an English noun",
    (ALL, "ro"): f"`toate`: read, it lists {_ARTICLE}; `tot` also means still and is Dutch",
    (ONLY, "fr"): f"`seulement`: {_UNASKED}; `juste` also means right",
    (ONLY, "de"): f"`nur`: {_UNASKED}",
    (ONLY, "es"): "`solo` also means alone and is an Italian word too",
    (ONLY, "ro"): f"`doar`: read, it lists {_ARTICLE}, or one that stays after `tot`",
    (ALSO, "es"): "`también`: read, it lists a row beside `solo`, a word for only left unread",
    (ALSO, "ro"): "`și` is the word for and, which has its own row, and `de asemenea` is two words",
    (ALL_BUT, "fr"): _NO_ALL_BUT,
    (ALL_BUT, "de"): _NO_ALL_BUT,
    (ALL_BUT, "es"): _NO_ALL_BUT,
    (ALL_BUT, "ro"): _NO_ALL_BUT,
    (OWNER, "es"): "`el`, `los`, `mi` and `mis` add a row only beside an adding word, none read",
    (OWNER, "ro"): "the article is an ending of the noun, and the word for my follows the noun",
    (RELATIVE, "de"): "the relative words are `der`, `die` and `das`, which name a row",
}


def words(form: str) -> frozenset[str]:
    """Every word of the row ``form``, over all five languages."""
    return frozenset(word for cell in FORMS[form] for word in cell.split())
