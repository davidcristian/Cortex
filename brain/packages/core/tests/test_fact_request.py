import pytest

from cortex_core.fact_request import asks_kept_fact_other, stores_fact


@pytest.mark.parametrize(
    "query",
    [
        "Save my phone number 0721 555 019.",
        "Store this: my phone is 0721 555 019.",
        "Keep my phone number 0721 555 019.",
        "Write down my phone number 0721 555 019.",
        "Memorize my phone number 0721 555 019.",
        "Please save that my code is 4242.",
        "Write this down: our wifi password is hunter2",
        "Record my email ana.pop@example.com",
    ],
)
def test_an_english_request_to_store_a_stated_value_stores_a_fact(query: str) -> None:
    assert stores_fact(query)


@pytest.mark.parametrize(
    "query",
    [
        "Don't save my phone number.",
        "Store nothing about my phone.",
        "Keep my phone number out of your memory.",
        "Write down that you should forget my number.",
        "Save me a seat.",
        "Store the old one somewhere else.",
        "Don't save my PIN.",
        "Save my phone number.",
        "Keep my phone number 0721 555 019 out of the notes you keep.",
        "Save my phone number 0721. Thanks!",
        "My phone is 0721 555 019, save it.",
        "Salva il mio numero 0721 555 019.",
        "Guarda o meu número 0721 555 019.",
        "Bewaar mijn nummer 0721 555 019.",
        "Zapisz mój numer 0721 555 019.",
    ],
)
def test_a_store_verb_with_no_stated_value_stores_no_fact(query: str) -> None:
    assert not stores_fact(query)


@pytest.mark.parametrize(
    "query",
    [
        "Souviens-toi que le code de mon casier à la piscine est 7731.",
        "Merk dir, dass meine Schwester Vegetarierin ist.",
        "Recuerda que mi color favorito es el verde.",
        "Ține minte că numărul apartamentului meu este 42.",
        "Merci. Souviens-toi que mon vélo est bleu.",
        "Recuerda que mi código es 4512, ¡muchas gracias!",
        "Merke dir, meine Telefonnummer ist 0721 555 019.",
        "Recuerda: mi código es 4512.",
        "Ține minte, codul meu e 4512.",
        "Recuerda, mi código es 4242.",
        "Retiens, mon code est 4242.",
        "Reține, codul meu e 4242.",
        "Recuerda que las llaves están en el coche.",
        "Merke dir, der Code ist 4242.",
        "Mais souvenez-vous que je suis végétarien.",
        "Merk dir, dass ich Vegetarier bin.",
        "Recuerda que soy vegetariano.",
        "Ține minte că sunt vegetarian.",
    ],
)
def test_a_request_to_remember_a_fact_stated_with_a_copula_asks_kept_fact_other(
    query: str,
) -> None:
    assert asks_kept_fact_other(query)


@pytest.mark.parametrize(
    "query",
    [
        "Recuerda que remuevas mi código.",
        "Recuerda que tires mi código.",
        "Souviens-toi que tu jettes mon code.",
        "Merk dir, dass du meinen Code wegwirfst.",
        "Tine minte ca vreau sa arunci codul.",
        "Recuerda que borres mi código.",
        "Retiens, oublie mon code.",
        "Merk dir, vergiss meinen Code.",
        "Reține, șterge codul meu.",
        "Recuerda, borra mi código.",
        "Merk dir, dass mein Hund Bello heißt.",
        "Merci. Retiens qu'Anna préfère les plantes.",
        "Merk dir, dass ich morgen arbeiten muss.",
        "Recuerda que tienes cita a las 9.",
        "Recuerda que borres lo que es mío.",
        "Ține minte că e timpul să arunci codul.",
        "Ține minte să arunci codul.",
        "Merk dir: weg mit meinem alten Code.",
        "Recuerda esto y sube el volumen.",
        "Merk dir nicht alles, aber merk dir, dass mein Code 4512 ist.",
        "Souviens-toi que mon vélo est bleu et jette mon code.",
        "Remember that my code is 4512.",
        "Merk dir, dass du meinen Code wegwerfen sollst.",
        "Recuerda que debes tirar mi código.",
        "Merke dir, wirf meinen Code weg.",
        "Souviens-toi, mon code est 4512 et jette 1111.",
        "Merke dir, meine Nummer ist 0721. Lösch die alte.",
        "Ricorda, il mio codice è 4242.",
        "Lembra, o meu código é 4242.",
        "Onthoud, mijn code is 4242.",
        "Zapamiętaj, mój kod to 4242.",
    ],
)
def test_a_request_to_remember_an_action_or_no_copula_is_not_kept_fact_other(
    query: str,
) -> None:
    assert not asks_kept_fact_other(query)
