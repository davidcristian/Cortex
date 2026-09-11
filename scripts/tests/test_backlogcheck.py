from pathlib import Path

import pytest

import backlog
import backlogcheck
import backlogindex

REFINEMENTS = Path("docs/refinements")
HOST = Path("docs/host")
INDEX = f"# The backlog\n\nHow a person works it.\n\n{backlogindex.BEGIN}\n{backlogindex.END}\n"
REFINEMENT = (
    "# Wire the memory port\n\n"
    "**Status:** open, actionable\n"
    "**Area:** brain\n"
    "**Origin:** ADR-0001\n"
)
HOST_TASK = (
    "# Bring the hotkey up\n\n"
    "**Status:** never attempted\n"
    "**Sitting:** hotkey bring-up\n"
    "**Capability:** W\n"
    "**Origin:** ADR-0003\n"
)


def _write(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _repo(root: Path) -> Path:
    """Build both backlogs, each with one task and an index whose block is still empty."""
    _write(root, "docs/refinements/index.md", INDEX)
    _write(root, "docs/refinements/tasks/001-wire-the-memory-port.md", REFINEMENT)
    _write(root, "docs/host/index.md", INDEX)
    _write(root, "docs/host/tasks/001-bring-the-hotkey-up.md", HOST_TASK)
    return root


# ── a tasks directory holds task files and nothing else ────────────────────────


def test_check_stray_accepts_a_directory_of_task_files(tmp_path: Path) -> None:
    _write(tmp_path, "001-wire-the-memory-port.md", REFINEMENT)
    assert backlogcheck.check_stray(tmp_path) == []


def test_check_stray_names_everything_that_is_not_a_task_file(tmp_path: Path) -> None:
    _write(tmp_path, "001-wire-the-memory-port.md", REFINEMENT)
    _write(tmp_path, "notes.txt", "a note nobody can cite\n")
    _write(tmp_path, "drafts/002-a-draft.md", REFINEMENT)
    problems = backlogcheck.check_stray(tmp_path)
    assert [Path(problem.split(":")[0]).name for problem in problems] == ["drafts", "notes.txt"]
    assert all("task files and nothing else" in problem for problem in problems)


# ── every relative link still resolves ─────────────────────────────────────────


def test_check_links_passes_when_every_relative_link_resolves(tmp_path: Path) -> None:
    task = _write(tmp_path, "tasks/001-wire-the-memory-port.md", REFINEMENT)
    _write(tmp_path, "tasks/002-a-sibling.md", REFINEMENT)
    task.write_text(REFINEMENT + "\nSee [the sibling](002-a-sibling.md).\n", encoding="utf-8")
    index = _write(tmp_path, "index.md", INDEX + "\n[the first](tasks/002-a-sibling.md)\n")
    tasks = backlog.load(tmp_path / "tasks", "refinements")
    sources = [*backlogcheck.task_texts(tasks), (index, index.read_text(encoding="utf-8"))]
    assert backlogcheck.check_links(tmp_path, sources) == []


def test_check_links_resolves_each_link_from_its_own_document(tmp_path: Path) -> None:
    """The same target is one link that resolves and one that does not, by where it is written."""
    task = _write(tmp_path, "tasks/001-wire-the-memory-port.md", REFINEMENT)
    _write(tmp_path, "tasks/002-a-sibling.md", REFINEMENT)
    text = "See [the sibling](002-a-sibling.md).\n"
    assert backlogcheck.check_links(tmp_path, [(task, text), (tmp_path / "index.md", text)]) == [
        "index.md: link '002-a-sibling.md' does not resolve"
    ]


def test_check_links_judges_the_text_it_is_handed_and_not_the_file(tmp_path: Path) -> None:
    """The caller says what text a document is judged as, which for an index is the text a
    write run is about to put on disk rather than the file it replaces."""
    index = _write(tmp_path, "index.md", INDEX + "\nSee [the gone one](tasks/002-gone.md).\n")
    assert backlogcheck.check_links(tmp_path, [(index, INDEX)]) == []
    fresh = INDEX + "\nSee [the other gone one](tasks/003-gone.md).\n"
    assert backlogcheck.check_links(tmp_path, [(index, fresh)]) == [
        "index.md: link 'tasks/003-gone.md' does not resolve"
    ]


# ── one backlog at a time ──────────────────────────────────────────────────────


def test_run_one_reports_a_missing_tasks_directory(tmp_path: Path) -> None:
    _write(tmp_path, "docs/refinements/index.md", INDEX)
    problems, offered = backlogcheck.run_one(
        tmp_path, "refinements", REFINEMENTS, "area", write=False
    )
    assert problems == ["docs/refinements/tasks is missing; the backlog is one file per task"]
    assert offered is None


def test_run_one_reports_a_missing_index(tmp_path: Path) -> None:
    _write(tmp_path, "docs/refinements/tasks/001-wire-the-memory-port.md", REFINEMENT)
    problems, offered = backlogcheck.run_one(
        tmp_path, "refinements", REFINEMENTS, "area", write=False
    )
    assert problems == ["docs/refinements/index.md is missing"]
    assert offered is None


def test_run_one_reports_a_task_file_outside_the_layout(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _write(root, "docs/refinements/tasks/002-broken.md", REFINEMENT.replace("actionable", "soon"))
    problems, offered = backlogcheck.run_one(root, "refinements", REFINEMENTS, "area", write=False)
    assert len(problems) == 1
    assert "unknown open state 'soon'" in problems[0]
    assert offered is None


def test_run_one_reports_both_a_stray_entry_and_the_task_it_broke(tmp_path: Path) -> None:
    """The stray scan runs first, so its finding survives the parse failure that follows."""
    root = _repo(tmp_path)
    _write(root, "docs/refinements/tasks/notes.txt", "a note\n")
    (root / REFINEMENTS / "tasks" / "002-a-folder.md").mkdir()
    problems, _ = backlogcheck.run_one(root, "refinements", REFINEMENTS, "area", write=False)
    assert len(problems) == 3
    assert sum("task files and nothing else" in problem for problem in problems) == 2
    assert any("cannot be read as a task file" in problem for problem in problems)


def test_run_one_reports_a_stale_index(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    problems, offered = backlogcheck.run_one(root, "refinements", REFINEMENTS, "area", write=False)
    assert problems == [
        "docs/refinements/index.md is out of date with its 1 task files; run `just backlog`"
    ]
    assert offered is not None
    assert "actionable-now-1" in offered


def test_run_one_rewrites_a_stale_index_when_asked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    assert backlogcheck.run_one(root, "refinements", REFINEMENTS, "area", write=True)[0] == []
    written = (root / REFINEMENTS / "index.md").read_text(encoding="utf-8")
    assert "How a person works it." in written
    assert "**1 open, 0 closed, 1 in total.**" in written
    assert "rewrote docs/refinements/index.md" in capsys.readouterr().out


def test_run_one_is_clean_once_the_index_matches(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    backlogcheck.run_one(root, "refinements", REFINEMENTS, "area", write=True)
    capsys.readouterr()
    assert backlogcheck.run_one(root, "refinements", REFINEMENTS, "area", write=False)[0] == []
    assert "docs/refinements has 1 tasks, 1 open" in capsys.readouterr().out


def test_run_one_reports_an_index_without_its_markers(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _write(root, "docs/refinements/index.md", "# The backlog\n\nProse, and no markers.\n")
    problems, offered = backlogcheck.run_one(root, "refinements", REFINEMENTS, "area", write=True)
    assert len(problems) == 1
    assert "docs/refinements/index.md: the index needs both" in problems[0]
    assert offered is None


def test_run_one_reports_a_link_that_stopped_resolving(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    task = root / REFINEMENTS / "tasks" / "001-wire-the-memory-port.md"
    task.write_text(REFINEMENT + "\nSee [the sibling](002-moved-away.md).\n", encoding="utf-8")
    problems, _ = backlogcheck.run_one(root, "refinements", REFINEMENTS, "area", write=True)
    assert problems == [
        "docs/refinements/tasks/001-wire-the-memory-port.md: "
        "link '002-moved-away.md' does not resolve"
    ]


def test_run_one_accepts_a_link_that_climbs_out_of_the_backlog(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _write(root, "docs/adr/ADR-0001-architecture.md", "# The decision\n")
    task = root / REFINEMENTS / "tasks" / "001-wire-the-memory-port.md"
    task.write_text(
        REFINEMENT + "\nSee [the decision](../../adr/ADR-0001-architecture.md#decision-7).\n",
        encoding="utf-8",
    )
    assert backlogcheck.run_one(root, "refinements", REFINEMENTS, "area", write=True)[0] == []


# ── the gate, end to end ───────────────────────────────────────────────────────


def test_main_fails_on_a_stale_index_then_writes_it_then_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    assert backlogcheck.main(["--root", str(root)]) == 1
    reported = capsys.readouterr().err
    assert "docs/refinements/index.md is out of date" in reported
    assert "docs/host/index.md is out of date" in reported
    assert "backlogcheck: 2 problem(s)" in reported

    assert backlogcheck.main(["--root", str(root), "--write"]) == 0
    refinements = (root / REFINEMENTS / "index.md").read_bytes()
    host = (root / HOST / "index.md").read_bytes()
    entry = b"- **[R-001](tasks/001-wire-the-memory-port.md)** Wire the memory port (brain)."
    roll = b"- [H-001](tasks/001-bring-the-hotkey-up.md) Bring the hotkey up. never attempted."
    assert b"**1 open, 0 closed, 1 in total.**" in refinements
    assert b"### Actionable now (1)" in refinements
    assert entry in refinements
    assert b"### Never attempted (1)" in host
    assert roll in host

    assert backlogcheck.main(["--root", str(root)]) == 0
    assert "backlogcheck OK" in capsys.readouterr().out
    assert backlogcheck.main(["--root", str(root), "--write"]) == 0
    assert (root / REFINEMENTS / "index.md").read_bytes() == refinements
    assert (root / HOST / "index.md").read_bytes() == host


def test_main_judges_the_index_links_on_the_text_the_write_run_puts_on_disk(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A trigger's link resolves from the task file and not from the index that renders it.

    The write run that puts the link into the index reports it, once, and the write run that
    takes it out again passes: each verdict is about the file the run leaves behind. Judging
    the file on disk before the rewrite gave the opposite pair, a pass for the run that wrote
    the broken link and a failure for the run that removed it.
    """
    root = _repo(tmp_path)
    _write(root, "docs/refinements/tasks/002-a-sibling.md", REFINEMENT)
    task = root / REFINEMENTS / "tasks" / "001-wire-the-memory-port.md"
    waiting = REFINEMENT.replace("open, actionable", "open, fix when it bites")
    task.write_text(waiting + "**Trigger:** [the sibling](002-a-sibling.md) lands.\n")
    assert backlogcheck.main(["--root", str(root), "--write"]) == 1
    reported = capsys.readouterr().err
    assert reported.count("does not resolve") == 1
    assert "docs/refinements/index.md: link '002-a-sibling.md' does not resolve" in reported
    assert "[the sibling](002-a-sibling.md)" in (root / REFINEMENTS / "index.md").read_text()

    task.write_text(waiting + "**Trigger:** the sibling lands.\n")
    assert backlogcheck.main(["--root", str(root), "--write"]) == 0
    assert "does not resolve" not in capsys.readouterr().err
    assert backlogcheck.main(["--root", str(root)]) == 0


def test_main_reports_a_new_task_as_a_stale_index(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A task file arrives, so the index describing the set of tasks is now out of date."""
    root = _repo(tmp_path)
    assert backlogcheck.main(["--root", str(root), "--write"]) == 0
    _write(root, "docs/refinements/tasks/002-split-the-module.md", REFINEMENT)
    capsys.readouterr()
    assert backlogcheck.main(["--root", str(root)]) == 1
    assert "out of date with its 2 task files" in capsys.readouterr().err


def test_main_reports_a_pointer_left_aimed_at_a_renamed_area(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The gate's other half: the link still resolves and the heading it aims at is gone."""
    root = _repo(tmp_path)
    _write(root, "docs/adr/ADR-0001.md", "See [the area](../refinements/index.md#brain).\n")
    assert backlogcheck.main(["--root", str(root), "--write"]) == 0
    capsys.readouterr()
    task = root / REFINEMENTS / "tasks" / "001-wire-the-memory-port.md"
    task.write_text(REFINEMENT.replace("**Area:** brain", "**Area:** brain-core"), encoding="utf-8")
    assert backlogcheck.main(["--root", str(root), "--write"]) == 1
    reported = capsys.readouterr().err
    assert "docs/adr/ADR-0001.md:1: pointer '../refinements/index.md#brain' aims at a heading" in (
        reported
    )
    assert "docs/refinements/index.md does not render" in reported


def test_main_judges_no_pointer_at_a_backlog_whose_index_it_could_not_render(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With the markers gone there is no rendering to judge against, so only that is reported.

    The stale file on disk still renders `### brain`, so what keeps the widened scan from
    answering out of it is the index being registered as unjudgeable for this run.
    """
    root = _repo(tmp_path)
    _write(root, "docs/adr/ADR-0001.md", "See [the area](../refinements/index.md#brain).\n")
    _write(root, "docs/refinements/index.md", "# The backlog\n\nProse, and no markers.\n")
    assert backlogcheck.main(["--root", str(root), "--write"]) == 1
    reported = capsys.readouterr().err
    assert "docs/refinements/index.md: the index needs both" in reported
    assert "aims at a heading" not in reported


def test_main_reports_a_pointer_left_aimed_at_a_renamed_heading_in_any_document(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The scan reaches beyond the two indexes: the target here is an ordinary decision record."""
    root = _repo(tmp_path)
    _write(root, "docs/adr/ADR-0001.md", "# The decision\n\n## Risks flagged for user review\n")
    task = root / REFINEMENTS / "tasks" / "001-wire-the-memory-port.md"
    task.write_text(
        REFINEMENT + "\nSee [the risks](../../adr/ADR-0001.md#risks-flagged-for-user-review).\n",
        encoding="utf-8",
    )
    assert backlogcheck.main(["--root", str(root), "--write"]) == 0
    _write(
        root, "docs/adr/ADR-0001.md", "# The decision\n\n## Risks flagged for maintainer review\n"
    )
    capsys.readouterr()
    assert backlogcheck.main(["--root", str(root)]) == 1
    assert (
        "docs/refinements/tasks/001-wire-the-memory-port.md:7: pointer "
        "'../../adr/ADR-0001.md#risks-flagged-for-user-review' aims at a heading "
        "docs/adr/ADR-0001.md does not offer"
    ) in capsys.readouterr().err


def test_main_rejects_a_root_that_is_not_a_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(tmp_path, "a-file.md", "x\n")
    assert backlogcheck.main(["--root", str(path)]) == 2
    assert "is not a directory" in capsys.readouterr().err


def test_main_defaults_to_the_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    assert backlogcheck.main(["--write"]) == 0
    assert backlogcheck.main([]) == 0
