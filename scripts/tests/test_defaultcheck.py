from pathlib import Path

import pytest

import defaultcheck
from composedefaults import Substitution
from defaultcheck import Spend

REPO_ROOT = Path(__file__).resolve().parents[2]


def _compose(root: Path, body: str, name: str = "docker-compose.yml") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _environment(*spends: str) -> str:
    lines = "\n".join(f'      VAR_{index}: "{spend}"' for index, spend in enumerate(spends))
    return f"services:\n  brain:\n    environment:\n{lines}\n"


def test_a_whole_number_spelled_two_ways_is_one_value(tmp_path: Path) -> None:
    _compose(tmp_path, _environment("${MEM_BUDGET_GB:-8.0}", "${MEM_BUDGET_GB:-8}g"))
    assert defaultcheck.check(tmp_path).faults == []


def test_a_real_drift_in_that_same_variable_is_reported(tmp_path: Path) -> None:
    _compose(tmp_path, _environment("${MEM_BUDGET_GB:-8.0}", "${MEM_BUDGET_GB:-9}g"))
    faults = defaultcheck.check(tmp_path).faults
    assert [fault.subject for fault in faults] == ["MEM_BUDGET_GB"]
    assert "does not have one default" in faults[0].detail
    assert "${MEM_BUDGET_GB:-8.0}" in faults[0].detail
    assert "${MEM_BUDGET_GB:-9}" in faults[0].detail


def test_a_fraction_that_is_lost_rather_than_zero_is_not_a_re_spelling(tmp_path: Path) -> None:
    _compose(tmp_path, _environment("${MEM_BUDGET_GB:-8.5}", "${MEM_BUDGET_GB:-8}g"))
    assert [fault.subject for fault in defaultcheck.check(tmp_path).faults] == ["MEM_BUDGET_GB"]


def test_one_default_written_the_same_way_twice_holds(tmp_path: Path) -> None:
    _compose(tmp_path, _environment("${PG_PASSWORD:-cortex}", "pg://x:${PG_PASSWORD:-cortex}@y"))
    assert defaultcheck.check(tmp_path).faults == []


def test_a_drift_across_two_files_names_both(tmp_path: Path) -> None:
    _compose(tmp_path, _environment("${MODELS_DIR:-./models}"), name="docker/docker-compose.yml")
    _compose(tmp_path, _environment("${MODELS_DIR:-./cache}"), name="docker/docker-compose.gpu.yml")
    faults = defaultcheck.check(tmp_path).faults
    assert len(faults) == 1
    assert "docker/docker-compose.gpu.yml:4" in faults[0].detail
    assert "docker/docker-compose.yml:4" in faults[0].detail


def test_a_spend_with_no_sibling_is_never_compared(tmp_path: Path) -> None:
    _compose(tmp_path, _environment("${ENDPOINT:-http://llama-subagent:8082}"))
    assert defaultcheck.check(tmp_path).faults == []


def test_an_empty_default_beside_a_filled_one_is_a_drift(tmp_path: Path) -> None:
    _compose(tmp_path, _environment("${CA_CERT:-}", "${CA_CERT:-/etc/ssl/bridge.pem}"))
    assert [fault.subject for fault in defaultcheck.check(tmp_path).faults] == ["CA_CERT"]


def test_two_empty_defaults_agree(tmp_path: Path) -> None:
    _compose(tmp_path, _environment("${CA_CERT:-}", "${CA_CERT:-}"))
    assert defaultcheck.check(tmp_path).faults == []


def test_falling_back_two_different_ways_is_a_drift(tmp_path: Path) -> None:
    _compose(tmp_path, _environment("${MODELS_DIR:-./models}", "${MODELS_DIR-./models}"))
    faults = defaultcheck.check(tmp_path).faults
    assert [fault.subject for fault in faults] == ["MODELS_DIR"]
    assert "different fallback operators" in faults[0].detail


def test_one_file_demanding_what_another_supplies_is_a_drift(tmp_path: Path) -> None:
    _compose(tmp_path, _environment("${IMAP_USER:?set the Bridge username}", "${IMAP_USER:-x}"))
    assert "different fallback operators" in defaultcheck.check(tmp_path).faults[0].detail


def test_two_required_spends_may_word_their_message_differently(tmp_path: Path) -> None:
    _compose(tmp_path, _environment("${IMAP_USER:?set the username}", "${IMAP_USER:?see runbook}"))
    assert defaultcheck.check(tmp_path).faults == []


def test_two_spends_carrying_no_default_at_all_agree(tmp_path: Path) -> None:
    _compose(tmp_path, _environment("${SEAM_TOKEN}", "${SEAM_TOKEN}"))
    assert defaultcheck.check(tmp_path).faults == []


@pytest.mark.parametrize(
    ("arguments", "agree"),
    [
        (["./models", "./models"], True),
        (["8.0", "8"], True),
        (["8.0", "8", "8.00"], True),
        (["2", "2.0"], True),
        (["8.0", "9"], False),
        (["8.5", "8"], False),
        (["./models", "./cache"], False),
        (["cortex", "8"], False),
        (["", "x"], False),
    ],
)
def test_same_value_allows_a_re_spelling_and_nothing_else(
    arguments: list[str], *, agree: bool
) -> None:
    assert defaultcheck.same_value(arguments) is agree


def test_a_spend_prints_as_the_place_and_the_text() -> None:
    spend = Spend(path="docker/docker-compose.yml", substitution=Substitution(4, "V", ":-", "8.0"))
    assert str(spend) == "docker/docker-compose.yml:4 ${V:-8.0}"


def test_a_tree_with_no_compose_file_is_a_failure_not_a_pass(tmp_path: Path) -> None:
    with pytest.raises(defaultcheck.ComposeSearchError, match="matched nothing cannot fail"):
        defaultcheck.check(tmp_path)


def test_a_form_the_reader_refuses_is_a_refused_file_not_a_disagreement(tmp_path: Path) -> None:
    _compose(tmp_path, _environment("${OUTER:-${INNER}}"))
    scanned = defaultcheck.check(tmp_path)
    assert [fault.subject for fault in scanned.refused] == ["docker-compose.yml"]
    assert scanned.refused[0].detail.startswith("line 4: nested substitution ${OUTER:-${INNER}}, ")
    assert scanned.disagreements == []


def test_a_compose_file_that_is_not_text_is_a_fault(tmp_path: Path) -> None:
    (tmp_path / "docker-compose.yml").write_bytes(b"\xff\xfe not utf-8")
    assert len(defaultcheck.check(tmp_path).faults) == 1


def _both(root: Path) -> None:
    """Write one file the reader cannot decode and one whose variable has two different defaults."""
    _compose(root, _environment("${OUTER:-${INNER}}"), name="docker-compose.bad.yml")
    _compose(root, _environment("${DIR:-./a}", "${DIR:-./b}"))


def test_an_unreadable_file_does_not_stop_the_scan(tmp_path: Path) -> None:
    _both(tmp_path)
    scanned = defaultcheck.check(tmp_path)
    assert [fault.subject for fault in scanned.refused] == ["docker-compose.bad.yml"]
    assert [fault.subject for fault in scanned.disagreements] == ["DIR"]
    assert scanned.faults == scanned.refused + scanned.disagreements


def test_the_repo_itself_carries_one_default_per_variable() -> None:
    assert defaultcheck.check(REPO_ROOT).faults == []


def test_the_repo_really_spells_variables_more_than_once() -> None:
    walk = defaultcheck.group(REPO_ROOT)
    assert walk.faults == []
    repeated = {name: spends for name, spends in walk.groups.items() if len(spends) > 1}
    assert len(repeated) >= 6, sorted(walk.groups)


def test_the_repo_really_spells_one_value_two_ways() -> None:
    respelled = {
        name
        for name, spends in defaultcheck.group(REPO_ROOT).groups.items()
        if len({spend.substitution.argument for spend in spends}) > 1
    }
    assert respelled == {"CORTEX_SUBAGENTS_MEM_BUDGET_GB"}


def test_main_passes_the_real_repo(capsys: pytest.CaptureFixture[str]) -> None:
    assert defaultcheck.main(["--root", str(REPO_ROOT)]) == 0
    assert "defaultcheck OK" in capsys.readouterr().out


def _counted(root: Path) -> None:
    """Write three files with five variables, two of them compared, so the three counts differ."""
    _compose(root, _environment("${DIR:-./a}", "${DIR:-./a}", "${PORT:-8080}"))
    _compose(root, _environment("${PORT:-8080}", "${HOST:-x}"), name="docker/compose.gpu.yml")
    _compose(root, _environment("${TOKEN}", "${SEED:-1}"), name="docker/docker-compose.email.yml")


def test_check_counts_the_files_variables_and_comparisons(tmp_path: Path) -> None:
    _counted(tmp_path)
    scanned = defaultcheck.check(tmp_path)
    assert (scanned.files, scanned.variables, scanned.compared) == (3, 5, 2)
    assert scanned.faults == []


def test_main_states_what_it_read_beside_the_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _counted(tmp_path)
    assert defaultcheck.main(["--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == (
        f"defaultcheck OK: 2 variable(s) written twice or more under {tmp_path} have one value, "
        f"over 3 compose file(s) and 5 variable(s) read\n"
    )


_REFUSED = (
    "\ndefaultcheck: 1 compose file(s) could not be read, so no spend in them was compared. "
    "Rewrite a form the reader refuses in one it takes, or save the file as UTF-8 text, as the "
    "file's own fault says.\n"
)
_DISAGREEING = (
    "\ndefaultcheck: 1 compose variable(s) do not have one default. Give every spend of one "
    "variable the same default, rewritten only where the far side's own syntax cannot take it as "
    "written.\n"
)


def test_main_reports_each_fault_and_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _compose(tmp_path, _environment("${DIR:-./a}", "${DIR:-./b}"))
    assert defaultcheck.main(["--root", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert captured.out.startswith("DIR: is written 2 times")
    assert captured.err == _DISAGREEING


def test_main_counts_a_refused_file_as_a_file_and_not_as_a_variable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _compose(tmp_path, _environment("${OUTER:-${INNER}}"))
    assert defaultcheck.main(["--root", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert captured.out.startswith("docker-compose.yml: line 4: nested substitution")
    assert captured.err == _REFUSED


def test_main_prints_one_summary_per_kind_when_both_occur(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _both(tmp_path)
    assert defaultcheck.main(["--root", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert [line.split(":")[0] for line in captured.out.splitlines()] == [
        "docker-compose.bad.yml",
        "DIR",
    ]
    assert captured.err == _REFUSED + _DISAGREEING


def test_main_rejects_a_root_that_is_not_a_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "nowhere"
    assert defaultcheck.main(["--root", str(missing)]) == 2
    assert "is not a directory" in capsys.readouterr().err


def test_main_reports_a_scan_that_could_not_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert defaultcheck.main(["--root", str(tmp_path)]) == 2
    assert "defaultcheck: no compose file" in capsys.readouterr().err


def test_a_group_all_on_one_line_points_at_the_note_behind_it(tmp_path: Path) -> None:
    spend = '      DIR: "${MODELS_DIR:-./models}"  # ${MODELS_DIR:-./cache}\n'
    _compose(tmp_path, f"services:\n  brain:\n    environment:\n{spend}")
    (fault,) = defaultcheck.check(tmp_path).faults
    assert "does not have one default" in fault.detail
    assert "more than one of those spends is on docker-compose.yml:4" in fault.detail
    assert "move it above the line it annotates" in fault.detail


def test_a_group_spread_over_two_lines_is_offered_no_such_remedy(tmp_path: Path) -> None:
    _compose(tmp_path, _environment("${MODELS_DIR:-./models}", "${MODELS_DIR:-./cache}"))
    (fault,) = defaultcheck.check(tmp_path).faults
    assert "does not have one default" in fault.detail
    assert "more than one of those spends" not in fault.detail


def test_one_line_with_no_comment_in_sight_gets_the_hint_as_a_maybe(tmp_path: Path) -> None:
    _compose(tmp_path, _environment("${V:-a}/in:${V:-b}"))
    (fault,) = defaultcheck.check(tmp_path).faults
    assert "more than one of those spends is on docker-compose.yml:4" in fault.detail
    assert "if one of them is a comment" in fault.detail
