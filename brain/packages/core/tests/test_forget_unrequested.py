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
