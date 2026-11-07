import pytest

from cortex_core.memory_request import asks_kept, asks_not_kept


@pytest.mark.parametrize(
    "query",
    [
        "Mon code PIN de la banque est 9911, mais ne le retiens pas.",
        "Ne note pas ça, s'il te plaît.",
        "Mein Garagencode ist 4402, aber merk dir das nicht.",
        "Merk es dir nicht.",
        "Speicher das nicht.",
        "Bitte nicht speichern: mein PIN ist 1234.",
        "Mi PIN es 1234, pero no lo guardes.",
        "No recuerdes esto.",
        "Codul meu este 7788, dar nu-l reține.",
        "Nu salva asta.",
    ],
)
def test_a_request_not_to_keep_in_french_german_spanish_or_romanian_asks_not_kept(
    query: str,
) -> None:
    assert asks_not_kept(query)


@pytest.mark.parametrize(
    "query",
    [
        "Je ne retiens pas les noms facilement.",
        "Il ne note pas ses rendez-vous.",
        "Ich kann mir das nicht merken.",
        "Ich speichere das nicht auf dem Handy.",
        "Merk dir, dass mein Hund Bello heißt.",
        "Merk dir: nicht vergessen, den Müll rauszubringen.",
        "No recuerdo su nombre.",
        "Mi hermano no lo guarda nunca.",
        "El nu reține nimic.",
        "Nu rețin numele ușor.",
        "Souviens-toi que le code de mon casier est 7731.",
    ],
)
def test_a_statement_with_the_same_verb_does_not_ask_not_kept(query: str) -> None:
    assert not asks_not_kept(query)


def test_a_request_not_to_keep_in_another_language_is_not_read_as_a_request_to_keep() -> None:
    assert not asks_kept("Mein Garagencode ist 4402, aber merk dir das nicht.")
