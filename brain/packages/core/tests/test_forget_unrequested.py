import pytest

from cortex_core import FORGET_CHOSEN_TOOL_NAME
from cortex_core.forget_open import Exchange
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
    assert forget_unrequested(query, [Exchange("", last_reply)]) == frozenset()


@pytest.mark.parametrize(
    "query",
    [
        "Can you note that Anna likes plants?",
        "What is my bike lock code?",
        "Remember that my sister is vegan.",
        "Hi. How are you?",
        "what is my bike lock code",
        "Remember my code is 4862.",
    ],
)
def test_a_message_with_no_word_that_can_retract_refuses_the_forget_tool(query: str) -> None:
    assert forget_unrequested(query) == _REFUSED


@pytest.mark.parametrize(
    "query",
    [
        "Hi",
        "Tell me a joke, then the time",
        "I live in Berlin.",
        "My name's Ana.",
        "My code is 7319?",
        "My locker code is 7319, and my pin is 1111.",
        "My PIN is 4412 (keep it nowhere).",
        "My PIN is 4412 - I keep it nowhere near the kids.",
        "My kode is verkeerd en vee dit dadelik weg.",
        "My PIN is 4412 - keep it.",
        "My code is 7319. Usun moj stary numer.",
        "My friend from the gym who lives near the big station is Ion.",
        "Mijn code is 7319.",
        "Moj kod to 7319.",
        "My to usuniemy.",
        "I asked you to zap 8426",
        "Descarta el que et vaig dir de la meva salut.",
        "Wis mijn adres.",
        "Svuota la memoria.",
        "Tira o meu numero da memoria.",
        "Glem det jeg sa om helsa mi.",
        "Unohda puhelinnumeroni.",
        "Usun moj stary numer.",
        "Wat is mijn adres?",
        "Is het mogelijk mijn adres te wissen?",
        "Czy my to usuniemy?",
        "Qual e o meu codigo?",
        "Has esborrat el meu numero?",
        "Hva er koden min?",
        "Care este codul meu de la bicicleta?",
        "Cual es mi codigo?",
        "Don't save my phone number.",
        "Store nothing about my phone.",
        "Keep my phone number out of your memory.",
        "Write down that you should forget my number.",
        "Save me a seat.",
        "Store the old one somewhere else.",
        "Don't save my PIN.",
        "Save my phone number 0721 555 019 and delete the old one.",
        "Salva il mio numero 0721 555 019.",
        "Guarda o meu número 0721 555 019.",
        "Bewaar mijn nummer 0721 555 019.",
        "Zapisz mój numer 0721 555 019.",
    ],
)
def test_a_message_neither_asking_to_remember_nor_an_english_question_keeps_the_forget_tool(
    query: str,
) -> None:
    assert forget_unrequested(query) == frozenset()


@pytest.mark.parametrize(
    "query",
    [
        "My phone is 0721 555 019.",
        "My locker code at the pool is 7319.",
        "My sister is vegan.",
        "Our wifi password is hunter2",
        "Her birthday was on May 3. My code is 7319!",
        "  My email is ana.pop@example.com.  ",
        "My phone is 0721-555-019.",
        "Save my phone number 0721 555 019.",
        "Store this: my phone is 0721 555 019.",
        "Keep my phone number 0721 555 019.",
        "Write down my phone number 0721 555 019.",
        "Memorize my phone number 0721 555 019.",
    ],
)
def test_an_english_statement_of_a_fact_refuses_the_forget_tool(query: str) -> None:
    assert forget_unrequested(query) == _REFUSED


_WHICH_PHONE = "Which one, the mobile or the landline?"
_ANYTHING = "Got it. Anything else I can help with?"


@pytest.mark.parametrize(
    ("query", "earlier"),
    [
        (
            "My locker code is 4242.",
            [Exchange("Cancel the code I gave you.", "Which code is it?", forgot=True)],
        ),
        (
            "My locker code is 4242.",
            [Exchange("Cancel the code I gave you.", "Which code should I forget?")],
        ),
        (
            "My alarm code is 5528.",
            [
                Exchange("The alarm one.", "Which is it?"),
                Exchange("Cancel my code.", "Which code should I delete?"),
            ],
        ),
        (
            "My mobile is 0721 555 019.",
            [Exchange("The mobile one.", _WHICH_PHONE), Exchange("Forget my phone.", "Which one?")],
        ),
        (
            "My PIN is 4412.",
            [Exchange("Die für die Bank.", "Welche?"), Exchange("Vergiss meine PIN.", "Welche?")],
        ),
        (
            "Remember that my PIN is 4412.",
            [Exchange("Delete my PIN from your memory.", "Which one?")],
        ),
        ("What is my bike lock code?", [Exchange("The bike.", "Done.", forgot=True)]),
    ],
)
def test_a_message_after_an_exchange_that_opened_a_forget_keeps_the_forget_tool(
    query: str, earlier: list[Exchange]
) -> None:
    assert forget_unrequested(query, earlier) == frozenset()


@pytest.mark.parametrize(
    "ask",
    [
        "Don't forget my dentist on Friday.",
        "I forgot my keys.",
        "Remember to buy milk.",
        "I'm not sure yet.",
        "No, that's fine.",
        "I used to live in Berlin.",
        "I'm at the café.",
        "Can you update my calendar?",
        "What did I tell you earlier?",
        "Plese forgt my PIN.",
        "Look at this.",
    ],
)
@pytest.mark.parametrize(
    "query", ["My alarm code is 5528.", "Remember that my alarm code is 5528."]
)
def test_a_message_after_exchanges_that_opened_no_forget_refuses_the_forget_tool(
    query: str, ask: str
) -> None:
    earlier = [Exchange(ask, _ANYTHING), Exchange("Hello.", "Hi! How can I help?")]
    assert forget_unrequested(query, earlier) == _REFUSED


@pytest.mark.parametrize(
    ("query", "earlier"),
    [
        ("My alarm code is 5528.", [Exchange("", "Got it. How was your day?")]),
        (
            "My locker code at the pool is 7319.",
            [
                Exchange(
                    "Hi! How are you today?",
                    "I'm doing well, thank you for asking! How can I help you today?",
                )
            ],
        ),
        ("My mobile is 0721 555 019.", [Exchange("The mobile one.", _WHICH_PHONE)]),
        ("My locker code is 4242.", [Exchange("Cancel the code I gave you.", "Which code is it?")]),
        (
            "My work phone is 0744 111 222.",
            [Exchange("Get my phone number out of there.", "Which one, work or personal?")],
        ),
    ],
)
def test_a_statement_after_exchanges_that_did_nothing_about_forgetting_refuses_the_tool(
    query: str, earlier: list[Exchange]
) -> None:
    assert forget_unrequested(query, earlier) == _REFUSED


@pytest.mark.parametrize(
    ("query", "last_reply"),
    [
        ("My locker code is 7319, forget the old one.", ""),
        ("My old locker code was 7319.", ""),
        ("My locker code is no longer 7319.", ""),
        ("My biggest regret is that I forgot her birthday.", ""),
        ("My café is Brühl.", ""),
        ("My code is 7319.", "Should I forget your old code?"),
    ],
)
def test_an_english_statement_naming_a_retracting_word_keeps_the_forget_tool(
    query: str, last_reply: str
) -> None:
    assert forget_unrequested(query, [Exchange("", last_reply)]) == frozenset()


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
        "Peux-tu noter qu'Anna préfère les plantes ?",
        "Wie lautet mein Fahrradschloss-Code für das Rad?",
        "¿Cuál es mi código?",
        "Care este codul meu de la bicicletă?",
        "Remember that my favourite café is Brühl.",
        "Je veux que tu te souviennes que mon vélo est bleu.",
    ],
)
def test_a_letter_outside_english_or_a_word_that_can_retract_keeps_the_forget_tool(
    query: str,
) -> None:
    assert forget_unrequested(query) == frozenset()


@pytest.mark.parametrize(
    "query",
    [
        "Souviens-toi que le code de mon casier à la piscine est 7731.",
        "Recuerda que mi color favorito es el verde.",
        "Ține minte că numărul apartamentului meu este 42.",
        "Reține că mașina mea este o Dacia albastră.",
        "Merci. Souviens-toi que mon vélo est bleu.",
    ],
)
def test_a_request_to_remember_in_a_read_language_refuses_the_forget_tool(query: str) -> None:
    assert forget_unrequested(query) == _REFUSED


@pytest.mark.parametrize(
    "query",
    [
        "Merke dir, meine Telefonnummer ist 0721 555 019.",
        "Merke dir meine Nummer ist 0721.",
        "Merken Sie sich, unsere Nummer war 0721 555 019!",
        "Souviens-toi, mon code est 4242.",
        "Souviens-toi : mon numéro de téléphone est 0721 555 019.",
        "Recuerda: mi código es 4242.",
        "Acuérdate, mi coche está en la plaza 12.",
        "Ține minte, numărul meu de telefon este 0721 555 019.",
        "Ține minte, codul meu e 4242.  ",
        "Recuerda, mi código es 4242.",
        "Retiens, mon code est 4242.",
        "Reține, codul meu e 4242.",
        "Merke dir, der Code ist 4242.",
        "Merke dir, meine Nummer ist 0721, danke.",
    ],
)
def test_a_request_to_remember_a_statement_in_a_read_language_refuses_the_forget_tool(
    query: str,
) -> None:
    assert forget_unrequested(query) == _REFUSED


@pytest.mark.parametrize(
    "query",
    [
        "Merke dir das nicht, vergiss meine Nummer.",
        "Recuerda, borra mi código.",
        "Merke dir, wirf meinen Code weg.",
        "Merk dir, meine Nummer: 0721.",
        "Merke dir, meine Nummer ist nicht 0721.",
        "Recuerda: mi código ya no es 4242.",
        "Souviens-toi, mon ancien code était 4242.",
        "Ține minte, numărul meu vechi era 42.",
        "Souviens-toi, mon code est 4242 et jette 1111.",
        "Merke dir, meine Nummer ist 0721 555 019 und meine PIN 1111.",
        "Merke dir, meine Nummer ist 0721. Lösch die alte.",
        "Merke dir, mein Code ist 4242 (oder 4243).",
        "Merke dir, mein Code ist 4242 wirf den alten Zettel weg.",
        "Ricorda, il mio codice è 4242.",
        "Onthoud, mijn code is 4242.",
        "Lembra, o meu código é 4242.",
        "Zapamiętaj, mój kod to 4242.",
        "Retiens, oublie mon code.",
        "Merk dir, vergiss meinen Code.",
        "Reține, șterge codul meu.",
    ],
)
def test_a_request_to_remember_beside_no_whole_statement_keeps_the_forget_tool(
    query: str,
) -> None:
    assert forget_unrequested(query) == frozenset()


@pytest.mark.parametrize(
    "query",
    [
        "Recuerda que debes tirar mi código.",
        "Recuerda que tienes que desechar mi código.",
        "Recuerda que hay que tirar mi código.",
        "Ține minte că trebuie să arunci codul meu.",
        "Ține minte că vreau să arunci codul.",
        "Ține minte că trebuie să plec la 9.",
        "Souviens-toi que tu dois jeter mes données de santé.",
        "Souviens-toi que je veux que tu jettes mon code.",
        "Souviens-toi qu'il faut jeter mon code.",
        "Retenez que vous devez jeter mon code.",
        "Merk dir, dass du meinen Code wegwerfen sollst.",
        "Merk dir, dass du meinen Code wegwerfen musst.",
        "Recuerda que remuevas mi código.",
        "Recuerda que tires mi código.",
        "Recuerda que borres mi código.",
        "Souviens-toi que tu jettes mon code.",
        "Merk dir, dass du meinen Code wegwirfst.",
        "Tine minte ca vreau sa arunci codul.",
    ],
)
def test_a_request_to_remember_an_obligation_or_a_request_of_you_keeps_the_forget_tool(
    query: str,
) -> None:
    assert forget_unrequested(query) == frozenset()


@pytest.mark.parametrize(
    "query",
    [
        "Recuerda que las llaves están en el coche.",
        "Souviens-toi que sa voiture est rouge.",
        "Merk dir, dass meine Schwester Vegetarierin ist.",
    ],
)
def test_a_request_to_remember_a_fact_stated_with_a_copula_refuses_the_forget_tool(
    query: str,
) -> None:
    assert forget_unrequested(query) == _REFUSED


@pytest.mark.parametrize(
    "query",
    [
        "Ține minte să arunci codul.",
        "Ține minte să cumperi pâine.",
        "Merk dir, den Code wegzuwerfen.",
        "Merk dir: weg mit meinem alten Code.",
        "Souviens-toi : jette mon code.",
        "Souviens-toi de jeter mon code.",
        "Retiens mon code et jette l'ancien.",
        "Jette mon code. Souviens-toi que mon vélo est bleu.",
        "Souviens-toi que mon vélo est bleu. Jette mon code.",
        "Souviens-toi que ma sœur s'appelle Claire et rappelle-moi demain à 18h de l'appeler.",
        "Merk dir, dass das Treffen am Montag stattfindet und mein anderer Hund Rex heißt.",
        "Recuerda que mi código del gimnasio es 4242, quizá lo necesite.",
        "Recuerda que tienes cita a las 9.",
        "Recuerda que debo llamar a mi madre.",
        "Souviens-toi que je dois partir à 9 h.",
        "Merk dir, dass ich morgen arbeiten muss.",
        "Ține minte că sora mea vine mâine.",
        "Merk dir, dass mein Hund Bello heißt.",
        "Merk dir, dass ich den Code weggeworfen habe.",
        "Ține minte că am aruncat codul.",
        "Souviens-toi que j'ai jeté mon vieux code.",
        "Recuerda que tiré mi código.",
    ],
)
def test_a_request_to_remember_that_states_no_fact_with_a_copula_alone_keeps_the_tool(
    query: str,
) -> None:
    assert forget_unrequested(query) == frozenset()


@pytest.mark.parametrize(
    "query",
    [
        "Dimentica il mio numero di telefono.",
        "Cancella il mio indirizzo di casa.",
        "Via il mio vecchio numero, è sbagliato.",
        "Il numero che ti ho dato è sbagliato: è 4862.",
        "Il mio indirizzo adesso è Via Roma 5.",
        "Quello che ti ho detto ieri è falso.",
        "Aggiorna il mio indirizzo: è Via Roma 5.",
        "Togli dalla memoria quello che ho detto della palestra, è privato.",
        "Butta via la nota sulla palestra, è vecchia.",
        "Lascia perdere quello che ho detto: è una cosa privata.",
        "Svuota la memoria, è tutto privato.",
        "Sostituisci il mio numero: è 555 1234.",
        "Tira o meu número da memória.",
        "Limpa a memória sobre a academia.",
        "Mudei de número: agora é 555 1234.",
        "Troquei de senha, a nova é 4862.",
        "Atualiza o meu número: é 555 1234.",
        "O meu endereço está errado, é Rua Augusta 5.",
        "Deixa pra lá o que eu disse sobre a academia.",
        "Joga fora o que eu disse sobre a minha saúde.",
        "Descarta a nota da academia, é privada.",
        "Esquece o meu número de telefone.",
        "Treu el meu número de la memòria.",
        "He canviat de número: ara és el 555 1234.",
        "Llença el que et vaig dir del gimnàs.",
        "Actualitza la meva adreça: és el carrer Major 5.",
        "Canvia el meu número per 555 1234.",
        "Esborra la meva adreça.",
        "Treu la nota del gimnàs, és privada.",
        "Wis wat ik zei over België.",
        "Gooi mijn oude adres weg, ik ben naar België verhuisd.",
        "Haal mijn adres uit je geheugen.",
        "Mijn code is veranderd, het is nu 4862 voor de reünie.",
        "Vergeet mijn telefoonnummer.",
        "Wis de notitie over de reünie.",
        "Weg met mijn oude ideeën over het café.",
        "Glöm bort det jag sa om gymmet.",
        "Ta bort det jag sa om min hälsa.",
        "Unohda mitä sanoin kuntosalista, se on yksityistä ja vähän noloa.",
        "Poista muistista se mitä kerroin terveydestäni.",
        "Glem det jeg sa om helsa mi, det er privat og sårt.",
        "Zapomnij mój stary numer.",
        "Ricorda che il mio caffè preferito è l'espresso.",
        "Lembra que o meu café favorito é o expresso.",
        "Recorda que el meu cafè preferit és el tallat.",
        "Onthoud dat mijn favoriete café in België ligt.",
    ],
)
def test_a_message_in_a_language_the_lists_do_not_read_keeps_the_forget_tool(query: str) -> None:
    assert forget_unrequested(query) == frozenset()


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
        "Streich die Notiz über Jürgen.",
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
        "Te rog sa scoti codul.",
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
        "Souviens-toi que j'ai oublié mon parapluie chez Hélène.",
        "Merk dir die neue Adresse und streich die alte.",
        "Merk dir, dass ich die Nummer für Jürgen geändert habe.",
        "Recuerda que tengo un número nuevo y quita el de antes.",
        "Ține minte numărul nou și scoate-l pe cel vechi.",
        "Amintește-ți să uiți codul meu de la sală.",
        "Ține minte să uiți codul meu.",
        "Ține minte să scoți codul meu din listă.",
        "Ține minte că mereu uiți cheile.",
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
    assert forget_unrequested("What about my address?", [Exchange("", last_reply)]) == frozenset()


def test_a_message_after_a_reply_that_names_no_forgetting_refuses_the_forget_tool() -> None:
    reply = [Exchange("", "Your code is 4862.")]
    assert forget_unrequested("What about my address?", reply) == _REFUSED


@pytest.mark.parametrize(
    "query",
    [
        "Can you forgt my phone number?",
        "Can you frget my phone number?",
        "Can you foget my phone number?",
        "Can you fogret my phone number?",
        "Can you delte my phone number?",
        "Can you delet my phone number?",
        "CAN YOU ERSE MY ADDRESS?",
        "Can you take my address out of memory?",
        "Can you bin that note?",
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
        ("What about my email?", "Done. I no longer have your phone number."),
        ("What about my email?", "Done, your phone number is gone."),
        ("What about the address?", "I won't remember your phone number anymore."),
    ],
)
def test_a_message_after_a_reply_with_a_retracting_word_keeps_the_forget_tool(
    query: str, last_reply: str
) -> None:
    assert forget_unrequested(query, [Exchange("", last_reply)]) == frozenset()


def test_an_answer_to_a_question_about_an_earlier_forget_keeps_the_forget_tool() -> None:
    reply = "You have two numbers stored, 0712 and 0713. Which one do you mean?"
    query = "What about the first one?"
    earlier = [Exchange("Forget my phone number.", reply)]
    assert forget_unrequested(query, earlier) == frozenset()


@pytest.mark.parametrize(
    "earlier", ["Vreau să uiți codul.", "Vreau să scoți codul.", "Vreau sa scoti codul."]
)
def test_an_answer_after_a_romanian_forget_in_the_second_person_keeps_the_forget_tool(
    earlier: str,
) -> None:
    exchanges = [Exchange(earlier, "Care cod?")]
    assert forget_unrequested("Cel de la bicicleta.", exchanges) == frozenset()


def test_an_answer_to_a_question_about_an_earlier_message_with_no_forget_refuses() -> None:
    reply = "You have two numbers stored, 0712 and 0713. Which one do you mean?"
    query = "What about the first one?"
    earlier = [Exchange("What is my phone number?", reply)]
    assert forget_unrequested(query, earlier) == _REFUSED


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
    assert forget_unrequested(query, [Exchange("", last_reply)]) == _REFUSED


@pytest.mark.parametrize("earlier", ["Remember to buy milk.", "I used to live in Bonn."])
def test_an_earlier_message_with_no_forget_still_refuses_the_forget_tool(earlier: str) -> None:
    exchanges = [Exchange(earlier, "Noted.")]
    assert forget_unrequested("What is my bike lock code?", exchanges) == _REFUSED
