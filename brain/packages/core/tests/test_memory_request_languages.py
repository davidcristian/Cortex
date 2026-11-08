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
        "N'enregistre pas ça.",
        "Mon code est 7731, mais n\u2019enregistrez pas ce numéro.",
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
        "Je n'enregistre pas les appels.",
        "Il n'enregistre rien.",
        "Mon téléphone n'enregistre pas les appels.",
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


@pytest.mark.parametrize(
    "query",
    [
        "Ne garde pas rancune à Paul, il a déménagé à Lyon.",
        "Ne le retiens pas contre moi, mais mon nouveau numéro est 0176 5550 1234.",
        "Ne le garde pas pour toi, dis-le à ta sœur.",
        "Ne garde pas ça pour toi.",
        "Behalt das nicht für dich, mein neuer Job beginnt am 1. Dezember.",
        "No guardes rencor, mi jefe se llama Luis.",
        "No lo guardes para ti: mi hermana se casa el 12 de mayo.",
        "Nu ține minte răul, fratele meu se mută la Cluj.",
        "Merk dir nicht alles, aber merk dir, dass mein Code 4512 ist.",
    ],
)
def test_an_idiom_with_a_keep_verb_in_another_language_does_not_ask_not_kept(query: str) -> None:
    assert not asks_not_kept(query)


@pytest.mark.parametrize(
    "query",
    [
        "Ne garde pas ça en mémoire.",
        "Ne retiens pas mon numéro.",
        "Merk dir das nicht, bitte.",
        "No guardes mi número, por favor.",
        "No recuerdes esto por favor.",
        "Nu salva numărul meu.",
        "Nu ține minte asta, te rog.",
        "Ne retiens pas cette information : le code de mon casier est 7731.",
        "Ne garde pas ce numéro, stp.",
        "Ne note pas ce code, merci.",
        "Ne retiens pas ça stp",
        "Speichere das nicht ab.",
        "No guardes este número, porfa: mi taquilla es la 7731.",
        "No guardes esto nunca.",
        "Nu salva numărul ăsta.",
        "Nu reține asta niciodată.",
    ],
)
def test_a_request_not_to_keep_in_another_language_asks_not_kept(query: str) -> None:
    assert asks_not_kept(query)


@pytest.mark.parametrize(
    "query",
    [
        "Oublie le code de mon casier 7731.",
        "Efface mon code 7731 de ta mémoire.",
        "Mon code est 7731, mais oublie-le.",
        "Oubliez mon adresse, s'il vous plaît.",
        "Merci pour la recette. Oublie mon code 7731.",
        "Vergiss meinen Code 4402.",
        "Bitte vergiss das.",
        "Vergessen Sie meine Nummer.",
        "Lösche meinen Code 4402.",
        "Olvida mi PIN 1234.",
        "Pero olvida mi PIN.",
        "Olvídalo, mi PIN es 1234.",
        "Borra mi número 612345678.",
        "Uită codul meu 7788.",
        "Uita codul meu 7788.",
        "Șterge codul meu 7788.",
        "Sterge codul meu 7788.",
    ],
)
def test_a_request_to_forget_in_another_language_asks_not_kept(query: str) -> None:
    assert asks_not_kept(query)


@pytest.mark.parametrize(
    "query",
    [
        "J'oublie toujours mes clés.",
        "J'ai oublié mon code.",
        "Tu as oublié ?",
        "N'oublie pas d'acheter du pain.",
        "Oublie pas d'acheter du pain.",
        "Je n'efface jamais mes messages.",
        "Ich vergesse das immer.",
        "Ich vergesse oft meine Schlüssel.",
        "Vergiss nicht, den Müll rauszubringen.",
        "Vergiss es nicht.",
        "Vergiss den Termin nicht.",
        "Vergiss nie, dass ich Vegetarier bin.",
        "Lösch das nicht.",
        "Se me olvidó la contraseña.",
        "Olvidé mi PIN.",
        "Siempre olvido mis llaves.",
        "No olvides llamar a tu madre.",
        "Ella siempre borra sus mensajes.",
        "Am uitat codul.",
        "Nu uita să cumperi pâine.",
        "Uită-te la asta.",
        "Ți-ai uitat cheile?",
        "El șterge mereu mesajele.",
    ],
)
def test_a_statement_question_or_reminder_with_a_forget_verb_does_not_ask_not_kept(
    query: str,
) -> None:
    assert not asks_not_kept(query)


def test_a_request_to_remember_after_an_idiom_in_another_language_asks_kept() -> None:
    assert asks_kept("Merk dir nicht alles, aber merk dir, dass mein Code 4512 ist.")
