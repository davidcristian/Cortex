from pathlib import Path

import pytest

import backlog
import backlogindex


def _task(  # noqa: PLR0913 -- one keyword per field a task file has, all but two optional
    number: int,
    status: str,
    *,
    title: str = "Wire the memory port",
    group: str = "brain",
    trigger: str | None = None,
    verified: str | None = None,
    kind: str = "refinements",
) -> backlog.Task:
    """Build one parsed task with the fields the renderer reads."""
    fields = {"Status": status, "Origin": "ADR-0001"}
    fields["Area" if kind == "refinements" else "Session"] = group
    if trigger is not None:
        fields["Trigger"] = trigger
    if verified is not None:
        fields["Verified"] = verified
    return backlog.Task(
        kind=kind,
        number=number,
        slug="a-slug",
        path=Path(f"docs/{kind}/tasks/{number:03d}-a-slug.md"),
        title=title,
        status=backlog.parse_status(status),
        fields=fields,
    )


def test_render_lays_out_the_headline_the_open_half_and_the_roll_call() -> None:
    tasks = [
        _task(1, "open, actionable", title="Wire the port"),
        _task(2, "done 2026-03-04", title="Split the module"),
    ]
    expected = [
        backlogindex.BEGIN,
        "",
        "**1 open, 1 closed, 2 in total.**",
        "",
        "## What remains",
        "",
        "### Actionable now (1)",
        "",
        "- **[R-001](tasks/001-a-slug.md)** Wire the port (brain).",
        "",
        "## Every task, by area",
        "",
        "### brain",
        "",
        "1 open of 2.",
        "",
        "- [R-001](tasks/001-a-slug.md) Wire the port. open, actionable.",
        "- [R-002](tasks/002-a-slug.md) Split the module. done 2026-03-04.",
        "",
        backlogindex.END,
    ]
    assert backlogindex.render(tasks, "area") == "\n".join(expected)


def test_the_open_half_follows_the_reader_order_not_the_file_order() -> None:
    states = [f"open, {state}" for state in backlog.OPEN_STATES]
    states += ["never attempted", "attempted 2026-03-04, inconclusive: the card was busy"]
    tasks = [
        _task(number, status, trigger="a consumer arrives")
        for number, status in enumerate(reversed(states), start=1)
    ]
    remains, _, _ = backlogindex.render(tasks, "area").partition("## Every task")
    headings = [line for line in remains.splitlines() if line.startswith("### ")]
    assert headings == [f"### {bucket} (1)" for bucket in backlogindex.BUCKET_ORDER]
    assert remains.count("Reopens when: a consumer arrives") == len(backlog.NEEDS_TRIGGER)


def test_a_bucket_nobody_is_in_is_left_out() -> None:
    block = backlogindex.render([_task(1, "open, actionable")], "area")
    remains, _, _ = block.partition("## Every task")
    assert "### Actionable now (1)" in remains
    assert "Waiting for its trigger" not in remains


def test_a_bucket_names_how_many_are_in_it() -> None:
    tasks = [_task(number, "open, actionable") for number in (1, 2, 3)]
    assert "### Actionable now (3)" in backlogindex.render(tasks, "area")


def test_a_closed_task_is_absent_from_the_open_half() -> None:
    tasks = [_task(1, "done 2026-03-04"), _task(2, "open, actionable")]
    remains, _, _ = backlogindex.render(tasks, "area").partition("## Every task")
    assert "R-002" in remains
    assert "R-001" not in remains


def test_a_waiting_task_says_what_would_reopen_it() -> None:
    task = _task(1, "open, waiting for its trigger", trigger="a turn drops a memory")
    entry = "- **[R-001](tasks/001-a-slug.md)** Wire the memory port (brain). Reopens when: "
    assert entry + "a turn drops a memory." in backlogindex.render([task], "area")


def test_a_trigger_on_a_state_that_waits_for_nothing_is_not_shown() -> None:
    task = _task(1, "open, actionable", trigger="a second adapter arrives")
    assert "Reopens when" not in backlogindex.render([task], "area")


def test_a_backlog_with_nothing_open_says_so_instead() -> None:
    block = backlogindex.render([_task(1, "done 2026-03-04")], "area")
    assert "**0 open, 1 closed, 1 in total.**" in block
    assert "Nothing. Every task here is closed." in block
    assert "### Actionable now" not in block


def test_the_roll_call_sorts_the_groups_and_counts_each_one() -> None:
    tasks = [
        _task(1, "open, actionable", group="seam"),
        _task(2, "done 2026-03-04", group="brain", title="Split the module"),
        _task(3, "open, actionable", group="brain", title="Wire the port"),
    ]
    _, _, roll = backlogindex.render(tasks, "area").partition("## Every task, by area")
    assert [line for line in roll.splitlines() if line.startswith("### ")] == [
        "### brain",
        "### seam",
    ]
    assert "1 open of 2." in roll
    assert "1 open of 1." in roll
    assert roll.index("R-002") < roll.index("R-003")


@pytest.mark.parametrize(
    ("status", "phrase"),
    [
        ("open, actionable", "open, actionable"),
        ("never attempted", "never attempted"),
        ("attempted 2026-03-04, inconclusive: the card was busy", "attempted 2026-03-04"),
        ("done 2026-03-04", "done 2026-03-04"),
    ],
)
def test_the_roll_call_phrase_for_each_kind_of_status(status: str, phrase: str) -> None:
    task = _task(7, status, kind="host", group="hotkey bring-up", title="Bring the hotkey up")
    line = f"- [H-007](tasks/007-a-slug.md) Bring the hotkey up. {phrase}."
    assert line in backlogindex.render([task], "session")


def test_an_empty_backlog_names_the_word_its_groups_go_by() -> None:
    block = backlogindex.render([], "session")
    assert "**0 open, 0 closed, 0 in total.**" in block
    assert "## Every task, by session" in block
    assert "No session holds a task yet." in block


def test_splice_replaces_the_generated_block_and_nothing_else() -> None:
    existing = (
        f"# The backlog\n\nHow a person works it.\n\n{backlogindex.BEGIN}\nstale\n"
        f"{backlogindex.END}\n\nA footer nobody generated.\n"
    )
    kept = "# The backlog\n\nHow a person works it.\n\nFRESH\n\nA footer nobody generated.\n"
    assert backlogindex.splice(existing, "FRESH") == kept


def test_splice_of_an_already_fresh_index_changes_nothing() -> None:
    block = backlogindex.render([_task(1, "open, actionable")], "area")
    existing = f"# The backlog\n\n{backlogindex.BEGIN}\n{backlogindex.END}\n\nA footer.\n"
    once = backlogindex.splice(existing, block)
    assert backlogindex.splice(once, block) == once


@pytest.mark.parametrize(
    "existing",
    [
        "# The backlog\n\nNo markers at all.\n",
        f"# The backlog\n\n{backlogindex.BEGIN}\nno end marker\n",
        f"# The backlog\n\nno begin marker\n{backlogindex.END}\n",
        f"# The backlog\n\n{backlogindex.END}\nthe wrong way round\n{backlogindex.BEGIN}\n",
    ],
)
def test_splice_refuses_an_index_that_does_not_mark_its_generated_block(existing: str) -> None:
    with pytest.raises(ValueError, match="the index needs both"):
        backlogindex.splice(existing, "FRESH")


def test_an_ongoing_item_is_counted_apart_from_open_and_closed() -> None:
    tasks = [
        _task(1, "never attempted", kind="host", group="windows-desktop"),
        _task(2, "done 2026-08-04", kind="host", group="windows-desktop"),
        _task(3, "ongoing: watched over months", kind="host", group="windows-desktop"),
    ]
    block = backlogindex.render(tasks, "session")
    assert "**1 open, 1 ongoing, 1 closed, 3 in total.**" in block


def test_the_ongoing_clause_is_absent_when_nothing_is_ongoing() -> None:
    block = backlogindex.render([_task(1, "open, actionable")], "area")
    assert "**1 open, 0 closed, 1 in total.**" in block
    assert "ongoing" not in block


def test_an_ongoing_item_gets_its_own_section_naming_why_it_never_closes() -> None:
    tasks = [
        _task(1, "open, actionable"),
        _task(
            2,
            "ongoing: an obligation on every change",
            kind="host",
            group="windows-desktop",
            title="The toolchain-linked full build",
        ),
    ]
    block = backlogindex.render(tasks, "session")
    assert "## Ongoing, never closes (1)" in block
    assert (
        "- **[H-002](tasks/002-a-slug.md)** The toolchain-linked full build "
        "(windows-desktop): an obligation on every change." in block
    )


def test_the_ongoing_section_is_absent_when_nothing_is_ongoing() -> None:
    block = backlogindex.render([_task(1, "open, actionable")], "area")
    assert "Ongoing, never closes" not in block


def test_an_ongoing_item_is_absent_from_the_open_half() -> None:
    tasks = [_task(1, "ongoing: watched over months", kind="host", group="windows-desktop")]
    block = backlogindex.render(tasks, "session")
    assert "Nothing. Every task here is closed." in block


def test_the_roll_call_phrase_for_an_ongoing_item_shows_its_reason() -> None:
    tasks = [_task(1, "ongoing: watched over months", kind="host", group="windows-desktop")]
    block = backlogindex.render(tasks, "session")
    assert "ongoing: watched over months." in block


def test_an_unrecorded_trigger_is_named_rather_than_quoted() -> None:
    tasks = [_task(1, "open, waiting for its trigger", trigger=backlog.UNRECORDED)]
    block = backlogindex.render(tasks, "area")
    assert "No trigger was ever recorded for it." in block
    assert "Reopens when" not in block


def test_the_open_half_counts_the_triggers_nobody_wrote() -> None:
    tasks = [
        _task(1, "open, waiting for its trigger", trigger=backlog.UNRECORDED),
        _task(2, "open, waiting for a consumer", trigger=backlog.UNRECORDED),
        _task(3, "open, waiting for its trigger", trigger="a second consumer appears"),
    ]
    block = backlogindex.render(tasks, "area")
    assert "2 of these wait on something nobody wrote down." in block


def test_the_last_unwritten_trigger_is_counted_in_the_singular() -> None:
    tasks = [
        _task(1, "open, waiting for its trigger", trigger=backlog.UNRECORDED),
        _task(2, "open, waiting for its trigger", trigger="a second consumer appears"),
    ]
    block = backlogindex.render(tasks, "area")
    assert "One of these waits on something nobody wrote down." in block
    assert "1 of these wait" not in block


def test_nothing_is_said_when_every_waiting_task_names_its_trigger() -> None:
    tasks = [_task(1, "open, waiting for its trigger", trigger="a second consumer appears")]
    block = backlogindex.render(tasks, "area")
    assert "nobody wrote down" not in block
    assert "Reopens when: a second consumer appears" in block


CLAIM = "Its claim was checked against the code on 2026-09-09."


def test_a_dated_claim_is_shown_on_the_entry_that_records_it() -> None:
    task = _task(1, "open, actionable", verified="2026-09-09")
    entry = f"- **[R-001](tasks/001-a-slug.md)** Wire the memory port (brain). {CLAIM}"
    assert entry in backlogindex.render([task], "area")


def test_a_dated_claim_follows_the_trigger_rather_than_displacing_it() -> None:
    task = _task(
        1, "open, waiting for its trigger", trigger="a turn drops a memory", verified="2026-09-09"
    )
    entry = (
        "- **[R-001](tasks/001-a-slug.md)** Wire the memory port (brain). "
        f"Reopens when: a turn drops a memory. {CLAIM}"
    )
    assert entry in backlogindex.render([task], "area")


def test_a_trigger_written_as_a_sentence_is_not_given_a_second_full_stop() -> None:
    task = _task(1, "open, waiting for its trigger", trigger="a turn drops a memory.")
    block = backlogindex.render([task], "area")
    assert "Reopens when: a turn drops a memory." in block
    assert "memory.." not in block


def test_the_open_half_counts_the_claims_somebody_has_checked() -> None:
    tasks = [
        _task(1, "open, actionable", verified="2026-09-09"),
        _task(2, "open, actionable", verified="2026-09-08"),
        _task(3, "open, actionable"),
    ]
    block = backlogindex.render(tasks, "area")
    assert (
        "2 of these record the day their claims were last checked against the code. On every "
        "other task here, that reading is still yours to take." in block
    )


def test_the_first_dated_claim_is_counted_in_the_singular() -> None:
    tasks = [_task(1, "open, actionable", verified="2026-09-09"), _task(2, "open, actionable")]
    block = backlogindex.render(tasks, "area")
    assert "One of these records the day its claim was last checked against the code." in block
    assert "1 of these record" not in block


def test_nothing_is_said_when_no_task_records_a_reading() -> None:
    block = backlogindex.render([_task(1, "open, actionable")], "area")
    assert "checked against the code" not in block


def test_a_host_task_renders_its_dated_claim_and_is_counted() -> None:
    tasks = [
        _task(7, "never attempted", kind="host", group="hotkey bring-up", title="Bring it up"),
        _task(8, "never attempted", kind="host", group="hotkey bring-up", verified="2026-09-11"),
    ]
    block = backlogindex.render(tasks, "session")
    entry = (
        "- **[H-008](tasks/008-a-slug.md)** Wire the memory port (hotkey bring-up). "
        "Its claim was checked against the code on 2026-09-11."
    )
    assert entry in block
    assert "One of these records the day its claim was last checked against the code." in block
