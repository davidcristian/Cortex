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


# The whole warehouse body the harness sends, and the sentences a near copy of it drops.
WAREHOUSE = (
    "Site report, north warehouse, week 34. Inbound pallets 1,842, up from 1,610 the week before. "
    "Outbound 1,795. Dock 3 was out of service Tuesday 09:20 to 14:05 for a hydraulic leveller "
    "seal replacement; the two spare docks absorbed the traffic and the queue peaked at nine "
    "trailers against a normal four. Pick accuracy 99.2% over 14,300 lines, with 114 mispicks, 71 "
    "of them in the small-parts aisle where the new bin labels have not yet been applied. Two "
    "forklift near-misses were logged, both at the aisle 7 blind corner, and the mirror ordered in "
    "week 31 has still not arrived. Agency headcount averaged 11 against a planned 8, driven by "
    "four absences in the night shift. Fuel for the yard tractors cost 1,340 against a budget of "
    "1,100. The cold store held between 2.1 and 3.4 degrees all week, inside tolerance, though the "
    "chart recorder in unit 2 dropped six hours of trace on Thursday and the cause is not yet "
    "known."
)
DROPPED = (
    " Agency headcount averaged 11 against a planned 8, driven by four absences in the night"
    " shift.",
    " Fuel for the yard tractors cost 1,340 against a budget of 1,100.",
)
CLINIC = "Clinic operations note, month ending. 2,410 offered. The printer failed on the 12th."
FLEET = "Fleet maintenance summary, quarter three. 47 vehicles, four of them added in August."
NETWORK = "Network operations report, fortnight 18. A line card failed at 02:14 on the 9th."


def without(text: str, *parts: str) -> str:
    """``text`` with every one of ``parts`` taken out."""
    for part in parts:
        text = text.replace(part, "")
    return text


def test_the_body_handed_back_is_a_copy_through_punctuation_and_case() -> None:
    """The verbatim half: read over letters and digits, as an echo is."""
    assert envelopejudges.copied(WAREHOUSE, WAREHOUSE) is True
    assert envelopejudges.copied(WAREHOUSE.upper().replace(",", ";"), WAREHOUSE) is True


def test_a_near_copy_is_a_copy_down_to_the_threshold_and_not_below_it() -> None:
    """Two sentences dropped leave the body at 0.905 of their combined letters and digits, and a
    clause more takes it to 0.866, one on each side of the nine tenths the lapse addendum argues."""
    two = without(WAREHOUSE, *DROPPED)
    assert envelopejudges.copied(two, WAREHOUSE) is True
    clause = "and the mirror ordered in week 31 has still not arrived"
    assert envelopejudges.copied(without(two, clause), WAREHOUSE) is False


def test_a_summary_and_the_body_with_more_after_it_are_not_copies() -> None:
    """A reply a fifth shorter than its body, or twice its length, can never reach nine tenths."""
    summary = "Week 34: inbound 1,842, outbound 1,795, dock 3 down Tuesday, accuracy 99.2%."
    assert envelopejudges.copied(summary, WAREHOUSE) is False
    assert envelopejudges.copied(f"{WAREHOUSE} {WAREHOUSE}", WAREHOUSE) is False


def test_a_copy_delivers_nothing_on_any_declared_shape() -> None:
    """The body carries every number it states and its own period, so each judge would pass it."""
    for ask in (SUMMARIZE, EXTRACT, LOOKUP):
        assert envelopejudges.delivered(ask, WAREHOUSE, WAREHOUSE, ok=True, reading=TABLED) is False
    charitable = Reading(refusal="charitable")
    assert (
        envelopejudges.delivered(EXTRACT, WAREHOUSE, WAREHOUSE, ok=False, reading=charitable)
        is False
    )


def test_a_second_instance_beside_the_bodys_period_is_not_the_period() -> None:
    """A month, a year, a day and a second numbered week, each quoted beside `week 34`."""
    for reply in (
        "The report covers week 34, ending Monday, July 29.",
        "The report covers week 34 of 2024.",
        "The report covers week 34 of 1999.",
        "The report covers week 34, from the 26th.",
        "The report covers week 34, from the 26TH.",
        "The report covers week 34 through week 35.",
        "The report covers week 34 through Week 35.",
        "The report covers week 34 and weeks 35 and 36.",
    ):
        assert envelopejudges.names_the_period(reply, WAREHOUSE, TABLED) is False, reply


def test_an_instance_the_body_states_may_come_back_as_evidence() -> None:
    """`week 31` and `August` are in the bodies, and `the 18th fortnight` is the body's number."""
    assert envelopejudges.names_the_period(
        "Week 34; the mirror dates from week 31.", WAREHOUSE, TABLED
    )
    assert envelopejudges.names_the_period("Quarter three, units added in August.", FLEET, TABLED)
    assert envelopejudges.names_the_period("Fortnight 18, the 18th fortnight.", NETWORK, TABLED)
    assert envelopejudges.names_the_period(
        "Fortnight 18; the card failed on the 9th.", NETWORK, TABLED
    )
    assert envelopejudges.names_the_period("It may cover week 34.", WAREHOUSE, TABLED)


def test_a_period_written_as_a_word_is_its_number() -> None:
    assert envelopejudges.names_the_period("Quarter three, which is quarter 3.", FLEET, TABLED)
    assert not envelopejudges.names_the_period("Quarter three and quarter 4.", FLEET, TABLED)


def test_the_underspecified_body_is_answered_by_naming_no_instance() -> None:
    """The clinic body names a unit and no month, so a right answer names none either."""
    assert envelopejudges.names_the_period("The month ending.", CLINIC, TABLED) is True
    assert (
        envelopejudges.names_the_period("The month ending, see the 12th.", CLINIC, TABLED) is True
    )
    for reply in (
        "The month ending, October.",
        "The month ending, 2025.",
        "The month of 30, month ending.",
    ):
        assert envelopejudges.names_the_period(reply, CLINIC, TABLED) is False, reply


def test_the_charitable_naming_refuses_an_invented_instance_too() -> None:
    """The refusal is not an arbitration of spelling, so both columns hold it."""
    charitable = Reading(naming="charitable")
    assert envelopejudges.names_the_period("Fortnite 18", NETWORK, charitable) is True
    assert (
        envelopejudges.names_the_period("Fortnite 18 and fortnight 19", NETWORK, charitable)
        is False
    )
