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

# The tool audit's shape: the mapping is bound, grown under a condition and only then handed
# over, so the code reader refuses the call and a sample of it is held to the sink's own suite.
AUDIT_MODULE = "brain/packages/tools/src/cortex_tools/audit.py"
AUDIT_SUITE = "brain/packages/tools/tests/test_audit.py"

AUDIT = '''\
"""A miniature of the tool audit."""

import logging

_LOGGER_NAME = "cortex.tools.audit"
_MESSAGE = "tool.invocation"

_logger = logging.getLogger(_LOGGER_NAME)


def record(name: str, ok: bool) -> None:
    """Write one audit line."""
    fields = {"tool": name}
    if ok:
        fields["ok"] = ok
    _logger.info(_MESSAGE, extra=fields)
'''

# One line asserted whole, and the head of a longer one checked with `in`, which read as a whole
# line would be a one-field line the sink never prints.
SUITE = """\
def test_a_line() -> None:
    assert _line(record) == (
        "INFO:cortex.tools.audit:tool.invocation "
        "ok=True tool=read"
    )


def test_a_head() -> None:
    assert "INFO:cortex.tools.audit:tool.invocation tool=send" in line
"""

AUDIT_SAMPLE = "INFO:cortex.tools.audit:tool.invocation ok=<whether it succeeded> tool=<name>"

AUDIT_RUNBOOK = f"## What the trail prints\n\n```text\n{AUDIT_SAMPLE}\n```\n"


def repo(root: Path, *, module: str = SETTLE, runbook: str = RUNBOOK) -> Path:
    """Write a miniature repo: one logging module, one runbook that prints its line."""
    source = root / MODULE
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(module, encoding="utf-8")
    book = root / samplecheck.RUNBOOKS / "model-swap.md"
    book.parent.mkdir(parents=True, exist_ok=True)
    book.write_text(runbook, encoding="utf-8")
    return root


def audited(
    root: Path,
    *,
    module: str = AUDIT,
    suite: str | None = SUITE,
    runbook: str = AUDIT_RUNBOOK,
) -> Path:
    """Write a miniature repo whose one line is the audit's shape, with the suite that proves it.

    ``suite`` None writes no tests directory at all, which is a package nothing proves.
    """
    source = root / AUDIT_MODULE
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(module, encoding="utf-8")
    if suite is not None:
        tests = root / AUDIT_SUITE
        tests.parent.mkdir(parents=True, exist_ok=True)
        tests.write_text(suite, encoding="utf-8")
    book = root / samplecheck.RUNBOOKS / "tools-mcp.md"
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


# ── a line the source cannot list, held to the sink's own suite ───────────────


def test_a_sample_of_a_line_the_reader_cannot_read_is_held_to_the_suite(tmp_path: Path) -> None:
    """The tool audit's shape: the call is refused for its fields, and the sample passes because
    the sink's own suite asserts a line with the same fields whole."""
    scanned = samplecheck.check(audited(tmp_path))
    assert scanned.misses == []
    assert scanned.proven == 1


def test_a_field_no_asserted_line_carries_is_caught(tmp_path: Path) -> None:
    """This is the drift the fallback is written for: the runbook names a field the suite proves
    no line of this shape prints, and the fault says what the suite does prove."""
    wider = AUDIT_RUNBOOK.replace(
        "ok=<whether it succeeded>", "at=<when> ok=<whether it succeeded>"
    )
    misses = samplecheck.check(audited(tmp_path, runbook=wider)).misses
    assert len(misses) == 1
    assert misses[0].detail == (
        f"prints at, ok, tool where {AUDIT_MODULE}:16: extra= names fields, bound at line 13 and "
        "used again at line 15, so the mapping reaching the call is not the one written out, and "
        "no line under brain/packages/tools/tests is asserted whole with those fields (asserted "
        "whole there: ok, tool)"
    )


def test_a_sample_printing_the_fields_in_another_order_is_not_a_line_the_suite_proves(
    tmp_path: Path,
) -> None:
    swapped = AUDIT_RUNBOOK.replace("ok=<whether it succeeded> tool=<name>", "tool=<name> ok=<ok>")
    misses = samplecheck.check(audited(tmp_path, runbook=swapped)).misses
    assert len(misses) == 1
    assert misses[0].detail.startswith("prints tool, ok where")


def test_a_suite_that_stops_asserting_the_line_whole_leaves_the_sample_unheld(
    tmp_path: Path,
) -> None:
    """A suite that moves its equality into a containment check proves no line, so the sample is
    a miss rather than a pass: the chain from the runbook to the code is broken at the suite."""
    loosened = SUITE.replace(
        'assert _line(record) == (\n        "INFO:cortex.tools.audit:tool.invocation "\n'
        '        "ok=True tool=read"\n    )',
        'assert "ok=True tool=read" in _line(record)',
    )
    misses = samplecheck.check(audited(tmp_path, suite=loosened)).misses
    assert len(misses) == 1
    assert misses[0].detail.endswith("(asserted whole there: none)")


def test_a_head_checked_with_in_does_not_prove_a_line(tmp_path: Path) -> None:
    """The containment spells `tool` alone as the head of a longer line; a runbook printing that
    alone is not held by it, since a containment says nothing about what follows."""
    headed = AUDIT_RUNBOOK.replace("ok=<whether it succeeded> tool=<name>", "tool=<name>")
    misses = samplecheck.check(audited(tmp_path, runbook=headed)).misses
    assert len(misses) == 1
    assert "asserted whole there: ok, tool)" in misses[0].detail


def test_a_line_the_suite_asserts_under_another_message_holds_nothing(tmp_path: Path) -> None:
    other = SUITE.replace("tool.invocation ", "tool.refusal ")
    misses = samplecheck.check(audited(tmp_path, suite=other)).misses
    assert len(misses) == 1
    assert misses[0].detail.endswith("(asserted whole there: none)")


def test_the_level_is_compared_against_the_call_before_the_suite_is_read(tmp_path: Path) -> None:
    """The call was read as far as its level, so a sample at another level is the same miss it
    would be for a call whose fields were read."""
    demoted = AUDIT_RUNBOOK.replace("INFO:", "WARNING:")
    misses = samplecheck.check(audited(tmp_path, runbook=demoted)).misses
    assert [miss.detail for miss in misses] == [
        f"prints WARNING where {AUDIT_MODULE}:16 logs at INFO"
    ]


def test_a_sink_whose_package_has_no_suite_is_a_failure(tmp_path: Path) -> None:
    with pytest.raises(samplecheck.SampleCheckError, match="tests is not a directory"):
        samplecheck.check(audited(tmp_path, suite=None))


def test_a_suite_that_does_not_parse_is_a_failure(tmp_path: Path) -> None:
    with pytest.raises(samplecheck.SampleCheckError, match=r"cannot parse .*test_audit\.py"):
        samplecheck.check(audited(tmp_path, suite="def (:\n"))


def test_a_suite_is_read_only_for_a_call_whose_fields_cannot_be_read(tmp_path: Path) -> None:
    """A call the reader reads is held to the call: the suite beside it is never opened, so its
    absence is no failure and its assertions cannot overrule the source."""
    written = AUDIT.replace(
        '    fields = {"tool": name}\n    if ok:\n        fields["ok"] = ok\n', ""
    ).replace("extra=fields", 'extra={"ok": ok, "tool": name}')
    scanned = samplecheck.check(audited(tmp_path, module=written, suite=None))
    assert scanned.misses == []
    assert scanned.proven == 0


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
    assert scanned.proven == 0


def test_main_states_what_it_read_beside_the_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo(tmp_path)
    assert samplecheck.main(["--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == (
        f"samplecheck OK: 1 log sample(s) under {tmp_path} in 1 runbook(s) print the level, "
        "logger, message and fields their call sites write, resolved against 1 logger(s) the "
        "brain declares and the 1 message(s) it logs, 0 of the samples held to a line the "
        "sink's own suite asserts whole\n"
    )


def test_main_counts_the_samples_held_to_a_suite(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    audited(tmp_path)
    assert samplecheck.main(["--root", str(tmp_path)]) == 0
    assert "1 of the samples held to a line the sink's own suite asserts whole" in (
        capsys.readouterr().out
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


def test_the_repo_really_holds_a_sample_to_a_suite() -> None:
    """The tools runbook prints the audit trail's shapes, and each is held to the sink's own
    suite rather than to a call the source cannot list the fields of; a tree where none was
    would leave the fallback tested against its fixtures alone."""
    assert samplecheck.check(REPO_ROOT).proven >= 5


def test_main_passes_the_real_repo(capsys: pytest.CaptureFixture[str]) -> None:
    assert samplecheck.main(["--root", str(REPO_ROOT)]) == 0
    assert "samplecheck OK" in capsys.readouterr().out
