import pytest

from cortex_core.unsaved_claim import claims_unsaved


@pytest.mark.parametrize(
    "reply",
    [
        "I couldn't find any previous memory about your sister's name, so I haven't \"saved\" it "
        "as a long-term memory.",
        "Your reminder is set for 18:00. I noticed I didn't save it.",
        "I have not stored your locker code.",
        "I've set the reminder, but your code was not saved.",
        "Your code hasn't been stored yet.",
        "I wasn't able to save that.",
        "Le rappel est prévu, mais je n'ai pas pu m'en souvenir.",
        "Je ne l'ai pas enregistré.",
        "Ich habe die Nummer nicht gespeichert.",
        "No lo he guardado todavía.",
        "Nu l-am salvat încă.",
        "Codul nu a fost reținut.",
    ],
)
def test_a_statement_that_the_fact_was_not_saved_is_read(reply: str) -> None:
    assert claims_unsaved(reply)


@pytest.mark.parametrize(
    "reply",
    [
        "I haven't set a reminder.",
        "I didn't save the file.",
        "I couldn't find a previous memory.",
        "I couldn't save the changes to notes.txt.",
        "I haven't saved the reminder yet.",
        "The folder was not saved.",
        "Do you mean I haven't saved it?",
        "I saved it.",
        "I don't remember your locker code.",
        "Je n'ai pas enregistré le fichier.",
        "Ich habe die Datei nicht gespeichert.",
        "No he guardado el archivo.",
        "Nu am salvat fișierul.",
        "No problem, I noted it.",
        "No te lo apuntes.",
        "No guardes rencor.",
        "",
    ],
)
def test_a_near_miss_is_not_read(reply: str) -> None:
    assert not claims_unsaved(reply)
