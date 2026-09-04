import envelopejudges
from envelopejudges import TABLED, Reading

# The three subtask shapes this arc sweeps, as the harness asks them, and one body of the four.
SUMMARIZE = "Summarize the report below, keeping every detail."
EXTRACT = "Extract every number from the report below."
LOOKUP = "What reporting period does the report below cover?"
SENT = f"{SUMMARIZE} Your entire response must be the answer itself."
BODY = (
    "Site report, north warehouse, week 34. Inbound pallets 1,842, up from 1,610 the week before. "
    "Outbound 1,795. Pick accuracy 99.2% over 14,300 lines, with 114 mispicks."
)
NUMBERS = "1,842 1,610 1,795 99.2 14,300 114 34"


def test_a_literal_is_the_value_it_names() -> None:
    """Two spellings of one number are one literal, so a reply that drops a comma or pads a
    digit still recalls the number the body wrote."""
    assert envelopejudges.canonical("1,842") == "1842"
    assert envelopejudges.canonical("09") == "9"
    assert envelopejudges.canonical("0") == "0"
    assert envelopejudges.canonical("99.2") == "99.2"


def test_a_comma_joins_digit_groups_or_ends_a_number() -> None:
    """The arbitration itself, on the shape that forces it: a bare comma-joined list, in which
    one comma is inside a number and the next is between two."""
    assert envelopejudges.literals("1,842, 1,610", joined=True) == frozenset({"1842", "1610"})
    assert envelopejudges.literals("1,842, 1,610", joined=False) == frozenset({"1", "842", "610"})


def test_the_charitable_comma_reads_a_joined_list_the_better_of_the_two_ways() -> None:
    """The column the ADR-0028 tables are in. Under the separator reading the same reply recalls
    none of the body's numbers, which is the cell the lineup addendum found moving by one draw."""
    reply = "1,842, 1,610, 1,795, 99.2, 14,300, 114, 34"
    assert envelopejudges.carries_the_numbers(reply, BODY, TABLED) is True
    assert envelopejudges.carries_the_numbers(reply, BODY, Reading(comma="thousands")) is True
    assert envelopejudges.carries_the_numbers(reply, BODY, Reading(comma="separator")) is False


def test_a_narration_carries_none_of_the_bodys_numbers() -> None:
    """The failure this whole arc is about: a well formed reply about the task rather than the
    answer to it, which stands and does not deliver."""
    narration = "The user wants a summary of the provided site report."
    assert envelopejudges.carries_the_numbers(narration, BODY, TABLED) is False


def test_a_body_stating_no_number_is_judged_by_nothing() -> None:
    """The recall proxy is a fraction of the body's own numbers, so a body carrying none leaves
    the run unjudged rather than counted either way."""
    blank = "a report with no numbers"
    assert envelopejudges.carries_the_numbers("anything", blank, TABLED) is None


def test_the_strict_naming_wants_the_period_as_the_body_writes_it() -> None:
    assert envelopejudges.names_the_period("The report covers week 34.", BODY, TABLED) is True
    assert envelopejudges.names_the_period("The second half of the month.", BODY, TABLED) is False


def test_the_charitable_naming_accepts_the_period_garbled_or_inflected() -> None:
    """Both replies are the record's own: `Fortnite 18` and `34 weeks` are what the charitable
    column of the row addendum moved two cells on."""
    fortnight = "Network operations report, fortnight 18."
    charitable = Reading(naming="charitable")
    assert envelopejudges.names_the_period("Fortnite 18", fortnight, charitable) is True
    assert envelopejudges.names_the_period("34 weeks", BODY, charitable) is True
    assert envelopejudges.names_the_period("Fortnite 18", fortnight, TABLED) is False


def test_the_charitable_naming_still_wants_both_halves_of_the_period() -> None:
    """A unit with the wrong number and a number with no unit are both wrong answers, so the
    charitable reading forgives the spelling of the unit and nothing else."""
    charitable = Reading(naming="charitable")
    assert envelopejudges.names_the_period("week 31", BODY, charitable) is False
    assert envelopejudges.names_the_period("34", BODY, charitable) is False


def test_a_body_stating_no_period_is_judged_by_nothing() -> None:
    assert envelopejudges.names_the_period("week 34", "a report about nothing", TABLED) is None


def test_a_judge_is_declared_for_each_shape_this_arc_sweeps() -> None:
    for instruction in (SUMMARIZE, EXTRACT, LOOKUP):
        declared = envelopejudges.declared(instruction)
        assert declared is not None, instruction


def test_a_shape_is_matched_on_its_opening_so_the_appended_sentence_does_not_hide_it() -> None:
    """The runner appends `REPLY_INSTRUCTION` last on the constrained path, so the constrained
    arm's instruction is the shape plus a sentence and is still that shape."""
    declared = envelopejudges.declared(SENT)
    assert declared is not None
    assert declared.shape == "Summarize the report below, keeping every detail"


def test_a_hand_typed_instruction_has_no_judge() -> None:
    """`CORTEX_ENVELOPE_INSTRUCTION` lets the subtask be anything, and anything is what no judge
    here can read, so the run is unjudged rather than guessed at."""
    assert envelopejudges.declared("Write a limerick about the report below.") is None


def test_a_run_of_an_undeclared_shape_delivers_nothing_either_way() -> None:
    ask = "Write a limerick about the report below."
    assert envelopejudges.delivered(ask, BODY, NUMBERS, ok=True, reading=TABLED) is None


def test_the_strict_refusal_reading_counts_a_refused_run_a_non_delivery() -> None:
    """The column the tables are in: a run cut at the cap is a non-delivery whatever its text
    held, and the text of this one holds every number the body states."""
    assert envelopejudges.delivered(EXTRACT, BODY, NUMBERS, ok=False, reading=TABLED) is False


def test_the_charitable_refusal_reading_judges_a_refused_runs_text() -> None:
    charitable = Reading(refusal="charitable")
    assert envelopejudges.delivered(EXTRACT, BODY, NUMBERS, ok=False, reading=charitable) is True


def test_an_accepted_run_is_judged_by_the_shapes_own_judge() -> None:
    assert envelopejudges.delivered(EXTRACT, BODY, NUMBERS, ok=True, reading=TABLED) is True
    assert envelopejudges.delivered(LOOKUP, BODY, "week 34", ok=True, reading=TABLED) is True
    assert envelopejudges.delivered(LOOKUP, BODY, NUMBERS, ok=True, reading=TABLED) is False


def test_a_reading_names_its_three_columns() -> None:
    """Every report says which reading produced its rates, since each of the three is a reading
    the addenda took rather than a rule they followed."""
    assert TABLED.rendered() == "comma charitable, refusal strict, naming strict"
