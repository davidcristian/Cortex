"""Tests for the gate holding a runbook's log samples to the calls that would print them.

The fixtures are a miniature repo: one brain package that logs one line, one runbook that prints
it. Every mutation below is an edit somebody could make to one side and forget on the other, which
is why this gate exists: the two sides are two hundred files apart and each of them stays green on
its own. The last tests here run the gate over the committed tree, since the fixtures alone would
test the gate against itself.
"""

from pathlib import Path

import pytest

import samplecheck

REPO_ROOT = Path(__file__).resolve().parents[2]

MODULE = "brain/packages/core/src/cortex_core/swap_settle.py"

SETTLE = '''\
"""A miniature of the settler."""

import logging

_logger = logging.getLogger(__name__)


def fail(record: object, reason: str) -> None:
    """Settle the record failed."""
    _logger.warning(
        "a handoff ended failed",
        extra={"session_id": record, "turn_id": record, "reason": reason},
    )
'''

SAMPLE = (
    'WARNING:cortex_core.swap_settle:a handoff ended failed reason="<what happened>" '
    "session_id=<chat id> turn_id=<turn id>"
)

RUNBOOK = f"## Why a handoff failed\n\n```text\n{SAMPLE}\n```\n"


def repo(root: Path, *, module: str = SETTLE, runbook: str = RUNBOOK) -> Path:
    """Write a miniature repo: one logging module, one runbook that prints its line."""
    source = root / MODULE
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(module, encoding="utf-8")
    book = root / samplecheck.RUNBOOKS / "model-swap.md"
    book.parent.mkdir(parents=True, exist_ok=True)
    book.write_text(runbook, encoding="utf-8")
    return root


def detail(root: Path) -> str:
    """Return the one miss the fixture produces, asserting the count so a miscount fails here."""
    misses = samplecheck.check(root).misses
    assert len(misses) == 1
    return misses[0].detail


# ── the agreement it is written to hold ────────────────────────────────────────


def test_a_sample_that_prints_what_the_call_attaches_is_clean(tmp_path: Path) -> None:
    assert samplecheck.check(repo(tmp_path)).misses == []


def test_a_field_the_call_stopped_attaching_is_caught(tmp_path: Path) -> None:
    """This is the defect the gate is written for: the sample goes on printing a field the call no
    longer attaches."""
    dropped = SETTLE.replace(', "reason": reason', "")
    assert "attaches session_id, turn_id" in detail(repo(tmp_path, module=dropped))


def test_a_field_the_call_started_attaching_is_caught(tmp_path: Path) -> None:
    """The same drift in the other direction, which a check anchored on the neighbouring fields
    would not see."""
    gained = SETTLE.replace('"reason": reason', '"reason": reason, "state": record')
    assert "attaches reason, session_id, state, turn_id" in detail(repo(tmp_path, module=gained))


def test_a_sample_printing_its_fields_in_another_order_is_caught(tmp_path: Path) -> None:
    """Fields render in name order, so an order the formatter never renders is a miss."""
    swapped = RUNBOOK.replace(
        'reason="<what happened>" session_id=<chat id>',
        'session_id=<chat id> reason="<what happened>"',
    )
    assert "prints session_id, reason, turn_id" in detail(repo(tmp_path, runbook=swapped))


def test_a_line_demoted_to_another_level_is_caught(tmp_path: Path) -> None:
    """The runbook tells an operator which level to grep, so the level is part of the claim."""
    demoted = SETTLE.replace("_logger.warning(", "_logger.info(")
    assert (
        detail(repo(tmp_path, module=demoted)) == f"prints WARNING where {MODULE}:10 logs at INFO"
    )


def test_a_message_the_module_no_longer_logs_is_caught(tmp_path: Path) -> None:
    reworded = SETTLE.replace("a handoff ended failed", "a handoff failed")
    assert "logs no message 'a handoff ended failed'" in detail(repo(tmp_path, module=reworded))


def test_a_sample_naming_a_logger_nothing_declares_is_caught(tmp_path: Path) -> None:
    """A runbook quoting a logger no module declares is reported as a miss rather than skipped."""
    moved = RUNBOOK.replace("cortex_core.swap_settle", "cortex_core.swap_settler")
    assert "which no module under the brain declares" in detail(repo(tmp_path, runbook=moved))


def test_an_empty_field_list_is_reported_in_words(tmp_path: Path) -> None:
    """A sample printing no fields is reported in words, since an empty list in the message would
    read as a formatting slip."""
    bare = RUNBOOK.replace(SAMPLE, "WARNING:cortex_core.swap_settle:a handoff ended failed")
    assert detail(repo(tmp_path, runbook=bare)).startswith("prints no fields where")


def test_a_miss_names_the_runbook_and_the_line_it_stands_on(tmp_path: Path) -> None:
    dropped = SETTLE.replace(', "reason": reason', "")
    miss = samplecheck.check(repo(tmp_path, module=dropped)).misses[0]
    assert (miss.doc, miss.line) == ("docs/runbooks/model-swap.md", 4)


# ── fail closed ────────────────────────────────────────────────────────────────


def test_a_repo_with_no_runbook_tree_is_a_failure(tmp_path: Path) -> None:
    source = tmp_path / MODULE
    source.parent.mkdir(parents=True)
    source.write_text(SETTLE, encoding="utf-8")
    with pytest.raises(samplecheck.SampleCheckError, match="is not a directory"):
        samplecheck.check(tmp_path)


def test_a_runbook_tree_with_no_sample_in_it_is_a_failure(tmp_path: Path) -> None:
    """A runbook tree holding no sample raises, since a comparison over nothing would pass every
    time it ran."""
    with pytest.raises(samplecheck.SampleCheckError, match="no log sample"):
        samplecheck.check(repo(tmp_path, runbook="## Nothing rendered here\n"))


def test_a_brain_that_declares_no_logger_is_a_failure(tmp_path: Path) -> None:
    """This is the other empty side: a logger table nothing filled would leave every sample's
    logger unknown."""
    with pytest.raises(samplecheck.SampleCheckError, match="declares no logger"):
        samplecheck.check(repo(tmp_path, module="x = 1\n"))


def test_a_brain_that_logs_no_message_is_a_failure(tmp_path: Path) -> None:
    """The third empty side: a module that declares a logger and writes nothing through it would
    leave every sample's message unaccounted for, and this floor keeps that from reading as
    clean."""
    module = "import logging\n\n_logger = logging.getLogger(__name__)\n"
    with pytest.raises(samplecheck.SampleCheckError, match="logs no message"):
        samplecheck.check(repo(tmp_path, module=module))


def test_a_brain_that_cannot_be_walked_is_a_failure(tmp_path: Path) -> None:
    book = tmp_path / samplecheck.RUNBOOKS / "model-swap.md"
    book.parent.mkdir(parents=True)
    book.write_text(RUNBOOK, encoding="utf-8")
    with pytest.raises(samplecheck.SampleCheckError, match="cannot read brain/packages"):
        samplecheck.check(tmp_path)


def test_a_runbook_that_is_not_text_is_a_failure(tmp_path: Path) -> None:
    repo(tmp_path)
    (tmp_path / samplecheck.RUNBOOKS / "blob.md").write_bytes(b"\xff\xfe\x00")
    with pytest.raises(samplecheck.SampleCheckError, match=r"cannot read docs/runbooks/blob\.md"):
        samplecheck.check(tmp_path)


def test_a_pruned_directory_under_the_runbooks_is_not_read(tmp_path: Path) -> None:
    repo(tmp_path)
    cached = tmp_path / samplecheck.RUNBOOKS / "node_modules"
    cached.mkdir()
    (cached / "vendored.md").write_text("```text\nINFO:nope.nowhere:hi\n```\n", encoding="utf-8")
    assert samplecheck.check(tmp_path).misses == []


# ── what the comparison was over ───────────────────────────────────────────────


def test_check_counts_the_samples_the_runbooks_the_loggers_and_the_messages(
    tmp_path: Path,
) -> None:
    scanned = samplecheck.check(repo(tmp_path))
    assert (scanned.samples, scanned.docs, scanned.loggers, scanned.messages) == (1, 1, 1, 1)


def test_main_states_what_it_read_beside_the_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo(tmp_path)
    assert samplecheck.main(["--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == (
        f"samplecheck OK: 1 log sample(s) under {tmp_path} in 1 runbook(s) print the level, "
        "logger, message and fields their call sites write, resolved against 1 logger(s) the "
        "brain declares and the 1 message(s) it logs\n"
    )


def test_main_reports_each_miss_and_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo(tmp_path, module=SETTLE.replace(', "reason": reason', ""))
    assert samplecheck.main(["--root", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert "docs/runbooks/model-swap.md:4: the sample prints reason, session_id" in captured.out
    assert "1 documented log sample(s) do not say what the call site would print" in captured.err


def test_main_rejects_a_root_that_is_not_a_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert samplecheck.main(["--root", str(tmp_path / "nope")]) == 2
    assert "is not a directory" in capsys.readouterr().err


def test_main_reports_a_comparison_that_could_not_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert samplecheck.main(["--root", str(tmp_path)]) == 2
    assert "cannot read brain/packages" in capsys.readouterr().err


# ── the repo this gate guards ──────────────────────────────────────────────────


def test_the_repo_itself_is_clean() -> None:
    """The gate's own assertion, run as a test so `check-scripts` catches drift too."""
    assert samplecheck.check(REPO_ROOT).misses == []


def test_the_repo_really_carries_samples_for_this_gate_to_have_checked() -> None:
    """This guards the test above, which a walk that read nothing would leave vacuous."""
    scanned = samplecheck.check(REPO_ROOT)
    assert scanned.samples >= 3
    assert scanned.docs >= 10
    assert scanned.loggers >= 20


def test_main_passes_the_real_repo(capsys: pytest.CaptureFixture[str]) -> None:
    assert samplecheck.main(["--root", str(REPO_ROOT)]) == 0
    assert "samplecheck OK" in capsys.readouterr().out
