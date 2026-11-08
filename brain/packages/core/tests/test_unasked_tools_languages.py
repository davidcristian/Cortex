import pytest

from cortex_core import SCHEDULE_TOOL_NAME, SET_VOLUME_TOOL_NAME, SPAWN_TOOL_NAME, ToolSpec
from cortex_core.unasked_tools import unasked_forget, unasked_sidecar_tools, unasked_tools

_SIDECAR = (
    ToolSpec(name="read_file", description="", parameters={}, sidecar=True),
    ToolSpec(name=SPAWN_TOOL_NAME, description="", parameters={}, calls_sidecar=True),
)
_BOTH = frozenset({SET_VOLUME_TOOL_NAME, SCHEDULE_TOOL_NAME})


@pytest.mark.parametrize(
    "query",
    [
        "Souviens-toi que le code de mon casier à la piscine est 7731.",
        "Merk dir, dass mein Hund Bello heißt.",
        "Recuerda que mi color favorito es el verde.",
        "Ține minte că numărul apartamentului meu este 42.",
    ],
)
def test_a_request_to_remember_a_fact_in_another_language_refuses_every_sidecar_tool(
    query: str,
) -> None:
    assert unasked_sidecar_tools(query, _SIDECAR) == {"read_file", SPAWN_TOOL_NAME}


@pytest.mark.parametrize(
    "query",
    [
        "Retiens bien ce qu'il y a dans le fichier de courses.",
        "Souviens-toi du contenu de mon dossier.",
        "Merk dir, was in der Datei steht.",
        "Merk dir den Inhalt meines Ordners.",
        "Recuerda esto del archivo.",
        "Recuerda esto de la carpeta.",
        "Ține minte conținutul fișierului.",
        "Tine minte atasamentul din mesajul meu.",
        "Retiens bien la pièce jointe de mon courriel.",
    ],
)
def test_a_request_to_remember_a_source_in_another_language_keeps_every_sidecar_tool(
    query: str,
) -> None:
    assert unasked_sidecar_tools(query, _SIDECAR) == frozenset()


@pytest.mark.parametrize(
    "query",
    [
        "Souviens-toi que ma sœur s'appelle Claire et rappelle-moi demain de l'appeler.",
        "Merk dir, dass Ana Geburtstag hat, und erinnere mich morgen daran.",
        "Recuerda que Ana cumple años y recuérdamelo mañana.",
        "Ține minte că Ana are ziua mâine și amintește-mi la 9.",
        "Merk dir, dass ich um 6 aufstehe, und stell den Wecker.",
    ],
)
def test_a_request_to_remember_that_asks_for_a_reminder_in_another_language_keeps_it(
    query: str,
) -> None:
    assert SCHEDULE_TOOL_NAME not in unasked_tools(query)


@pytest.mark.parametrize(
    "query",
    [
        "Souviens-toi que la musique est trop forte et baisse le volume.",
        "Merk dir das und mach die Lautstärke leiser.",
        "Recuerda esto y sube el volumen.",
        "Ține minte asta și dă volumul mai tare.",
    ],
)
def test_a_request_to_remember_that_names_the_sound_in_another_language_keeps_it(
    query: str,
) -> None:
    assert SET_VOLUME_TOOL_NAME not in unasked_tools(query)


def test_a_request_to_remember_a_fact_in_another_language_refuses_both_tools() -> None:
    assert unasked_tools("Merk dir, dass mein Hund Bello heißt.") == _BOTH


@pytest.mark.parametrize(
    "query",
    [
        "Souviens-toi que mon code est 7731.",
        "Tine minte ca i-am zis sa uiti codul vechi.",
        "Tine minte ca i-am cerut sa sterg codul.",
        "Retiens que my code est vieux, je veux le supprimer.",
        "Merk dir: my Code ist alt, bitte loschen.",
        "Recuerda que my code es viejo, quiero eliminarlo.",
    ],
)
def test_a_request_to_remember_in_another_language_keeps_the_forget_tool(query: str) -> None:
    assert unasked_forget(query) == frozenset()


@pytest.mark.parametrize(
    ("query", "tool"),
    [
        (
            "Souviens-toi que j'ai rendez-vous chez le dentiste et préviens-moi demain à 9h.",
            SCHEDULE_TOOL_NAME,
        ),
        (
            "Merk dir, dass ich morgen zum Zahnarzt muss, und sag mir um 9 Uhr Bescheid.",
            SCHEDULE_TOOL_NAME,
        ),
        ("Ține minte că mâine am dentist și anunță-mă la 9.", SCHEDULE_TOOL_NAME),
        ("Merk dir, dass ich um 6 aufstehe. Weck mich um 5.", SCHEDULE_TOOL_NAME),
        ("Ține minte că am dentist; anunță-mă la 9.", SCHEDULE_TOOL_NAME),
        ("Recuerda que me gusta así y sube la música.", SET_VOLUME_TOOL_NAME),
        ("Souviens-toi que j'aime ça et monte la musique.", SET_VOLUME_TOOL_NAME),
        ("Souviens-toi que je dors mais monte la musique.", SET_VOLUME_TOOL_NAME),
        ("Merke dir: mein Gewicht ist 72,5 kg, sag mir morgen Bescheid.", SCHEDULE_TOOL_NAME),
        ("Ține minte că am dentist la 9, anunță-mă.", SCHEDULE_TOOL_NAME),
        ("Merke dir: ich wiege 72,5 kg und mach die Musik an.", SET_VOLUME_TOOL_NAME),
        ("Recuerda que mi cita es a las 9. Gracias, y avísame antes.", SCHEDULE_TOOL_NAME),
        ("Retiens que mon rendez-vous est à 9h. Merci de me prévenir.", SCHEDULE_TOOL_NAME),
    ],
)
def test_a_request_to_remember_in_another_language_with_a_second_clause_keeps_both_tools(
    query: str, tool: str
) -> None:
    assert tool not in unasked_tools(query)


@pytest.mark.parametrize(
    "query",
    [
        "Souviens-toi que le code de mon casier à la piscine est 7731.",
        "Souviens-toi qu'il y a du pain dans le placard.",
        "Souviens-toi que j'y vais le mardi.",
        "Merk dir, dass mein Hund Bello heißt.",
        "Ține minte că numărul apartamentului meu este 42.",
        "Mon code est 7731, souviens-toi.",
        "Merke dir: mein Gewicht ist 72,5 kg.",
        "Retiens que mon code est 4512. Merci beaucoup !",
        "Ține minte că am 1,80 m. Mulțumesc!",
    ],
)
def test_a_request_to_remember_one_fact_in_another_language_refuses_both_tools(
    query: str,
) -> None:
    assert unasked_tools(query) == _BOTH


@pytest.mark.parametrize(
    "query",
    [
        "Recuerda que mi código es 4512. Gracias.",
        "Recuerda que mi código es 4512, ¡muchas gracias!",
    ],
)
def test_a_request_to_remember_in_spanish_with_a_closing_thanks_refuses_the_volume_tool(
    query: str,
) -> None:
    assert unasked_tools(query) == {SET_VOLUME_TOOL_NAME}
