"""Behaviour of the reader that says what a brain log call really puts on its line.

The fixtures are miniature brain packages, laid out the way the real ones are (`<package>/src/`
holding an importable tree), because the walk's whole job is to find a logger by the name a
document prints and that name is a function of where the module sits. The last tests here read
the committed brain, where every spelling of a logger claim is true or this reader is
answering about a tree nobody ships.
"""

from pathlib import Path

import pytest

import logcalls

REPO_ROOT = Path(__file__).resolve().parents[2]

SETTLE = '''\
"""A miniature of the settler."""

import logging

_logger = logging.getLogger(__name__)


def fail(record: object, reason: str) -> None:
    """Settle the record failed."""
    _logger.warning(
        "a handoff ended failed",
        extra={
            "session_id": record,
            "turn_id": record,
            "reason": reason,
        },
    )


def wedged(record: object) -> None:
    """Say the claim could not be released."""
    _logger.exception("could not release the handoff", extra={"turn_id": record})
'''


def brain(root: Path, files: dict[str, str]) -> None:
    """Write a miniature brain, each path relative to `brain/packages/`."""
    for relative, text in files.items():
        path = root / "brain" / "packages" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def settler(root: Path) -> None:
    """The one fixture package every test about a call site starts from."""
    brain(root, {"core/src/cortex_core/swap_settle.py": SETTLE})


# ── which module owns a logger name ────────────────────────────────────────────


def test_a_module_logging_under_name_is_found_by_its_dotted_path(tmp_path: Path) -> None:
    settler(tmp_path)
    assert logcalls.loggers(tmp_path) == {
        "cortex_core.swap_settle": "brain/packages/core/src/cortex_core/swap_settle.py"
    }


def test_a_sink_that_names_itself_is_found_under_the_name_it_chose(tmp_path: Path) -> None:
    """The tool audit and the recall trail both do this, their lines being read as a trail."""
    brain(tmp_path, {"tools/src/cortex_tools/audit.py": 'getLogger("cortex.tools.audit")\n'})
    assert set(logcalls.loggers(tmp_path)) == {"cortex.tools.audit"}


def test_a_sink_naming_its_logger_through_a_constant_is_found_under_that_name(
    tmp_path: Path,
) -> None:
    """The recall trail's spelling: its name is a declaration because three documents restate it
    and the constant registry ties them to it, so a reader that knew only a literal would drop
    that trail out of this answer and fail a sample of it as a logger no module declares."""
    brain(
        tmp_path,
        {
            "memory/src/cortex_memory/audit.py": (
                '_LOGGER_NAME = "cortex.memory.recall"\n_logger = logging.getLogger(_LOGGER_NAME)\n'
            )
        },
    )
    assert logcalls.loggers(tmp_path) == {
        "cortex.memory.recall": "brain/packages/memory/src/cortex_memory/audit.py"
    }


def test_a_logger_named_through_something_the_module_does_not_bind_is_a_fault(
    tmp_path: Path,
) -> None:
    """A name from anywhere but this module's own top level is refused rather than chased: an
    importer of the brain is what this tree may not become, so the fault says which name it is."""
    brain(
        tmp_path,
        {
            "memory/src/cortex_memory/audit.py": (
                "from cortex_core.log_fields import RECALL_LOGGER\n"
                "_logger = logging.getLogger(RECALL_LOGGER)\n"
            )
        },
    )
    with pytest.raises(logcalls.LogCallError, match="RECALL_LOGGER, which its own top level"):
        logcalls.loggers(tmp_path)


def test_a_package_barrel_claims_the_package_name_and_not_its_init(tmp_path: Path) -> None:
    brain(tmp_path, {"core/src/cortex_core/__init__.py": "getLogger(__name__)\n"})
    assert set(logcalls.loggers(tmp_path)) == {"cortex_core"}


def test_a_pruned_directory_inside_the_source_tree_is_not_walked(tmp_path: Path) -> None:
    """A cached copy of a module would otherwise claim the same name as the module itself."""
    settler(tmp_path)
    brain(tmp_path, {"core/src/cortex_core/__pycache__/stale.py": "getLogger(__name__)\n"})
    assert set(logcalls.loggers(tmp_path)) == {"cortex_core.swap_settle"}


def test_a_package_with_no_source_tree_is_passed_over(tmp_path: Path) -> None:
    settler(tmp_path)
    (tmp_path / "brain" / "packages" / "notes").mkdir()
    assert set(logcalls.loggers(tmp_path)) == {"cortex_core.swap_settle"}


def test_two_files_claiming_one_logger_name_is_a_fault_not_a_coin_toss(tmp_path: Path) -> None:
    brain(
        tmp_path,
        {
            "tools/src/cortex_tools/audit.py": 'getLogger("cortex.tools.audit")\n',
            "memory/src/cortex_memory/audit.py": 'getLogger("cortex.tools.audit")\n',
        },
    )
    with pytest.raises(logcalls.LogCallError, match="both declare the logger"):
        logcalls.loggers(tmp_path)


def test_a_brain_that_cannot_be_walked_is_a_fault(tmp_path: Path) -> None:
    with pytest.raises(logcalls.LogCallError, match="cannot read brain/packages"):
        logcalls.loggers(tmp_path)


def test_a_source_file_that_is_not_text_is_a_fault(tmp_path: Path) -> None:
    settler(tmp_path)
    (tmp_path / "brain/packages/core/src/cortex_core/blob.py").write_bytes(b"\xff\xfe\x00")
    with pytest.raises(logcalls.LogCallError, match=r"cannot read .*blob\.py"):
        logcalls.loggers(tmp_path)


# ── what one call attaches ─────────────────────────────────────────────────────


def test_a_call_reports_its_level_and_its_fields_in_printed_order() -> None:
    """Printed order is name order, which is what makes one comparison hold order too."""
    call = logcalls.logged(SETTLE, "a handoff ended failed", "settle.py")
    assert (call.level, call.fields) == ("WARNING", ("reason", "session_id", "turn_id"))


def test_a_call_reports_the_line_it_stands_on() -> None:
    assert logcalls.logged(SETTLE, "a handoff ended failed", "settle.py").line == 10


def test_an_exception_call_prints_at_error() -> None:
    """The one method that is not its own level, and a runbook quoting one prints ERROR."""
    assert logcalls.logged(SETTLE, "could not release the handoff", "settle.py").level == "ERROR"


def test_a_call_attaching_nothing_reports_no_fields() -> None:
    assert logcalls.logged('_log.info("bare")\n', "bare", "m.py").fields == ()


def test_a_message_no_call_logs_is_a_fault() -> None:
    with pytest.raises(logcalls.LogCallError, match="logs no message 'gone'"):
        logcalls.logged(SETTLE, "gone", "settle.py")


def test_a_message_logged_twice_is_a_fault_naming_both_lines() -> None:
    """Two call sites are two answers, and a sample cannot be about both."""
    text = '_log.info("twice")\n_log.warning("twice")\n'
    with pytest.raises(logcalls.LogCallError, match=r"in 2 places \(lines 1, 2\)"):
        logcalls.logged(text, "twice", "m.py")


def test_source_that_does_not_parse_is_a_fault() -> None:
    with pytest.raises(logcalls.LogCallError, match=r"cannot parse m\.py"):
        logcalls.logged("def (:\n", "anything", "m.py")


def test_a_line_whose_level_is_chosen_while_it_runs_is_refused_by_name() -> None:
    """The model host switches a request failure between warning and error exactly this way."""
    text = '_log.log(level, "a model-host request failed", extra={"model": model})\n'
    with pytest.raises(logcalls.LogCallError, match="at a level chosen while it runs"):
        logcalls.logged(text, "a model-host request failed", "api.py")


def test_a_dynamic_call_carrying_another_message_leaves_the_plain_fault_standing() -> None:
    """The second walk must not claim a line the module writes about something else."""
    shapes = (
        "_log.log(level)\n"
        "_log.log(level, built)\n"
        "_log.log(level, 404)\n"
        '_log.log(level, "another line")\n'
        'render.log(level, "a third")\n'
    )
    with pytest.raises(logcalls.LogCallError, match="logs no message 'wanted'"):
        logcalls.logged(shapes, "wanted", "m.py")


# ── what is not a log call ─────────────────────────────────────────────────────


def test_a_plain_function_carrying_the_same_string_is_not_a_log_call() -> None:
    """`raise Error("...")` and a helper are both calls, and neither writes a line."""
    with pytest.raises(logcalls.LogCallError, match="logs no message"):
        logcalls.logged('warn("a handoff ended failed")\n', "a handoff ended failed", "m.py")


def test_a_method_that_is_not_a_logging_level_is_not_a_log_call() -> None:
    with pytest.raises(logcalls.LogCallError, match="logs no message"):
        logcalls.logged('report.render("done")\n', "done", "m.py")


def test_a_level_call_with_no_arguments_is_not_a_log_call() -> None:
    with pytest.raises(logcalls.LogCallError, match="logs no message"):
        logcalls.logged("_log.info()\n", "done", "m.py")


def test_a_message_built_at_the_call_is_not_matched() -> None:
    """A name or an f-string is not a message this reader can compare with a page."""
    with pytest.raises(logcalls.LogCallError, match="logs no message"):
        logcalls.logged("_log.info(message)\n", "done", "m.py")


def test_a_first_argument_that_is_not_a_string_is_not_matched() -> None:
    with pytest.raises(logcalls.LogCallError, match="logs no message"):
        logcalls.logged("_log.info(404)\n", "done", "m.py")


# ── an extra= this reader will not guess at ────────────────────────────────────


def test_a_keyword_beside_extra_is_passed_over() -> None:
    text = '_log.info("done", stacklevel=2, extra={"ok": True})\n'
    assert logcalls.logged(text, "done", "m.py").fields == ("ok",)


def test_an_extra_that_is_not_written_out_at_the_call_is_a_fault() -> None:
    """A dict built elsewhere is a field set this reader cannot see, so it says so."""
    with pytest.raises(logcalls.LogCallError, match="not a mapping written out"):
        logcalls.logged('_log.info("done", extra=fields)\n', "done", "m.py")


def test_a_field_name_that_is_not_a_plain_string_is_a_fault() -> None:
    with pytest.raises(logcalls.LogCallError, match="not a plain string"):
        logcalls.logged('_log.info("done", extra={KEY: 1})\n', "done", "m.py")


def test_a_spread_into_extra_is_a_fault_rather_than_a_short_answer() -> None:
    """`**base` carries names from somewhere else, and a shrug here would under-report them."""
    with pytest.raises(logcalls.LogCallError, match="not a plain string"):
        logcalls.logged('_log.info("done", extra={**base, "ok": True})\n', "done", "m.py")


# ── the brain this reader is written for ───────────────────────────────────────


def test_the_committed_brain_declares_every_spelling_of_a_logger_claim() -> None:
    """A guard on the fixtures: a spelling nobody writes would be untested machinery."""
    names = logcalls.loggers(REPO_ROOT)
    assert names["cortex_core.swap_settle"].endswith("cortex_core/swap_settle.py")
    assert names["cortex.tools.audit"].endswith("cortex_tools/audit.py")
    assert names["cortex.memory.recall"].endswith("cortex_memory/audit.py")


def test_the_real_settler_attaches_the_three_fields_its_runbook_prints() -> None:
    module = REPO_ROOT / logcalls.loggers(REPO_ROOT)["cortex_core.swap_settle"]
    call = logcalls.logged(module.read_text(encoding="utf-8"), "a handoff ended failed", "settle")
    assert call.fields == ("reason", "session_id", "turn_id")
