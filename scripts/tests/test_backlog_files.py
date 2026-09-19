from pathlib import Path

import pytest

import backlog

TITLE = "Wire the memory port to its second adapter"
REFINEMENT_PATH = Path("docs/refinements/tasks/042-wire-the-memory-port.md")
HOST_PATH = Path("docs/host/tasks/007-bring-the-hotkey-up.md")
REFINEMENT_FIELDS = {"Status": "open, actionable", "Area": "brain", "Origin": "ADR-0001"}
HOST_FIELDS = {
    "Status": "never attempted",
    "Session": "hotkey bring-up",
    "Capability": "W",
    "Origin": "ADR-0003",
}


def _file(fields: dict[str, str], title: str = TITLE) -> str:
    """Render a task file: the H1, one blank line, then the field block."""
    block = "\n".join(f"**{name}:** {value}" for name, value in fields.items())
    return f"# {title}\n\n{block}\n"


def _write(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_a_refinement_file_parses_into_its_identity_and_fields() -> None:
    task = backlog.parse_task("refinements", REFINEMENT_PATH, _file(REFINEMENT_FIELDS))
    assert task.ident == "R-042"
    assert task.number == 42
    assert task.slug == "wire-the-memory-port"
    assert task.title == TITLE
    assert task.group == "brain"
    assert task.status.state == "actionable"
    assert task.fields["Origin"] == "ADR-0001"


def test_a_host_file_parses_into_its_own_identity_and_session() -> None:
    task = backlog.parse_task("host", HOST_PATH, _file(HOST_FIELDS, title="Bring the hotkey up"))
    assert task.ident == "H-007"
    assert task.group == "hotkey bring-up"
    assert task.status.state == "never attempted"
    assert task.fields["Capability"] == "W"


@pytest.mark.parametrize(
    "name",
    [
        "1-wire-the-port.md",
        "0042-wire-the-port.md",
        "042_wire_the_port.md",
        "042-Wire-The-Port.md",
        "042-wire--the-port.md",
        "042-wire-the-port-.md",
        "042-.md",
        "042-wire-the-port.markdown",
        "index.md",
    ],
)
def test_a_file_name_outside_the_layout_is_rejected(name: str) -> None:
    path = Path("docs/refinements/tasks") / name
    with pytest.raises(backlog.TaskFileError, match="must be NNN-a-hyphenated-slug"):
        backlog.parse_task("refinements", path, _file(REFINEMENT_FIELDS))


@pytest.mark.parametrize(
    ("name", "number", "slug"),
    [
        ("000-a.md", 0, "a"),
        ("007-two-words.md", 7, "two-words"),
        ("999-adr-0001-follow-up.md", 999, "adr-0001-follow-up"),
    ],
)
def test_a_file_name_inside_the_layout_gives_the_number_and_slug(
    name: str, number: int, slug: str
) -> None:
    task = backlog.parse_task("refinements", Path(name), _file(REFINEMENT_FIELDS))
    assert (task.number, task.slug) == (number, slug)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "**Status:** open, actionable\n",
        "## A subheading first\n",
        "#No space after the hash\n",
        "#  \n",
    ],
)
def test_a_file_without_an_h1_title_is_rejected(text: str) -> None:
    with pytest.raises(backlog.TaskFileError, match="first line must be a non-empty '# Title'"):
        backlog.parse_task("refinements", REFINEMENT_PATH, text)


def test_the_field_block_may_follow_the_title_with_or_without_blank_lines() -> None:
    block = "\n".join(f"**{name}:** {value}" for name, value in REFINEMENT_FIELDS.items())
    tight = backlog.parse_task("refinements", REFINEMENT_PATH, f"# {TITLE}\n{block}\n")
    loose = backlog.parse_task("refinements", REFINEMENT_PATH, f"# {TITLE}\n\n\n{block}\n")
    assert tight.fields == loose.fields == REFINEMENT_FIELDS


def test_the_field_block_ends_at_the_first_line_that_is_not_a_field() -> None:
    text = _file(REFINEMENT_FIELDS) + "\nWhy it waits.\n\n**Trigger:** not a field down here\n"
    task = backlog.parse_task("refinements", REFINEMENT_PATH, text)
    assert "Trigger" not in task.fields


def test_a_wrapped_field_keeps_every_line_of_its_value() -> None:
    text = (
        f"# {TITLE}\n\n**Status:** open, waiting for its trigger\n**Area:** brain\n"
        "**Origin:** ADR-0001\n**Trigger:** a coverage failure where the relayed line is\n"
        "not enough to settle whether the compiler moved, which would make\nthe check free\n"
        "\nWhy it waits.\n"
    )
    task = backlog.parse_task("refinements", REFINEMENT_PATH, text)
    assert task.fields["Trigger"] == (
        "a coverage failure where the relayed line is not enough to settle whether the "
        "compiler moved, which would make the check free"
    )


def test_a_wrapped_field_that_is_not_the_last_one_keeps_the_fields_after_it() -> None:
    text = (
        f"# {TITLE}\n\n**Status:** open, actionable\n**Area:** the brain,\nand its ports\n"
        "**Origin:** ADR-0001\n"
    )
    task = backlog.parse_task("refinements", REFINEMENT_PATH, text)
    assert task.fields == {
        "Status": "open, actionable",
        "Area": "the brain, and its ports",
        "Origin": "ADR-0001",
    }


def test_a_continuation_line_is_stripped_before_it_is_joined() -> None:
    fields = {**REFINEMENT_FIELDS, "Origin": "ADR-0001\n    and ADR-0068"}
    task = backlog.parse_task("refinements", REFINEMENT_PATH, _file(fields))
    assert task.fields["Origin"] == "ADR-0001 and ADR-0068"


def test_a_blank_line_ends_the_field_block_rather_than_wrapping_across_it() -> None:
    text = _file(REFINEMENT_FIELDS) + "\nThe body, which is not part of the Origin.\n"
    task = backlog.parse_task("refinements", REFINEMENT_PATH, text)
    assert task.fields == REFINEMENT_FIELDS


def test_prose_where_the_block_should_start_continues_nothing() -> None:
    text = f"# {TITLE}\n\nA body that forgot its fields.\n\n**Status:** open, actionable\n"
    with pytest.raises(backlog.TaskFileError, match="missing required field 'Status'"):
        backlog.parse_task("refinements", REFINEMENT_PATH, text)


def test_a_bold_line_inside_the_block_that_is_not_a_field_is_rejected() -> None:
    text = (
        f"# {TITLE}\n\n**Status:** open, actionable\n**Area:** brain\n**Origin:** ADR-0001\n"
        "**Trigger** the colon is missing\n"
    )
    with pytest.raises(backlog.TaskFileError, match="is not a field line"):
        backlog.parse_task("refinements", REFINEMENT_PATH, text)


def test_a_field_given_twice_is_rejected() -> None:
    text = (
        f"# {TITLE}\n\n**Status:** open, actionable\n**Status:** done 2026-03-04\n"
        "**Area:** brain\n**Origin:** ADR-0001\n"
    )
    with pytest.raises(backlog.TaskFileError, match="field 'Status' is given twice"):
        backlog.parse_task("refinements", REFINEMENT_PATH, text)


@pytest.mark.parametrize(
    ("kind", "path", "drop", "message"),
    [
        ("refinements", REFINEMENT_PATH, "Status", "missing required field 'Status'"),
        ("refinements", REFINEMENT_PATH, "Area", "missing required field 'Area'"),
        ("refinements", REFINEMENT_PATH, "Origin", "missing required field 'Origin'"),
        ("host", HOST_PATH, "Session", "missing required field 'Session'"),
        ("host", HOST_PATH, "Capability", "missing required field 'Capability'"),
    ],
)
def test_a_missing_required_field_is_rejected(
    kind: str, path: Path, drop: str, message: str
) -> None:
    source = REFINEMENT_FIELDS if kind == "refinements" else HOST_FIELDS
    fields = {name: value for name, value in source.items() if name != drop}
    with pytest.raises(backlog.TaskFileError, match=message):
        backlog.parse_task(kind, path, _file(fields, title="Bring the hotkey up"))


@pytest.mark.parametrize(
    ("kind", "path", "fields", "unknown"),
    [
        ("refinements", REFINEMENT_PATH, {**REFINEMENT_FIELDS, "Session": "hotkey"}, "Session"),
        ("refinements", REFINEMENT_PATH, {**REFINEMENT_FIELDS, "Capability": "W"}, "Capability"),
        ("host", HOST_PATH, {**HOST_FIELDS, "Trigger": "a card arrives"}, "Trigger"),
        ("host", HOST_PATH, {**HOST_FIELDS, "Area": "brain"}, "Area"),
    ],
)
def test_a_field_the_kind_does_not_allow_is_rejected(
    kind: str, path: Path, fields: dict[str, str], unknown: str
) -> None:
    with pytest.raises(backlog.TaskFileError, match=rf"unknown field\(s\) \['{unknown}'\]"):
        backlog.parse_task(kind, path, _file(fields, title="Bring the hotkey up"))


@pytest.mark.parametrize(
    ("title", "message"),
    [
        ("Declined: keep the port as it is", "the title states a status"),
        ("The scan is satisfied by the new check", "the title states a status"),
        ("Fix the 2026 regression in the memory port", "the title states a date"),
    ],
)
def test_a_title_that_restates_its_own_status_is_rejected(title: str, message: str) -> None:
    with pytest.raises(backlog.TaskFileError, match=message):
        backlog.parse_task("refinements", REFINEMENT_PATH, _file(REFINEMENT_FIELDS, title=title))


def test_a_title_may_use_the_words_that_are_not_status_verbs() -> None:
    title = "Reopen the closed section once the port is done"
    task = backlog.parse_task("refinements", REFINEMENT_PATH, _file(REFINEMENT_FIELDS, title=title))
    assert task.title == title


@pytest.mark.parametrize("state", sorted(backlog.NEEDS_TRIGGER))
def test_a_waiting_state_without_a_trigger_is_rejected(state: str) -> None:
    fields = {**REFINEMENT_FIELDS, "Status": f"open, {state}"}
    with pytest.raises(backlog.TaskFileError, match="must name the Trigger that would reopen it"):
        backlog.parse_task("refinements", REFINEMENT_PATH, _file(fields))


@pytest.mark.parametrize("state", sorted(backlog.NEEDS_TRIGGER))
def test_a_waiting_state_that_names_its_trigger_passes(state: str) -> None:
    fields = {**REFINEMENT_FIELDS, "Status": f"open, {state}", "Trigger": "a turn drops a memory"}
    task = backlog.parse_task("refinements", REFINEMENT_PATH, _file(fields))
    assert task.fields["Trigger"] == "a turn drops a memory"


def test_a_closed_task_may_not_keep_its_trigger() -> None:
    fields = {**REFINEMENT_FIELDS, "Status": "done 2026-03-04", "Trigger": "a turn drops one"}
    with pytest.raises(backlog.TaskFileError, match="a closed task may not have a Trigger"):
        backlog.parse_task("refinements", REFINEMENT_PATH, _file(fields))


def test_an_open_task_that_waits_on_nothing_may_still_have_a_trigger() -> None:
    fields = {**REFINEMENT_FIELDS, "Trigger": "a second adapter arrives"}
    task = backlog.parse_task("refinements", REFINEMENT_PATH, _file(fields))
    assert task.fields["Trigger"] == "a second adapter arrives"


def test_a_verified_line_keeps_the_day_the_claim_was_read() -> None:
    fields = {**REFINEMENT_FIELDS, "Verified": "2026-09-09"}
    task = backlog.parse_task("refinements", REFINEMENT_PATH, _file(fields))
    assert task.fields["Verified"] == "2026-09-09"


@pytest.mark.parametrize("value", ["yesterday", "2026-13-09", "09-09-2026", "2026-09-09 by hand"])
def test_a_verified_line_that_is_not_a_date_is_rejected(value: str) -> None:
    fields = {**REFINEMENT_FIELDS, "Verified": value}
    with pytest.raises(backlog.TaskFileError, match="needs a real YYYY-MM-DD date"):
        backlog.parse_task("refinements", REFINEMENT_PATH, _file(fields))


def test_a_bad_verified_date_is_reported_against_its_own_line() -> None:
    fields = {**REFINEMENT_FIELDS, "Verified": "2026-13-09"}
    with pytest.raises(backlog.TaskFileError, match=r"the Verified line '2026-13-09' needs a real"):
        backlog.parse_task("refinements", REFINEMENT_PATH, _file(fields))


def test_a_date_in_the_future_is_accepted() -> None:
    fields = {**REFINEMENT_FIELDS, "Verified": "2099-01-01"}
    task = backlog.parse_task("refinements", REFINEMENT_PATH, _file(fields))
    assert task.fields["Verified"] == "2099-01-01"


@pytest.mark.parametrize(
    ("kind", "path", "source", "closed"),
    [
        ("refinements", REFINEMENT_PATH, REFINEMENT_FIELDS, "done 2026-03-04"),
        ("host", HOST_PATH, HOST_FIELDS, "done 2026-03-04"),
    ],
)
def test_a_closed_task_may_not_have_a_verified_date(
    kind: str, path: Path, source: dict[str, str], closed: str
) -> None:
    fields = {**source, "Status": closed, "Verified": "2026-03-04"}
    with pytest.raises(backlog.TaskFileError, match="a closed task may not have a Verified date"):
        backlog.parse_task(kind, path, _file(fields, title="Bring the hotkey up"))


@pytest.mark.parametrize("status", ["never attempted", "attempted 2026-03-04, inconclusive: busy"])
def test_a_host_task_records_the_day_the_code_half_of_its_claim_was_read(status: str) -> None:
    fields = {**HOST_FIELDS, "Status": status, "Verified": "2026-09-11"}
    task = backlog.parse_task("host", HOST_PATH, _file(fields, title="Bring the hotkey up"))
    assert task.fields["Verified"] == "2026-09-11"


def test_an_ongoing_task_may_not_have_a_verified_date() -> None:
    fields = {**HOST_FIELDS, "Status": "ongoing: watched over months", "Verified": "2026-09-11"}
    with pytest.raises(backlog.TaskFileError, match="an ongoing task may not have a Verified"):
        backlog.parse_task("host", HOST_PATH, _file(fields, title="Bring the hotkey up"))


@pytest.mark.parametrize("capability", backlog.CAPABILITIES)
def test_each_capability_the_host_backlog_knows_passes(capability: str) -> None:
    fields = {**HOST_FIELDS, "Capability": capability}
    task = backlog.parse_task("host", HOST_PATH, _file(fields, title="Bring the hotkey up"))
    assert task.fields["Capability"] == capability


def test_a_capability_outside_the_roster_is_rejected() -> None:
    fields = {**HOST_FIELDS, "Capability": "GPU"}
    with pytest.raises(backlog.TaskFileError, match="capability 'GPU' is not one of"):
        backlog.parse_task("host", HOST_PATH, _file(fields, title="Bring the hotkey up"))


def test_load_reads_a_directory_in_number_order(tmp_path: Path) -> None:
    _write(tmp_path, "002-second-one.md", _file(REFINEMENT_FIELDS, title="Second"))
    _write(tmp_path, "001-first-one.md", _file(REFINEMENT_FIELDS, title="First"))
    tasks = backlog.load(tmp_path, "refinements")
    assert [task.ident for task in tasks] == ["R-001", "R-002"]
    assert [task.title for task in tasks] == ["First", "Second"]


def test_load_of_an_empty_directory_returns_no_tasks(tmp_path: Path) -> None:
    assert backlog.load(tmp_path, "refinements") == []


def test_load_reads_only_the_markdown_files(tmp_path: Path) -> None:
    _write(tmp_path, "001-first-one.md", _file(REFINEMENT_FIELDS))
    _write(tmp_path, "notes.txt", "not a task file at all\n")
    assert [task.ident for task in backlog.load(tmp_path, "refinements")] == ["R-001"]


def test_load_names_the_file_a_problem_came_from(tmp_path: Path) -> None:
    _write(tmp_path, "001-fine-one.md", _file(REFINEMENT_FIELDS))
    _write(tmp_path, "003-broken.md", _file({**REFINEMENT_FIELDS, "Status": "in progress"}))
    named = r"003-broken\.md: unknown status 'in progress'"
    with pytest.raises(backlog.TaskFileError, match=named):
        backlog.load(tmp_path, "refinements")


def test_load_rejects_a_number_used_twice(tmp_path: Path) -> None:
    _write(tmp_path, "001-first-one.md", _file(REFINEMENT_FIELDS))
    _write(tmp_path, "001-second-one.md", _file(REFINEMENT_FIELDS))
    with pytest.raises(backlog.TaskFileError, match=r"001-second-one\.md: number 001 is already"):
        backlog.load(tmp_path, "refinements")


def test_load_reports_a_directory_named_like_a_task_file(tmp_path: Path) -> None:
    (tmp_path / "001-first-one.md").mkdir()
    with pytest.raises(backlog.TaskFileError, match="cannot be read as a task file"):
        backlog.load(tmp_path, "refinements")


def test_load_reports_a_file_that_is_not_utf8(tmp_path: Path) -> None:
    (tmp_path / "001-first-one.md").write_bytes(b"# T\n\n**Status:** open, \xff\xfe\n")
    with pytest.raises(backlog.TaskFileError, match="cannot be read as a task file"):
        backlog.load(tmp_path, "refinements")
