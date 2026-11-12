import pytest

from cortex_core import FORGET_CHOSEN_TOOL_NAME
from cortex_core.forget_unrequested import forget_unrequested

_REFUSED = frozenset({FORGET_CHOSEN_TOOL_NAME})


@pytest.mark.parametrize(
    ("query", "last_reply"),
    [
        ("And my address too.", "I forgot your phone number."),
        ("Yes", "Should I forget it?"),
        ("Oublie mon adresse.", ""),
        ("Vergiss das.", ""),
        ("Get rid of my old number.", ""),
        ("My code is 4862, not 4826.", ""),
        ("That one is wrong.", ""),
        ("Merk es dir nicht.", ""),
        ("Ne le retiens pas.", ""),
        ("Mon code est 4862, pas 4826.", ""),
        ("Codul meu e 4862, nu 4826.", ""),
        ("Kein Code mehr.", ""),
    ],
)
def test_a_near_miss_keeps_the_forget_tool(query: str, last_reply: str) -> None:
    assert forget_unrequested(query, last_reply) == frozenset()


@pytest.mark.parametrize(
    "query",
    [
        "Can you note that Anna likes plants?",
        "What is my bike lock code?",
        "Remember that my sister is vegan.",
        "Hi. How are you?",
        "Tell me a joke, then the time",
    ],
)
def test_a_message_with_no_word_that_can_retract_refuses_the_forget_tool(query: str) -> None:
    assert forget_unrequested(query) == _REFUSED


@pytest.mark.parametrize(
    "query",
    [
        "Zapamiętaj, że mój kod to 7731.",
        "Запомни, что мой код 7731.",
        "私のコードは7731だと覚えて",
        "내 코드가 7731이라는 걸 기억해 줘",
        "Nezapomeň, že můj kód je 7731.",
        "Lembra que o meu código não é 7731.",
        "I don't need that",
        "Scrap it",
    ],
)
def test_a_letter_outside_the_read_languages_or_a_word_that_can_retract_keeps_the_forget_tool(
    query: str,
) -> None:
    assert forget_unrequested(query) == frozenset()


@pytest.mark.parametrize(
    "query",
    [
        "Peux-tu noter qu'Anna préfère les plantes ?",
        "Wie lautet mein Fahrradschloss-Code für das Rad?",
        "¿Cuál es mi código?",
        "Care este codul meu de la bicicletă?",
        "Souviens-toi que le code de mon casier à la piscine est 7731.",
        "Merk dir, dass mein Hund Bello heißt.",
        "Recuerda que mi color favorito es el verde.",
        "Ține minte că numărul apartamentului meu este 42.",
        "Souviens-toi que ma sœur s'appelle Claire et rappelle-moi demain à 18h de l'appeler.",
        "Merk dir, dass das Treffen am Montag stattfindet und mein anderer Hund Rex heißt.",
        "Recuerda que mi código del gimnasio es 4242, quizá lo necesite.",
        "Reține că mașina mea este o Dacia albastră.",
    ],
)
def test_a_request_to_remember_or_a_question_in_a_read_language_refuses_the_forget_tool(
    query: str,
) -> None:
    assert forget_unrequested(query) == _REFUSED


@pytest.mark.parametrize(
    "query",
    [
        "Efface mon code 7731 de ta mémoire.",
        "Mon code est 7731, mais oublie-le.",
        "Oublie le code de mon casier à la piscine.",
        "Oublie le code de mon vélo 7319, c'est tout.",
        "Oublie mon code de casier 7319, s'il te plaît.",
        "Retire mon code de casier.",
        "Enlève mon adresse, s'il te plaît.",
        "Supprime mon numéro de téléphone.",
        "Annule ce que je t'ai dit sur mon vélo.",
        "Sors mon code de ta mémoire.",
        "Je n'ai plus de vélo.",
        "J'ai plus de vélo.",
        "Mon code a changé, c'est 4862.",
        "Mets à jour mon code : 4862.",
        "Mon code a été modifié, c'est 4862.",
        "Mon nouveau code est 4862 au lieu de 4826.",
        "C'était une erreur, mon code est 4862.",
        "Ma sœur s'appelle Claire, pas Clara.",
        "Vergiss den Fahrradcode 7319 überall.",
        "Vergiss meinen Türcode, aber behalte die Postleitzahl.",
        "Vergiss, wie mein Hund heißt.",
        "Streich meine alte Adresse.",
        "Lösch meine Telefonnummer.",
        "Entferne den Code für das Schloss.",
        "Nimm das aus deinem Gedächtnis, bitte.",
        "Mein Code ist jetzt 4862 statt 4826.",
        "Der Code für das Schloss war falsch, er lautet 4862.",
        "Ich habe meinen Code geändert, er heißt 4862.",
        "Mein Hund heißt nicht mehr Bello.",
        "Olvida el código de la bici 7319, eso es todo.",
        "Olvídalo, por favor.",
        "Bórralo, por favor.",
        "Elimínalo de tu lista.",
        "Quítame el PIN del banco.",
        "Retíralo de la lista, gracias.",
        "Suprime mi número de teléfono.",
        "Saca mi PIN de tu memoria.",
        "Mi código ya no es 7731.",
        "Mi código cambió a 4862.",
        "Mi color favorito es el azul en lugar del verde.",
        "Ningún código sirve ya.",
        "Jamás tuve un gato.",
        "Te rog, uită codul meu 7788.",
        "Uită numărul apartamentului.",
        "Șterge codul meu de la bicicletă.",
        "Elimină numărul de telefon.",
        "Scoate-l din listă, te rog.",
        "Ia numărul din memoria ta.",
        "N-am mai bicicletă.",
        "Codul meu s-a schimbat în 4862.",
        "Codul vechi era greșit.",
        "Numărul este 43 în loc de 42.",
        "Esqueça o meu código.",
        "Şifremi sil.",
    ],
)
def test_a_request_to_forget_or_a_correction_in_another_language_keeps_the_forget_tool(
    query: str,
) -> None:
    assert forget_unrequested(query) == frozenset()


@pytest.mark.parametrize(
    "query",
    [
        "Merk dir, dass ich meinen Schlüssel vergessen habe.",
        "Souviens-toi que j'oublie toujours mon code.",
        "Recuerda que siempre olvido mis llaves en el coche.",
        "Ține minte că uit mereu cheile acasă.",
        "Souviens-toi que je n'aime pas les épinards.",
        "Merk dir, dass ich keine Nüsse esse.",
        "Recuerda que no me gusta el café.",
        "Ține minte că nu beau cafea dimineața.",
    ],
)
def test_a_request_to_remember_that_names_forgetting_or_a_negation_keeps_the_forget_tool(
    query: str,
) -> None:
    assert forget_unrequested(query) == frozenset()


@pytest.mark.parametrize(
    "last_reply",
    [
        "I deleted the row holding your code.",
        "J'ai oublié ton adresse.",
        "Ich habe es gelöscht.",
        "Lo he borrado.",
        "Am șters codul.",
        "Your number was removed.",
        "J'ai retiré ton code.",
        "Ich habe die Adresse gestrichen.",
        "He quitado tu PIN.",
        "Am scos numărul.",
    ],
)
def test_a_message_after_a_reply_that_names_forgetting_keeps_the_forget_tool(
    last_reply: str,
) -> None:
    assert forget_unrequested("And my address too.", last_reply) == frozenset()


def test_a_message_after_a_reply_that_names_no_forgetting_refuses_the_forget_tool() -> None:
    assert forget_unrequested("And my address too.", "Your code is 4862.") == _REFUSED


@pytest.mark.parametrize(
    "query",
    [
        "forgt my phone number",
        "frget my phone number",
        "foget my phone number",
        "fogret my phone number",
        "delte my phone number",
        "delet my phone number",
        "ERSE MY ADDRESS",
        "Take my address out of memory.",
        "Bin that note.",
    ],
)
def test_a_misspelled_forget_or_a_phrase_for_one_keeps_the_forget_tool(query: str) -> None:
    assert forget_unrequested(query) == frozenset()


@pytest.mark.parametrize(
    "query",
    ["Remember the delta format I renewed.", "What did I fret about at the forum?"],
)
def test_a_word_two_letters_from_a_forget_word_refuses_the_forget_tool(query: str) -> None:
    assert forget_unrequested(query) == _REFUSED


@pytest.mark.parametrize(
    ("query", "last_reply"),
    [
        ("Yes, do it.", "Do you want me to get rid of the note about your old address?"),
        ("Yes.", "Should I unlearn that?"),
        ("And my email too.", "Done. I no longer have your phone number."),
        ("And my email too.", "Done, your phone number is gone."),
        ("And the address as well.", "I won't remember your phone number anymore."),
    ],
)
def test_a_message_after_a_reply_with_a_retracting_word_keeps_the_forget_tool(
    query: str, last_reply: str
) -> None:
    assert forget_unrequested(query, last_reply) == frozenset()


def test_an_answer_to_a_question_about_an_earlier_forget_keeps_the_forget_tool() -> None:
    reply = "You have two numbers stored, 0712 and 0713. Which one do you mean?"
    assert forget_unrequested("The first one.", reply, "Forget my phone number.") == frozenset()


def test_an_answer_to_a_question_about_an_earlier_message_with_no_forget_refuses() -> None:
    reply = "You have two numbers stored, 0712 and 0713. Which one do you mean?"
    assert forget_unrequested("The first one.", reply, "What is my phone number?") == _REFUSED


@pytest.mark.parametrize(
    "last_reply",
    [
        "I don't have your bike lock code in my memory.",
        "Got it. Let me know if anything changes.",
        "I have no record of that.",
        "Your old code was 4826; I've updated it to 4862.",
        "I can't find a bike lock code in my notes.",
    ],
)
@pytest.mark.parametrize(
    "query",
    [
        "What is my bike lock code?",
        "Can you note that Anna likes plants?",
        "Remember that my wifi password is hunter22.",
    ],
)
def test_a_reply_with_a_negation_or_a_change_word_still_refuses_the_forget_tool(
    query: str, last_reply: str
) -> None:
    assert forget_unrequested(query, last_reply) == _REFUSED


@pytest.mark.parametrize("earlier", ["Remember to buy milk.", "I used to live in Bonn."])
def test_an_earlier_message_with_no_forget_still_refuses_the_forget_tool(earlier: str) -> None:
    assert forget_unrequested("What is my bike lock code?", "Noted.", earlier) == _REFUSED
