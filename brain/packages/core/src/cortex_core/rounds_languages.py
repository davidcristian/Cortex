"""The rounds note and the sentence naming each tool run, in four other languages."""

from collections.abc import Sequence

from cortex_core.conversation import ToolRun

ROUNDS_SPENT_NOTES = {
    "fr": "\n\n(Cette réponse s'est arrêtée après {rounds} tours d'appels d'outils, le maximum "
    "pour une réponse, sans répondre à ce que les derniers appels ont renvoyé. {runs} Redemandez "
    "pour continuer.)",
    "de": "\n\n(Diese Antwort endete nach {rounds} Runden von Werkzeugaufrufen, dem Höchstwert für "
    "eine Antwort, ohne auf das einzugehen, was die letzten Aufrufe zurückgaben. {runs} Bitten Sie "
    "erneut darum, um fortzufahren.)",
    "es": "\n\n(Esta respuesta se detuvo tras {rounds} rondas de llamadas a herramientas, el "
    "máximo para una respuesta, sin responder a lo que devolvieron las últimas llamadas. {runs} "
    "Pídelo de nuevo para continuar.)",
    "ro": "\n\n(Acest răspuns s-a oprit după {rounds} runde de apeluri de unelte, maximul pentru "
    "un răspuns, fără să răspundă la ce au returnat ultimele apeluri. {runs} Cere din nou pentru "
    "a continua.)",
}
# The label, the words for a run that succeeded and one that failed, and the sentence for no run.
_RUNS = {
    "fr": ("Outils lancés :", "réussi", "échoué", "Aucun outil n'a été lancé."),
    "de": (
        "Ausgeführte Werkzeuge:",
        "erfolgreich",
        "fehlgeschlagen",
        "Kein Werkzeug wurde ausgeführt.",
    ),
    "es": ("Herramientas ejecutadas:", "con éxito", "falló", "No se ejecutó ninguna herramienta."),
    "ro": ("Unelte rulate:", "reușit", "eșuat", "Nu a rulat nicio unealtă."),
}


def runs_said(runs: Sequence[ToolRun], language: str) -> str:
    """The sentence naming each tool of ``runs`` and whether it succeeded, in ``language``."""
    label, succeeded, failed, none = _RUNS[language]
    if not runs:
        return none
    listed = ", ".join(f"{run.name} ({succeeded if run.ok else failed})" for run in runs)
    return f"{label} {listed}."
