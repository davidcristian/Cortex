from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import MemoryRecord
from cortex_core.forget_unnamed import unnamed

_AT = datetime(2026, 11, 9, 6, 0, 0, tzinfo=UTC)
_ROWS = {
    "de": (
        "User: Merke dir, mein Fahrradschloss hat den Code 7319.\nAssistant: Notiert.",
        "User: Merke dir, der Schuppen hat auch den Code 7319.\nAssistant: Notiert.",
    ),
    "es": (
        "User: Recuerda que el código del candado de mi bici es 7319.\nAssistant: Anotado.",
        "User: Recuerda que el código del cobertizo también es 7319, por favor.\nAssistant: Hecho.",
    ),
    "fr": (
        "User: Retiens que le code de mon vélo est 7319.\nAssistant: Noté.",
        "User: Retiens que pour le cabanon, celui des outils, le code est 7319.\nAssistant: Noté.",
    ),
    "ro": (
        "User: Ține minte că codul de la bicicleta mea este 7319.\nAssistant: Notat.",
        "User: Ține minte că și codul care este la magazie este 7319.\nAssistant: Notat.",
    ),
    "en": (
        "User: Remember that my bike lock code is 7319.\nAssistant: Noted.",
        "User: Remember that the den TV code is also 7319.\nAssistant: Noted.",
    ),
}


def _kept(language: str, query: str) -> list[str]:
    bike, other = _ROWS[language]
    rows = [
        MemoryRecord(id=name, text=text, embedding=(1.0, 0.0), at=_AT + timedelta(minutes=i))
        for i, (name, text) in enumerate((("bike", bike), ("other", other)))
    ]
    return [record.id for record in unnamed(rows, "7319", query)]


@pytest.mark.parametrize(
    ("language", "query", "kept"),
    [
        ("de", "Vergiss den Code von meinem Fahrradschloss, 7319.", ["other"]),
        ("es", "Olvida el código del candado de mi bici, 7319, por favor.", ["other"]),
        ("fr", "Oublie celui de mon vélo, 7319.", ["other"]),
        ("fr", "Oublie le code qui est 7319 pour mon vélo.", ["other"]),
        ("ro", "Uită codul care este pentru bicicleta mea, 7319.", ["other"]),
        ("en", "Also, vergiss den bike lock Code 7319.", ["other"]),
    ],
)
def test_a_function_word_of_the_messages_language_names_no_row(
    language: str, query: str, kept: list[str]
) -> None:
    assert _kept(language, query) == kept


@pytest.mark.parametrize(
    ("language", "query", "kept"),
    [
        ("de", "Vergiss den Code vom Schuppen, 7319.", ["bike"]),
        ("de", "Vergiss den 7319.", []),
        ("es", "Olvida el del cobertizo, 7319.", ["bike"]),
        ("fr", "Oublie le code des outils, 7319.", ["bike"]),
        ("ro", "Uită codul de la magazie, 7319.", ["bike"]),
        ("en", "Forget the den code 7319.", ["bike"]),
    ],
)
def test_a_content_word_or_an_english_word_still_names_its_row(
    language: str, query: str, kept: list[str]
) -> None:
    assert _kept(language, query) == kept


@pytest.mark.parametrize(
    ("language", "query"),
    [
        ("de", "Vergiss 7319, behalte den vom Schuppen."),
        ("es", "Olvida 7319, guarda el del cobertizo."),
        ("ro", "Uită 7319, păstrează-l pe cel de la magazie."),
    ],
)
def test_a_keep_clause_beside_a_value_naming_no_fact_keeps_both_rows(
    language: str, query: str
) -> None:
    assert _kept(language, query) == ["bike", "other"]
