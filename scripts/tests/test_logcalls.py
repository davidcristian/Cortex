from pathlib import Path

import pytest

import logcalls
import loggernames

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

AUDIT = '''\
"""A miniature of the tool audit."""

_MESSAGE = "tool.invocation"


def note(name: str) -> None:
    """Write one audit line."""
    _logger.info(_MESSAGE, extra={"tool": name, "ok": True})
'''


def brain(root: Path, files: dict[str, str]) -> None:
    """Write a small brain tree, each path relative to `brain/packages/`."""
    for relative, text in files.items():
        path = root / "brain" / "packages" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def test_a_call_reports_its_level_and_its_fields_in_printed_order() -> None:
    call = logcalls.logged(SETTLE, "a handoff ended failed", "settle.py")
    assert (call.level, call.fields) == ("WARNING", ("reason", "session_id", "turn_id"))


def test_a_call_reports_the_line_it_stands_on() -> None:
    assert logcalls.logged(SETTLE, "a handoff ended failed", "settle.py").line == 10


def test_an_exception_call_prints_at_error() -> None:
    assert logcalls.logged(SETTLE, "could not release the handoff", "settle.py").level == "ERROR"


def test_a_call_attaching_nothing_reports_no_fields() -> None:
    assert logcalls.logged('_log.info("bare")\n', "bare", "m.py").fields == ()


def test_a_message_no_call_logs_is_a_fault() -> None:
    with pytest.raises(logcalls.LogCallError, match="logs no message 'gone'"):
        logcalls.logged(SETTLE, "gone", "settle.py")


def test_a_message_logged_twice_is_a_fault_naming_both_lines() -> None:
    text = '_log.info("twice")\n_log.warning("twice")\n'
    with pytest.raises(logcalls.LogCallError, match=r"in 2 places \(lines 1, 2\)"):
        logcalls.logged(text, "twice", "m.py")


def test_source_that_does_not_parse_is_a_fault() -> None:
    with pytest.raises(logcalls.LogCallError, match=r"cannot parse m\.py"):
        logcalls.logged("def (:\n", "anything", "m.py")


def test_a_line_whose_level_is_chosen_while_it_runs_is_refused_by_name() -> None:
    text = '_log.log(level, "a model-host request failed", extra={"model": model})\n'
    with pytest.raises(logcalls.LogCallError, match="at a level chosen while it runs"):
        logcalls.logged(text, "a model-host request failed", "api.py")


def test_a_dynamic_call_carrying_another_message_leaves_the_plain_fault_in_place() -> None:
    shapes = (
        "_log.log(level)\n"
        "_log.log(level, built)\n"
        "_log.log(level, 404)\n"
        '_log.log(level, "another line")\n'
        'render.log(level, "a third")\n'
    )
    with pytest.raises(logcalls.LogCallError, match="logs no message 'wanted'"):
        logcalls.logged(shapes, "wanted", "m.py")


def test_a_message_handed_to_the_call_by_name_is_the_message_that_call_logs() -> None:
    call = logcalls.logged(AUDIT, "tool.invocation", "audit.py")
    assert (call.level, call.fields) == ("INFO", ("ok", "tool"))


def test_a_name_the_module_does_not_bind_is_not_a_message_this_reader_can_read() -> None:
    with pytest.raises(logcalls.LogCallError, match="logs no message"):
        logcalls.logged("_log.info(message)\n", "done", "m.py")


def test_a_name_bound_to_something_that_is_not_a_string_is_not_a_message() -> None:
    with pytest.raises(logcalls.LogCallError, match="logs no message"):
        logcalls.logged("LIMIT = 12\n_log.info(LIMIT)\n", "12", "m.py")


def test_a_module_that_binds_its_message_and_writes_it_again_is_a_fault() -> None:
    text = '_MESSAGE = "tool.invocation"\n_log.info("tool.invocation", extra={"ok": True})\n'
    with pytest.raises(logcalls.LogCallError, match="binds it above as _MESSAGE; pass"):
        logcalls.logged(text, "tool.invocation", "audit.py")


def test_every_binding_of_a_twice_written_message_is_named() -> None:
    text = (
        '_AUDIT = "tool.invocation"\n_MESSAGE = "tool.invocation"\n_log.info("tool.invocation")\n'
    )
    with pytest.raises(logcalls.LogCallError, match="as _AUDIT, _MESSAGE;"):
        logcalls.logged(text, "tool.invocation", "audit.py")


def test_a_literal_message_beside_a_binding_of_some_other_string_is_left_alone() -> None:
    text = '_REFUSAL = "REFUSED: this turn is over budget"\n_log.info("tool.invocation")\n'
    assert logcalls.logged(text, "tool.invocation", "audit.py").level == "INFO"


def test_a_call_handed_its_message_by_name_reports_the_name_and_the_line_it_is_on() -> None:
    assert logcalls.handed(logcalls.parsed(AUDIT, "audit.py")) == [(8, "_MESSAGE")]


def test_a_wrapped_call_reports_the_line_the_name_sits_on() -> None:
    text = 'ABANDONED = "gone"\n_log.warning(\n    ABANDONED,\n    extra={},\n)\n'
    assert logcalls.handed(logcalls.parsed(text, "m.py")) == [(3, "ABANDONED")]


def test_a_call_writing_its_message_out_hands_no_name() -> None:
    assert logcalls.handed(logcalls.parsed(SETTLE, "settle.py")) == []


def test_a_call_that_is_not_a_log_call_hands_no_name() -> None:
    shapes = "warn(_MESSAGE)\nreport.render(_MESSAGE)\n_log.info()\n_log.info(404)\n"
    assert logcalls.handed(logcalls.parsed(shapes, "m.py")) == []


def test_a_plain_function_carrying_the_same_string_is_not_a_log_call() -> None:
    with pytest.raises(logcalls.LogCallError, match="logs no message"):
        logcalls.logged('warn("a handoff ended failed")\n', "a handoff ended failed", "m.py")


def test_a_method_that_is_not_a_logging_level_is_not_a_log_call() -> None:
    with pytest.raises(logcalls.LogCallError, match="logs no message"):
        logcalls.logged('report.render("done")\n', "done", "m.py")


def test_a_level_call_with_no_arguments_is_not_a_log_call() -> None:
    with pytest.raises(logcalls.LogCallError, match="logs no message"):
        logcalls.logged("_log.info()\n", "done", "m.py")


def test_a_first_argument_that_is_not_a_string_is_not_matched() -> None:
    with pytest.raises(logcalls.LogCallError, match="logs no message"):
        logcalls.logged("_log.info(404)\n", "done", "m.py")


def test_a_keyword_beside_extra_is_passed_over() -> None:
    text = '_log.info("done", stacklevel=2, extra={"ok": True})\n'
    assert logcalls.logged(text, "done", "m.py").fields == ("ok",)


def test_a_refused_field_list_is_raised_with_the_line_and_level_already_read() -> None:
    text = (
        "def f():\n"
        '    fields = {"ok": True}\n'
        '    fields["tool"] = 1\n'
        '    _log.warning("done", extra=fields)\n'
    )
    with pytest.raises(logcalls.UnreadFieldsError) as caught:
        logcalls.logged(text, "done", "m.py")
    assert (caught.value.line, caught.value.level) == (4, "WARNING")
    assert caught.value.reason == str(caught.value)
    assert "bound at line 2 and used again at line 3" in caught.value.reason


def test_an_extra_that_is_not_written_out_at_the_call_is_a_fault() -> None:
    with pytest.raises(logcalls.LogCallError, match="not a mapping written out"):
        logcalls.logged('_log.info("done", extra=fields)\n', "done", "m.py")


def test_a_field_name_that_is_not_a_plain_string_is_a_fault() -> None:
    with pytest.raises(logcalls.LogCallError, match="not a plain string"):
        logcalls.logged('_log.info("done", extra={KEY: 1})\n', "done", "m.py")


def test_a_spread_into_extra_is_a_fault_rather_than_a_short_answer() -> None:
    with pytest.raises(logcalls.LogCallError, match=r"spreads another into itself"):
        logcalls.logged('_log.info("done", extra={**base, "ok": True})\n', "done", "m.py")


def test_the_walk_answers_with_each_module_and_the_messages_its_calls_carry(
    tmp_path: Path,
) -> None:
    brain(
        tmp_path,
        {
            "core/src/cortex_core/swap_settle.py": SETTLE,
            "tools/src/cortex_tools/audit.py": AUDIT,
        },
    )
    assert logcalls.messages(tmp_path) == {
        "brain/packages/core/src/cortex_core/swap_settle.py": (
            "a handoff ended failed",
            "could not release the handoff",
        ),
        "brain/packages/tools/src/cortex_tools/audit.py": ("tool.invocation",),
    }


def test_a_module_that_logs_nothing_is_absent_rather_than_empty(tmp_path: Path) -> None:
    brain(tmp_path, {"core/src/cortex_core/ports.py": "class Clock:\n    pass\n"})
    assert logcalls.messages(tmp_path) == {}


def test_the_walk_refuses_a_word_written_twice_in_a_module_no_document_quotes(
    tmp_path: Path,
) -> None:
    brain(
        tmp_path,
        {
            "core/src/cortex_core/scheduler.py": (
                '_DRAINING = "pool draining for a model handoff"\n'
                '_log.warning("pool draining for a model handoff")\n'
            )
        },
    )
    with pytest.raises(logcalls.LogCallError, match="binds it above as _DRAINING; pass"):
        logcalls.messages(tmp_path)


def test_the_real_settler_attaches_the_three_fields_its_runbook_prints() -> None:
    module = REPO_ROOT / loggernames.loggers(REPO_ROOT)["cortex_core.swap_settle"]
    call = logcalls.logged(module.read_text(encoding="utf-8"), "a handoff ended failed", "settle")
    assert call.fields == ("reason", "session_id", "turn_id")
