"""Behaviour of the gate holding a document's roster to the set it describes.

The fixture is a miniature of the real thing: one page carrying one bulleted roster, one Rust
suite the roster is about. Every mutation below is an edit somebody could really make to one side
and forget on the other, which is the whole reason this gate exists: a check lands in a suite no
gate runs and the sentence describing that suite is two trees away.

The last tests run the gate over the committed tree, where the rosters hold or the fixtures are
testing the gate against itself.
"""

import re
from pathlib import Path

import pytest

import rostercheck
import rostermembers
import rosternames
import rosters
from rostercheck import Fault, RosterCheckError, check, check_one, main
from rosternames import Bare, Bulleted, Spelled
from rosters import Roster

REPO_ROOT = Path(__file__).resolve().parents[2]

DOCUMENT = Path("docs/modules/body-rpc.md")

SUITE = """\
//! Live seam checks.

#[tokio::test]
#[ignore = "live seam check: needs a real brain"]
async fn the_brain_answers() {
    assert!(true);
}

#[tokio::test]
#[ignore = "live seam check: needs no brain"]
async fn the_probe_gives_up() {
    assert!(true);
}
"""

PAGE = """\
# body/crates/rpc (`body_rpc`)

**Live checks** (the Rust `integration` suite). The roster below is every one of them:

- `the_brain_answers` calls `Health` and asserts `ready`.
- `the_probe_gives_up` dials a dead address and stays inside its budget.

Being ignored, they never run in CI and never count toward coverage.
"""

LIVE = Roster(
    label="the live seam checks",
    document=DOCUMENT,
    opens="**Live checks**",
    closes="Being ignored, they never run in CI",
    written=Bulleted(),
    subject="an ignored test in body/crates/rpc/tests/live.rs",
    why="the live suite is the one suite no gate runs",
    members=rostermembers.live_seam_checks,
)


def repo(root: Path, *, page: str = PAGE, suite: str = SUITE) -> Path:
    """Write a miniature repo: one page with a roster, one suite the roster is about."""
    document = root / DOCUMENT
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text(page, encoding="utf-8")
    source = root / rostermembers.LIVE_SEAM
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(suite, encoding="utf-8")
    return root


def faults(root: Path, roster: Roster = LIVE) -> list[Fault]:
    """Every fault one roster produces over ``root``."""
    return check_one(root, roster)[1]


def detail(root: Path, roster: Roster = LIVE) -> str:
    """The one fault the fixture produces, asserted to be one so a miscount cannot pass."""
    found = faults(root, roster)
    assert len(found) == 1
    return found[0].detail


# ── the agreement it is written to hold ────────────────────────────────────────


def test_a_roster_that_names_the_set_it_describes_is_clean(tmp_path: Path) -> None:
    assert faults(repo(tmp_path)) == []


def test_a_check_the_suite_gained_and_the_roster_did_not_is_caught(tmp_path: Path) -> None:
    """The defect this gate is named for, and the one observed here more than once."""
    grown = SUITE + '\n#[ignore = "live seam check"]\nasync fn the_token_is_refused() {}\n'
    assert detail(repo(tmp_path, suite=grown)).startswith(
        "the_token_is_refused is an ignored test in body/crates/rpc/tests/live.rs and the "
        "roster does not name it"
    )


def test_a_check_the_roster_kept_after_a_rename_is_caught(tmp_path: Path) -> None:
    """The other direction: the reader is sent looking for something that is gone."""
    renamed = SUITE.replace("the_probe_gives_up", "the_probe_trims_its_attempts")
    found = [fault.detail for fault in faults(repo(tmp_path, suite=renamed))]
    assert len(found) == 2
    # A rename is one edit and reads as two faults, in the order the gate reports them: what
    # the suite holds and the page does not, then what the page names and the suite does not.
    assert found[0].startswith("the_probe_trims_its_attempts is an ignored test")
    assert found[1].startswith("the roster names the_probe_gives_up, which is not an ignored test")


def test_every_fault_carries_the_reason_the_two_sides_must_agree(tmp_path: Path) -> None:
    """A fault that only says two lists differ leaves the reader to work out why it matters."""
    trimmed = PAGE.replace("- `the_probe_gives_up` dials a dead address and stays inside its", "")
    assert detail(repo(tmp_path, page=trimmed)).endswith(
        "the live suite is the one suite no gate runs"
    )


def test_a_fault_names_the_document_and_the_roster_it_is_against(tmp_path: Path) -> None:
    trimmed = PAGE.replace("- `the_probe_gives_up` dials a dead address and stays inside its", "")
    fault = faults(repo(tmp_path, page=trimmed))[0]
    assert (fault.document, fault.label) == (DOCUMENT.as_posix(), "the live seam checks")


# ── the prose the gate deliberately leaves alone ───────────────────────────────


def test_the_sentence_beside_a_name_may_say_anything(tmp_path: Path) -> None:
    """Holding the prose would destroy the thing the roster is for, so it is not held."""
    rewritten = PAGE.replace(
        "calls `Health` and asserts `ready`",
        "proves the brain is up, which is the first thing to check and the cheapest",
    )
    assert faults(repo(tmp_path, page=rewritten)) == []


def test_the_order_the_roster_writes_its_names_in_is_free(tmp_path: Path) -> None:
    """A document orders its list to read well; the suite orders its file to compile."""
    reversed_page = PAGE.replace(
        "- `the_brain_answers` calls `Health` and asserts `ready`.\n"
        "- `the_probe_gives_up` dials a dead address and stays inside its budget.\n",
        "- `the_probe_gives_up` dials a dead address and stays inside its budget.\n"
        "- `the_brain_answers` calls `Health` and asserts `ready`.\n",
    )
    assert faults(repo(tmp_path, page=reversed_page)) == []


def test_no_count_is_held_against_the_roster(tmp_path: Path) -> None:
    """A tally beside a list is the half that drifts first, so the gate does not read one."""
    tallied = PAGE.replace("The roster below is every one of them", "Nine of them, all told")
    assert faults(repo(tmp_path, page=tallied)) == []


# ── the names one half of a paragraph borrows from the other ──────────────────

CONTRACT = Path("docs/modules/repo-gates.md")

HALVES = """\
# scripts/ (`repo-gates`)

**Public contract** (all are CLIs, with `linecap.py` invoked by a `just` recipe).
**The rest have no CLI of their own**, two modules: `skippeddirs.py` is what `linecap.py` skips
and `values.py` is what it counts.

- `linecap.py [--root DIR]` implements AGENTS.md gate 1.
"""

LIBRARIES = Roster(
    label="the modules this tree only reads",
    document=CONTRACT,
    opens="**The rest have no CLI of their own**",
    closes="implements AGENTS.md gate 1",
    written=Spelled(pattern=re.compile(r"[a-z_]+\.py")),
    subject="a module in scripts/ with no command line",
    why="a module in the wrong half is described as something it is not",
    members=rostermembers.library_gate_modules,
    refers_to=rostermembers.cli_gate_modules,
)

GUARD = '"""A miniature."""\n\n\nif __name__ == "__main__":\n    main()\n'


def contract(root: Path, *, page: str = HALVES, runs: str = "linecap.py") -> Path:
    """Write a miniature contract beside a `scripts/` where ``runs`` is its only CLI."""
    document = root / CONTRACT
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text(page, encoding="utf-8")
    tree = root / rostermembers.GATES
    tree.mkdir(parents=True, exist_ok=True)
    (tree / runs).write_text(GUARD, encoding="utf-8")
    for name in ("skippeddirs.py", "values.py"):
        (tree / name).write_text('"""A miniature."""\n', encoding="utf-8")
    return root


def test_a_name_the_sibling_roster_owns_is_a_reference_and_not_a_fault(tmp_path: Path) -> None:
    """The sentence says whose reader a module is, and it says it with the other half's name."""
    assert faults(contract(tmp_path), LIBRARIES) == []


def test_a_name_no_roster_owns_is_still_reported(tmp_path: Path) -> None:
    """The allowance is one named set, not an amnesty on every name the passage carries."""
    invented = HALVES.replace("what `linecap.py` skips", "what `dashcheck.py` skips")
    assert detail(contract(tmp_path, page=invented), LIBRARIES).startswith(
        "the roster names dashcheck.py, which is not a module in scripts/ with no command line"
    )


def test_a_member_missing_from_a_borrowing_roster_is_still_reported(tmp_path: Path) -> None:
    """Membership is held in both halves; only the naming direction takes the allowance."""
    silent = HALVES.replace("`skippeddirs.py` is what `linecap.py` skips", "nothing to speak of")
    assert detail(contract(tmp_path, page=silent), LIBRARIES).startswith(
        "skippeddirs.py is a module in scripts/ with no command line and the roster does not name"
    )


def every_module(root: Path) -> frozenset[str]:
    """A borrowed set overlapping the roster's own members, which no registry here would write."""
    return rostermembers.gate_modules(root)


def test_a_borrowed_name_that_is_also_a_member_is_still_owed(tmp_path: Path) -> None:
    """Borrowing widens what a passage may NAME and never what it may leave out.

    The two halves of the real contract are disjoint by construction, a module either carrying a
    main guard or not, so nothing in the tree can tell the two rules apart. A registry that
    borrowed a set overlapping its own members could, and the direction it would forgive is the
    one that matters: a member nobody named.
    """
    silent = HALVES.replace("`skippeddirs.py` is what `linecap.py` skips", "nothing to speak of")
    overlapping = LIBRARIES._replace(refers_to=every_module)
    assert detail(contract(tmp_path, page=silent), overlapping).startswith(
        "skippeddirs.py is a module in scripts/ with no command line and the roster does not name"
    )


def test_a_module_that_gained_a_cli_and_stayed_put_reddens_the_half_that_lost_it(
    tmp_path: Path,
) -> None:
    """The defect the split exists for, and the reason the allowance leaves no hole.

    `skippeddirs.py` grows a command line and the paragraph is not touched. The half it is named
    in accepts it as a reference, exactly as designed, and the half it has moved into reports it
    as a member nobody named, which is the fault a reader needs.
    """
    root = contract(tmp_path)
    (root / rostermembers.GATES / "skippeddirs.py").write_text(GUARD, encoding="utf-8")
    clis = LIBRARIES._replace(
        label="the modules this tree runs from a shell",
        opens="**Public contract**",
        closes="**The rest have no CLI of their own**",
        subject="a module in scripts/ with a command line of its own",
        members=rostermembers.cli_gate_modules,
        refers_to=None,
    )
    assert faults(root, LIBRARIES) == []
    assert detail(root, clis).startswith(
        "skippeddirs.py is a module in scripts/ with a command line of its own and the roster "
        "does not name it"
    )


def test_a_set_a_roster_refers_to_that_cannot_be_read_is_an_input_failure(tmp_path: Path) -> None:
    """The borrowed set is read from the tree like any other, so it fails by the same door."""
    root = contract(tmp_path)
    (root / rostermembers.GATES / "linecap.py").write_text('"""No CLI now."""\n', encoding="utf-8")
    with pytest.raises(RosterCheckError, match="the CLIs in scripts came back empty"):
        check_one(root, LIBRARIES)


# ── the boundaries of a passage, which are part of what a roster claims ────────


def test_a_passage_that_moved_out_from_under_its_phrases_is_one_fault(tmp_path: Path) -> None:
    """Reported rather than thrown, so one run names every roster that moved, not the first.

    One fault and not three: with no passage the comparison is undefined, and reporting both
    members as unnamed would be an accusation the reader would then have to disprove. The
    `detail` helper is what pins the count.
    """
    rewritten = PAGE.replace("**Live checks**", "**Checks against a live brain**")
    assert "opening phrase '**Live checks**' appears 0 time(s)" in detail(
        repo(tmp_path, page=rewritten)
    )


# ── inputs that leave by their own door ────────────────────────────────────────


def test_a_document_that_is_not_there_is_an_input_failure(tmp_path: Path) -> None:
    with pytest.raises(RosterCheckError, match="cannot read docs/modules/body-rpc"):
        check_one(repo(tmp_path).joinpath("nowhere"), LIVE)


def test_a_set_that_cannot_be_read_is_an_input_failure(tmp_path: Path) -> None:
    """A described set that came back empty is not two lists agreeing about nothing."""
    document = tmp_path / DOCUMENT
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text(PAGE, encoding="utf-8")
    with pytest.raises(RosterCheckError, match="cannot read body/crates/rpc/tests/live"):
        check_one(tmp_path, LIVE)


def test_a_registry_holding_no_roster_at_all_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RosterCheckError, match="no roster is registered"):
        check(repo(tmp_path), ())


# ── what one scan reports about itself ─────────────────────────────────────────


def test_a_scan_states_the_collection_its_verdict_is_over(tmp_path: Path) -> None:
    """Three numbers that count different things, so no two of them can be read as one."""
    second = LIVE._replace(label="the same suite, read twice")
    scanned = check(repo(tmp_path), (LIVE, second))
    assert (scanned.rosters, scanned.documents, scanned.members) == (2, 1, 4)


def test_a_scan_over_two_rosters_reports_both(tmp_path: Path) -> None:
    grown = SUITE + '\n#[ignore = "live seam check"]\nasync fn the_token_is_refused() {}\n'
    second = LIVE._replace(label="the same suite, read twice")
    assert len(check(repo(tmp_path, suite=grown), (LIVE, second)).faults) == 2


# ── the CLI ────────────────────────────────────────────────────────────────────


def test_the_cli_passes_over_a_tree_whose_rosters_hold(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--root", str(REPO_ROOT)]) == 0
    assert "rostercheck OK:" in capsys.readouterr().out


def test_the_cli_fails_printing_every_fault(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    grown = SUITE + '\n#[ignore = "live seam check"]\nasync fn the_token_is_refused() {}\n'
    monkeypatch.setattr(rostercheck, "ROSTERS", (LIVE,))
    assert main(["--root", str(repo(tmp_path, suite=grown))]) == 1
    printed = capsys.readouterr()
    assert "the_token_is_refused is an ignored test" in printed.out
    assert "1 roster problem(s)" in printed.err


def test_the_cli_reports_an_unreadable_input_as_a_setup_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rostercheck, "ROSTERS", (LIVE,))
    assert main(["--root", str(tmp_path)]) == 2
    assert "rostercheck: cannot read" in capsys.readouterr().err


def test_the_cli_refuses_a_root_that_is_not_a_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "not-a-tree"
    assert main(["--root", str(missing)]) == 2
    assert "is not a directory" in capsys.readouterr().err


# ── against the tree this gate is written for ──────────────────────────────────


def test_the_repos_own_rosters_hold() -> None:
    """The gate over the committed tree, so `check-scripts` reddens when the recipe is not run."""
    assert check(REPO_ROOT).faults == []


def test_the_scan_roster_is_registered_in_more_than_one_shape() -> None:
    """One set spelled in three documents, which is the entry this registration answers.

    A comment inside a workflow is a roster when it names its members, and the bare shape is what
    reaches it, so dropping that registration would leave the copy nobody was holding unheld
    again while the two prose copies went on passing.
    """
    scans = [
        roster for roster in rosters.ROSTERS if roster.members is rostermembers.cross_tree_scans
    ]
    assert len(scans) > 2
    assert len({roster.document for roster in scans}) == len(scans)
    assert len({type(roster.written) for roster in scans}) > 1


def test_the_repos_own_rosters_are_over_something() -> None:
    """The floor under the test above: three empty comparisons would also report no fault."""
    scanned = check(REPO_ROOT)
    assert scanned.rosters == len(rosters.ROSTERS)
    assert scanned.members > scanned.rosters


def test_the_repo_really_writes_a_roster_in_every_shape() -> None:
    """A spelling nothing in the tree uses is a rule that cannot redden, so all three are pinned."""
    shapes = {type(roster.written) for roster in rosters.ROSTERS}
    assert shapes == {Bulleted, Spelled, Bare}


def test_the_repo_really_spends_the_allowance_for_a_borrowed_name() -> None:
    """Same floor for the other new rule: an allowance nothing exercises is one nobody keeps."""
    borrowing = [roster for roster in rosters.ROSTERS if roster.refers_to is not None]
    assert borrowing
    for roster in borrowing:
        passage = rosternames.passage(
            (REPO_ROOT / roster.document).read_text(encoding="utf-8"), roster.opens, roster.closes
        )
        named = frozenset(rosternames.names(passage, roster.written))
        assert named - roster.members(REPO_ROOT), roster.label


def test_every_registered_boundary_phrase_is_written_once_in_its_document() -> None:
    """A phrase carried twice is an ambiguous boundary, and one carried never is no boundary."""
    for roster in rosters.ROSTERS:
        text = (REPO_ROOT / roster.document).read_text(encoding="utf-8")
        assert text.count(roster.opens) == 1, roster.label
        assert text.count(roster.closes) == 1, roster.label


def test_no_registered_boundary_phrase_names_a_member() -> None:
    """A roster bounded by one of its own names would be its own far side, and drift with it."""
    for roster in rosters.ROSTERS:
        for member in roster.members(REPO_ROOT):
            assert member not in roster.opens, roster.label
            assert member not in roster.closes, roster.label


def test_every_registered_pattern_refuses_something_the_passage_carries() -> None:
    """A pattern matching every code span would hold the prose, the one thing it must not."""
    for roster in rosters.ROSTERS:
        if not isinstance(roster.written, Spelled):
            continue
        text = (REPO_ROOT / roster.document).read_text(encoding="utf-8")
        spans = {found.group(1) for found in re.finditer(r"`([^`]+)`", text)}
        assert any(roster.written.pattern.fullmatch(span) is None for span in spans), roster.label


def test_every_bare_roster_names_something_no_code_span_would_have_reached() -> None:
    """The shape earns its place only where names are written bare, which is what is pinned here."""
    bare = [roster for roster in rosters.ROSTERS if isinstance(roster.written, Bare)]
    assert bare
    for roster in bare:
        passage = rosternames.passage(
            (REPO_ROOT / roster.document).read_text(encoding="utf-8"), roster.opens, roster.closes
        )
        spanned = {found.group(1) for found in re.finditer(r"`([^`]+)`", passage)}
        assert set(rosternames.names(passage, roster.written)) - spanned, roster.label
