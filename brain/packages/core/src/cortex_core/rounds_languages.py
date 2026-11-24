"""The rounds note and the sentence naming each tool run, in four other languages."""

from collections.abc import Sequence

from cortex_core.conversation import ToolRun
from cortex_core.escalate import ESCALATE_TOOL_NAME

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
# The label, the words for a run that succeeded and one that failed, the sentence for no run, and
# the words for a handoff that started.
_RUNS = {
    "fr": (
        "Outils lancés :",
        "réussi",
        "échoué",
        "Aucun outil n'a été lancé.",
        "transfert lancé, réponse non enregistrée ici",
    ),
    "de": (
        "Ausgeführte Werkzeuge:",
        "erfolgreich",
        "fehlgeschlagen",
        "Kein Werkzeug wurde ausgeführt.",
        "Übergabe gestartet, Antwort hier nicht festgehalten",
    ),
    "es": (
        "Herramientas ejecutadas:",
        "con éxito",
        "falló",
        "No se ejecutó ninguna herramienta.",
        "traspaso iniciado, respuesta no registrada aquí",
    ),
    "ro": (
        "Unelte rulate:",
        "reușit",
        "eșuat",
        "Nu a rulat nicio unealtă.",
        "predare pornită, răspuns neînregistrat aici",
    ),
}


def runs_said(runs: Sequence[ToolRun], language: str) -> str:
    """The sentence naming each tool of ``runs`` and whether it succeeded, in ``language``."""
    label, succeeded, failed, none, started = _RUNS[language]
    if not runs:
        return none

    def said(run: ToolRun) -> str:
        if not run.ok:
            return failed
        return started if run.name == ESCALATE_TOOL_NAME else succeeded

    listed = ", ".join(f"{run.name} ({said(run)})" for run in runs)
    return f"{label} {listed}."
