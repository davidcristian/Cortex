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
        "Peux-tu noter qu'Anna préfère les plantes ?",
        "Wie lautet mein Fahrradschloss-Code für das Rad?",
        "¿Cuál es mi código?",
        "Care este codul meu de la bicicletă?",
        "I don't need that",
        "Scrap it",
    ],
)
def test_a_letter_outside_english_or_a_word_that_can_retract_keeps_the_forget_tool(
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
