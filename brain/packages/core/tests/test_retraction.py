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
