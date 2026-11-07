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


@pytest.mark.parametrize(
    "query",
    [
        "Souviens-toi que le code de mon casier à la piscine est 7731.",
        "Rappelle-toi que ma sœur s'appelle Claire.",
        "Retiens que mon train part à 8 h.",
        "N'oublie pas que mon vol est mardi.",
        "Mais souvenez-vous que je suis végétarien.",
        "Merk dir, dass mein Hund Bello heißt.",
        "Merken Sie sich, dass ich Vegetarier bin.",
        "Vergiss nicht, dass mein Flug am Dienstag ist.",
        "Bitte merk dir meinen Code 4512.",
        "Recuerda que mi color favorito es el verde.",
        "Acuérdate de que mi vuelo es el martes.",
        "No olvides que soy vegetariano.",
        "Ten en cuenta que trabajo de noche.",
        "Ține minte că numărul apartamentului meu este 42.",
        "Tine minte ca numarul meu este 42.",
        "Amintește-ți că sora mea se numește Ana.",
        "Nu uita că zborul meu e marți.",
    ],
)
def test_a_request_to_remember_in_french_german_spanish_or_romanian_asks_kept(
    query: str,
) -> None:
    assert asks_kept(query)


@pytest.mark.parametrize(
    "query",
    [
        "Je me souviens de lui.",
        "Il retient tout.",
        "Je me suis souvenu de son anniversaire.",
        "Tu te souviens de mon code ?",
        "Te souviens-tu quand on est allés à Paris ?",
        "Rappelle-moi demain d'appeler ma sœur.",
        "N'oublie pas d'acheter du pain.",
        "Ne retiens pas ça.",
        "Ich merke mir Namen schlecht.",
        "Er hat sich das gemerkt.",
        "Erinnerst du dich an meinen Code?",
        "Erinnere mich morgen um 9 an den Zahnarzt.",
        "Merk dir das nicht.",
        "Vergiss nicht, den Müll rauszubringen.",
        "Recuerdo que me llamaste.",
        "Ella recuerda todo.",
        "¿Recuerdas mi código?",
        "¿Te acuerdas cuando fuimos a Madrid?",
        "Recuérdame pagar el alquiler mañana.",
        "No recuerdes esto.",
        "No olvides llamar a tu madre.",
        "Îmi amintesc că m-ai sunat.",
        "El ține minte totul.",
        "Nu țin minte numele.",
        "Îți amintești când am fost la mare?",
        "Amintește-mi mâine să sun la bancă.",
        "Nu ține minte asta.",
        "Nu uita să cumperi pâine.",
    ],
)
def test_a_statement_question_or_reminder_with_a_remember_verb_does_not_ask_kept(
    query: str,
) -> None:
    assert not asks_kept(query)
