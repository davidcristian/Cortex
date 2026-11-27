import pytest

from cortex_core.retraction import words_to_keep


@pytest.mark.parametrize(
    ("query", "kept"),
    [
        (
            "Note that my phone number is now 0699000000, and delete the old one.",
            "Note that my phone number is now 0699000000",
        ),
        (
            "Remember that my locker code is now 8426 and forget the old one.",
            "Remember that my locker code is now 8426",
        ),
        (
            "Note that my code changed from 7319 to 8426, forget the old one.",
            "Note that my code changed from 7319 to 8426",
        ),
        (
            "Remember that my bank is Smith and Sons, and delete the old one.",
            "Remember that my bank is Smith and Sons",
        ),
        (
            "Please remember 0699000000 as my phone, then please delete the old one.",
            "Please remember 0699000000 as my phone",
        ),
        ("Remember my new pin 8426; can you delete the old one?", "Remember my new pin 8426"),
        (
            "Don't forget my new code is 8426, and delete the old one.",
            "Don't forget my new code is 8426",
        ),
        (
            "Don\u2019t forget my new code is 8426, and delete the old one.",
            "Don\u2019t forget my new code is 8426",
        ),
        (
            "Remember that I never forget a face, and erase the old code.",
            "Remember that I never forget a face",
        ),
    ],
)
def test_the_words_before_the_first_retraction_are_kept(query: str, kept: str) -> None:
    assert words_to_keep(query) == kept


@pytest.mark.parametrize(
    ("query", "kept"),
    [
        ("Forget the old number, my phone is now 0699000000.", "my phone is now 0699000000"),
        (
            "Delete the old one. Note that my phone number is now 0699000000.",
            "Note that my phone number is now 0699000000",
        ),
        (
            "Forget the old number and remember that my phone is 0699000000.",
            "remember that my phone is 0699000000",
        ),
        ("Forget 7319 and 5555, my new code is 8426.", "my new code is 8426"),
        ("Forget the old one and remember my pin is 8426", "remember my pin is 8426"),
        (
            "Please wipe the old pin, my pin is 8426, and drop the old email too.",
            "my pin is 8426",
        ),
    ],
)
def test_the_words_after_a_retraction_that_comes_first_are_kept(query: str, kept: str) -> None:
    assert words_to_keep(query) == kept


@pytest.mark.parametrize(
    "query",
    [
        "Remember that my phone is 0699000000.",
        "I always forget my keys, remember that.",
        "Forget the old one.",
        "Forget the old one",
        "Forget the old number and the old code.",
        "Remember 8426, I want you to forget 7319.",
        "Note my code is 8426, you can delete 7319, and forget the old pin.",
        "Remember that the dentist will remove my tooth, and forget the old date.",
        "Retiens que mon code est 8426 et oublie l'ancien.",
    ],
)
def test_no_words_are_kept_when_a_forget_verb_is_left_unread(query: str) -> None:
    assert words_to_keep(query) is None


@pytest.mark.parametrize(
    "query",
    [
        "Remember, delete the old one.",
        "Remember: wipe my old card and store 5500.",
        "Please remember, delete the old one.",
        "Please remember: wipe my old card and store 5500.",
        "Note that, delete the old one.",
        "Note that: wipe my old card and store 5500.",
        "Keep in mind, delete the old one.",
        "Keep in mind: wipe my old card and store 5500.",
        "Keep it in mind, and delete the old one.",
        "Don't forget, and delete the old one.",
        "Delete the old one. Remember that.",
        "Forget the old one and remember.",
    ],
)
def test_no_words_are_kept_when_nothing_follows_the_request_to_remember(query: str) -> None:
    assert words_to_keep(query) is None


@pytest.mark.parametrize(
    ("query", "kept"),
    [
        ("Remember 5500, delete the old one.", "Remember 5500"),
        ("Remember: 5500 is my card, wipe the old one.", "Remember: 5500 is my card"),
        (
            "Please remember that it is 5500, and delete the old one.",
            "Please remember that it is 5500",
        ),
        ("Remember this number 5500, and delete the old one.", "Remember this number 5500"),
        (
            "Keep this in mind: my card is 5500, and delete the old one.",
            "Keep this in mind: my card is 5500",
        ),
        (
            "Note that down: my card is 5500, wipe the old one.",
            "Note that down: my card is 5500",
        ),
        (
            "My card is 5500, remember that, and delete the old one.",
            "My card is 5500, remember that",
        ),
        ("Forget the old one, remember 5500.", "remember 5500"),
    ],
)
def test_the_words_are_kept_when_a_fact_follows_or_leads_the_request(query: str, kept: str) -> None:
    assert words_to_keep(query) == kept
