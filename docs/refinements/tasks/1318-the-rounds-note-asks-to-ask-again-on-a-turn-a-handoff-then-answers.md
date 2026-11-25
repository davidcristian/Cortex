# The rounds note asks to ask again on a turn a handoff then answers

**Status:** done 2026-11-25
**Area:** tools-mcp
**Origin:** [ADR-0076](../../adr/ADR-0076-closing-note-language.md)

An approved `escalate_to_brain` call does not end the cortex's tool loop: its result tells the
model to wrap up, and a model that calls tools on until `MAX_TOOL_STEPS` gets `ROUNDS_SPENT_NOTE`
(`turn_output.py`), in all five languages. The test
`test_a_turn_that_runs_out_of_rounds_after_a_handoff_names_it_as_started` (`test_engine.py`)
draws that turn. `EscalatingTurnEngine` then runs the handoff, since the slot holds a brief, and
the deep model's answer follows the note in the same reply. The note says the cortex did not
reply to what the last calls returned and ends `Ask again to continue.`, and it lists the handoff
as `handoff started, answer not recorded here`, which the person can read as saying no answer
came. Both are written for a turn that ends at the note.

What would close it: a form of the note for a turn whose runs hand off (`hands_off` in
`escalate.py`), true whether or not the deep model then answers, in the five note languages with
its sentences written for review, or a test showing a handoff answer never follows this note.

## History

- 2026-11-24: filed when the translated rounds note started writing a handoff as started
  ([R-1258](1258-the-translated-rounds-note-names-a-started-handoff-as-a-success.md)).
- 2026-11-25: done. The premise holds: `EscalatingTurnEngine` runs the handoff after the cortex
  phase whenever the slot holds a brief, so its answer or a failure note follows the rounds note.
  A turn whose runs hand off now gets `HANDED_ROUNDS_NOTE` (`rounds_languages.py`) in all five
  note languages: it says a handoff to the deep model started, lists the handoff as started with
  nothing about its answer, and asks for nothing. A declined handoff keeps the note that asks
  again. `model_text` leaves the new form out like every other note.
