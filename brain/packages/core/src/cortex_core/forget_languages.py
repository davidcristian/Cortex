"""The function words and forget verbs of the languages besides English a forget is read in."""

import re

from cortex_core.note_language import message_language

_WORD = re.compile(r"[^\W\d_]{3,}")
_VERBS = {
    "fr": "oublie oubliez efface effacez supprime supprimez",
    "de": "vergiss lösche entferne",
    "es": "olvida olvide borra borre elimina",
    "ro": "uită șterge ştergeţi sterge",
}
# Read only in a message read as that language, since an English fact can be named by "den",
# "son" or "care".
_OTHERS = {
    "fr": "les des une aux dans pour par avec sur sous chez que qui quoi dont mon ton son mes "
    "tes ses notre votre nos vos leur leurs celui celle ceux celles cela ceci cet cette ces "
    "est sont était ont mais aussi non pas plus moi toi lui elle nous vous eux elles ils "
    "mémoire merci",
    "de": "der die das den dem des ein eine einen einem einer eines und oder aber für von vom "
    "mit aus bei beim zum zur auf über unter nach mein meine meinen meinem meiner meines dein "
    "deine deinen deinem deiner sein seine seinen seinem ihr ihre ihren ihrem ihrer unser "
    "unsere euer eure ist sind war hat habe haben hast auch nicht noch nur jetzt bitte ich "
    "mich mir dich dir sie ihn ihm uns euch wir was dass diese dieser dieses diesen diesem",
    "es": "los las del una uno unos unas que con por para sin sobre mis tus sus mío mía tuyo "
    "tuya suyo suya nuestro nuestra este esta esto estos estas ese esa eso esos esas también "
    "pero está son era fue tiene tengo hay favor ahora solo ella ellos ellas usted les nos "
    "memoria",
    "ro": "sau dar pentru din despre cel cea cei cele lui ale mea meu mele mei tău tale său "
    "sale nostru noastră acest această acesta aceasta aceste acel acea aceea care este sunt "
    "era are acum doar încă tine mine noi voi lor îmi mie nici rog memorie",
}
VERBS = {language: frozenset(_WORD.findall(words)) for language, words in _VERBS.items()}
FUNCTION = {
    language: frozenset(_WORD.findall(words)) | VERBS[language]
    for language, words in _OTHERS.items()
}


def readings(query: str) -> set[str]:
    """The language ``message_language`` picks for ``query`` and each whose forget verb it uses."""
    words = {word.lower() for word in _WORD.findall(query)}
    found = {language for language, verbs in VERBS.items() if not verbs.isdisjoint(words)}
    return {message_language(query), *found}
