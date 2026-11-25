"""The rounds notes in four other languages, and the sentence naming each tool run in all five."""

from collections.abc import Sequence

from cortex_core.conversation import ToolRun
from cortex_core.escalate import ESCALATE_TOOL_NAME
from cortex_core.note_language import ENGLISH
from cortex_core.tool_replay import HANDOFF_STARTED, RUNS_LABEL

NO_TOOL_RAN = "No tool ran."
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
HANDED_ROUNDS_NOTE = (
    "\n\n(I stopped after {rounds} rounds of tool calls, the most one answer may use, and started "
    "a handoff to the deep model. {runs})"
)
HANDED_ROUNDS_NOTES = {
    "fr": "\n\n(Les appels d'outils se sont arrêtés après {rounds} tours, le maximum pour une "
    "réponse, et un transfert au modèle profond a été lancé. {runs})",
    "de": "\n\n(Die Werkzeugaufrufe endeten nach {rounds} Runden, dem Höchstwert für eine "
    "Antwort, und eine Übergabe an das tiefe Modell wurde gestartet. {runs})",
    "es": "\n\n(Las llamadas a herramientas se detuvieron tras {rounds} rondas, el máximo para "
    "una respuesta, y se inició un traspaso al modelo profundo. {runs})",
    "ro": "\n\n(Apelurile de unelte s-au oprit după {rounds} runde, maximul pentru un răspuns, "
    "și a fost pornită o predare către modelul profund. {runs})",
}
# The label, the words for a run that succeeded and one that failed, the sentence for no run, and
# the words for a handoff that started.
_RUNS = {
    ENGLISH: (f"{RUNS_LABEL}:", "succeeded", "failed", NO_TOOL_RAN, HANDOFF_STARTED),
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


# The words for a handoff that started, in a note the deep model's answer may follow.
_HANDED = {
    ENGLISH: "handoff started",
    "fr": "transfert lancé",
    "de": "Übergabe gestartet",
    "es": "traspaso iniciado",
    "ro": "predare pornită",
}


def runs_said(runs: Sequence[ToolRun], language: str, *, handed: bool = False) -> str:
    """The sentence naming each tool of ``runs`` and whether it succeeded, in ``language``."""
    label, succeeded, failed, none, started = _RUNS[language]
    if not runs:
        return none
    if handed:
        started = _HANDED[language]

    def said(run: ToolRun) -> str:
        if not run.ok:
            return failed
        return started if run.name == ESCALATE_TOOL_NAME else succeeded

    listed = ", ".join(f"{run.name} ({said(run)})" for run in runs)
    return f"{label} {listed}."
