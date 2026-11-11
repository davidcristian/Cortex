import pytest

from cortex_core import ToolSpec, asks_kept
from cortex_core.unasked_tools import unasked_forget, unasked_sidecar_tools, unasked_tools

_FILES = tuple(
    ToolSpec(name=name, description="", parameters={}, sidecar=True)
    for name in ("list_allowed_directories", "read_text_file", "list_directory")
)


@pytest.mark.parametrize(
    "query",
    [
        "Can you note that Anna likes plants?",
        "Could you remember that my sister is vegan?",
        "Would you keep in mind that I'm off on Fridays?",
        "can you please note that the boiler was serviced in May?",
        "Please, could you note that Luca prefers tea?",
        "Will you remember that we moved to Leeds?",
        "Can you note that she likes plants",
    ],
)
def test_a_question_asking_to_note_a_fact_refuses_every_sidecar_tool(query: str) -> None:
    assert unasked_sidecar_tools(query, _FILES) == {spec.name for spec in _FILES}


@pytest.mark.parametrize(
    "query",
    [
        "Can you note the time?",
        "Can you note down the steps for me?",
        "Can you note down the steps in notes.txt for me?",
        "Did you note that?",
        "Can you note that?",
        "Can you note that down?",
        "Can you note that for me?",
        "Can you not note that Anna likes plants?",
        "Can't you remember that Anna likes plants?",
        "Can you never remember that Anna likes plants?",
        "Do you remember that Anna likes plants?",
        "Can you remember that restaurant we liked?",
        "Can you remember that file I sent you?",
        "Can you note that the plan is in notes.txt?",
        "Could you remember that my notes file holds the plan?",
        "Can you note that Anna likes plants? Also, what is in my folder?",
        "Can you note that Anna likes plants and read notes.txt?",
        "Can you note that what Anna likes is in the list?",
        "Can you note that Anna likes plants, then look at the docs?",
        'Anna said: "remind me at 8". Can you note that she likes plants?',
        "Can you tell me if I asked you to note that Anna likes plants?",
        "Can you note that my notes are in C:\\Users\\me\\notes?",
        "Remember that my notes are in D:\\notes.",
    ],
)
def test_a_question_that_is_no_plain_request_to_note_keeps_every_sidecar_tool(
    query: str,
) -> None:
    assert unasked_sidecar_tools(query, _FILES) == frozenset()


@pytest.mark.parametrize(
    "query",
    [
        "Can you note that Anna likes plants?",
        "Could you remember that my sister is vegan?",
    ],
)
def test_a_question_asking_to_note_a_fact_changes_no_other_reader(query: str) -> None:
    assert not asks_kept(query)
    assert unasked_tools(query) == frozenset()
    assert unasked_forget(query) == frozenset()
