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
import rosters
from rostercheck import Fault, RosterCheckError, check, check_one, main
from rosternames import Bulleted, Spelled
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


def test_the_repos_own_rosters_are_over_something() -> None:
    """The floor under the test above: three empty comparisons would also report no fault."""
    scanned = check(REPO_ROOT)
    assert scanned.rosters == len(rosters.ROSTERS)
    assert scanned.members > scanned.rosters


def test_the_repo_really_writes_a_roster_in_both_shapes() -> None:
    """A spelling nothing in the tree uses is a rule that cannot redden, so both are pinned."""
    shapes = {type(roster.written) for roster in rosters.ROSTERS}
    assert shapes == {Bulleted, Spelled}


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
