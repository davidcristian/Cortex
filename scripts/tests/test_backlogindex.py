from pathlib import Path

import pytest

import backlog
import backlogindex


def _task(
    number: int,
    status: str,
    *,
    title: str = "Wire the memory port",
    group: str = "brain",
    trigger: str | None = None,
    kind: str = "refinements",
) -> backlog.Task:
    """Build one parsed task; the fields are the ones the renderer actually reads."""
    fields = {"Status": status, "Origin": "ADR-0001"}
    fields["Area" if kind == "refinements" else "Sitting"] = group
    if trigger is not None:
        fields["Trigger"] = trigger
    return backlog.Task(
        kind=kind,
        number=number,
        slug="a-slug",
        path=Path(f"docs/{kind}/tasks/{number:03d}-a-slug.md"),
        title=title,
        status=backlog.parse_status(status),
        fields=fields,
    )


# ── the whole block, line for line ─────────────────────────────────────────────


def test_render_lays_out_the_headline_the_open_half_and_the_roll_call() -> None:
    tasks = [
        _task(1, "open, actionable", title="Wire the port"),
        _task(2, "landed 2026-03-04", title="Split the module"),
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
        "- [R-002](tasks/002-a-slug.md) Split the module. landed 2026-03-04.",
        "",
        backlogindex.END,
    ]
    assert backlogindex.render(tasks, "area") == "\n".join(expected)


# ── the open half ──────────────────────────────────────────────────────────────


def test_the_open_half_follows_the_reader_order_not_the_file_order() -> None:
    """Order is the answer to "what should I pick up", so it cannot come from the numbers."""
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
    assert "Fix when it bites" not in remains


def test_a_bucket_names_how_many_are_in_it() -> None:
    tasks = [_task(number, "open, actionable") for number in (1, 2, 3)]
    assert "### Actionable now (3)" in backlogindex.render(tasks, "area")


def test_a_closed_task_is_absent_from_the_open_half() -> None:
    tasks = [_task(1, "landed 2026-03-04"), _task(2, "open, actionable")]
    remains, _, _ = backlogindex.render(tasks, "area").partition("## Every task")
    assert "R-002" in remains
    assert "R-001" not in remains


def test_a_waiting_task_says_what_would_reopen_it() -> None:
    task = _task(1, "open, fix when it bites", trigger="a turn drops a memory")
    entry = "- **[R-001](tasks/001-a-slug.md)** Wire the memory port (brain). Reopens when: "
    assert entry + "a turn drops a memory" in backlogindex.render([task], "area")


def test_a_trigger_on_a_state_that_waits_for_nothing_is_not_shown() -> None:
    """Only the two waiting states promise a trigger; elsewhere it is a note, not a heading."""
    task = _task(1, "open, actionable", trigger="a second adapter arrives")
    assert "Reopens when" not in backlogindex.render([task], "area")


def test_a_backlog_with_nothing_open_says_so_instead() -> None:
    block = backlogindex.render([_task(1, "landed 2026-03-04")], "area")
    assert "**0 open, 1 closed, 1 in total.**" in block
    assert "Nothing. Every task here is closed." in block
    assert "### Actionable now" not in block


# ── the roll call ──────────────────────────────────────────────────────────────


def test_the_roll_call_sorts_the_groups_and_counts_each_one() -> None:
    tasks = [
        _task(1, "open, actionable", group="seam"),
        _task(2, "landed 2026-03-04", group="brain", title="Split the module"),
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
    assert line in backlogindex.render([task], "sitting")


def test_an_empty_backlog_names_the_word_its_groups_go_by() -> None:
    block = backlogindex.render([], "sitting")
    assert "**0 open, 0 closed, 0 in total.**" in block
    assert "## Every task, by sitting" in block
    assert "No sitting holds a task yet." in block


# ── splicing the block into a hand-written index ───────────────────────────────


def test_splice_replaces_the_generated_block_and_nothing_else() -> None:
    existing = (
        f"# The backlog\n\nHow a person works it.\n\n{backlogindex.BEGIN}\nstale\n"
        f"{backlogindex.END}\n\nA footer nobody generated.\n"
    )
    kept = "# The backlog\n\nHow a person works it.\n\nFRESH\n\nA footer nobody generated.\n"
    assert backlogindex.splice(existing, "FRESH") == kept


def test_splice_of_an_already_fresh_index_changes_nothing() -> None:
    """The gate compares two texts, so a second pass must reproduce the first byte for byte."""
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


# ── standing items are counted apart, so that neither number lies ──────────────


def test_a_standing_item_is_counted_apart_from_open_and_closed() -> None:
    tasks = [
        _task(1, "never attempted", kind="host", group="windows-desktop"),
        _task(2, "done 2026-08-04", kind="host", group="windows-desktop"),
        _task(3, "standing: watched over months", kind="host", group="windows-desktop"),
    ]
    block = backlogindex.render(tasks, "sitting")
    assert "**1 open, 1 standing, 1 closed, 3 in total.**" in block


def test_the_standing_clause_is_absent_when_nothing_is_standing() -> None:
    block = backlogindex.render([_task(1, "open, actionable")], "area")
    assert "**1 open, 0 closed, 1 in total.**" in block
    assert "standing" not in block


def test_a_standing_item_gets_its_own_section_naming_why_it_never_closes() -> None:
    tasks = [
        _task(1, "open, actionable"),
        _task(
            2,
            "standing: an obligation on every change",
            kind="host",
            group="windows-desktop",
            title="The toolchain-linked full build",
        ),
    ]
    block = backlogindex.render(tasks, "sitting")
    assert "## Standing, never closes (1)" in block
    assert (
        "- **[H-002](tasks/002-a-slug.md)** The toolchain-linked full build "
        "(windows-desktop): an obligation on every change." in block
    )


def test_the_standing_section_is_absent_when_nothing_is_standing() -> None:
    block = backlogindex.render([_task(1, "open, actionable")], "area")
    assert "Standing, never closes" not in block


def test_a_standing_item_is_absent_from_the_open_half() -> None:
    tasks = [_task(1, "standing: watched over months", kind="host", group="windows-desktop")]
    block = backlogindex.render(tasks, "sitting")
    assert "Nothing. Every task here is closed." in block


def test_the_roll_call_phrase_for_a_standing_item_carries_its_reason() -> None:
    tasks = [_task(1, "standing: watched over months", kind="host", group="windows-desktop")]
    block = backlogindex.render(tasks, "sitting")
    assert "standing: watched over months." in block


# ── a trigger nobody ever wrote is counted, not hidden ─────────────────────────


def test_an_unrecorded_trigger_is_named_rather_than_quoted() -> None:
    tasks = [_task(1, "open, fix when it bites", trigger=backlog.UNRECORDED)]
    block = backlogindex.render(tasks, "area")
    assert "No trigger was ever recorded for it." in block
    assert "Reopens when" not in block


def test_the_open_half_counts_the_triggers_nobody_wrote() -> None:
    tasks = [
        _task(1, "open, fix when it bites", trigger=backlog.UNRECORDED),
        _task(2, "open, dead until a consumer", trigger=backlog.UNRECORDED),
        _task(3, "open, fix when it bites", trigger="a second consumer appears"),
    ]
    block = backlogindex.render(tasks, "area")
    assert "2 of these wait on something nobody wrote down." in block


def test_nothing_is_said_when_every_waiting_task_names_its_trigger() -> None:
    tasks = [_task(1, "open, fix when it bites", trigger="a second consumer appears")]
    block = backlogindex.render(tasks, "area")
    assert "nobody wrote down" not in block
    assert "Reopens when: a second consumer appears" in block
