"""Tests for the reader that says which fields a brain log call attaches.

Each fixture is one function in a miniature brain module, written in a spelling the brain uses or
in one this reader refuses, and the reader is asked about a log call in it the way `logcalls.py`
asks: with the call, the parsed module, and the rule for which calls are log calls. The last tests
read the committed brain, so the two spellings that motivated the reader are held to the lines this
repo really writes.
"""

import ast
from pathlib import Path

import pytest

import logcalls
import logfields
from moduleconstants import constants

REPO_ROOT = Path(__file__).resolve().parents[2]
BRAIN_PHASE = "brain/packages/core/src/cortex_core/brain_phase.py"
TOOL_AUDIT = "brain/packages/tools/src/cortex_tools/audit.py"

LEVELS = frozenset({"info", "warning"})

# The deep phase's shape: one mapping bound above two calls, handed bare to one and unioned with a
# mapping written out to the other, beside a call whose mapping is written out.
PHASE = """\
def report(reading, record):
    if reading is None:
        _logger.info("no reading", stacklevel=2, extra={"model": record, "turn_id": record})
        return
    extra = {
        "model": record,
        "turn_id": record,
        "tokens_per_second": reading,
    }
    if reading < 1:
        _logger.warning("spilled", extra=extra | {"shortfall": reading})
    else:
        _logger.info("measured", extra=extra)
"""

# The tool audit's shape: the mapping is bound and then grown, by a call on it and by a key set
# under a condition, before the call is handed it.
AUDIT = """\
def record(invocation):
    fields = {"tool": invocation, "ok": True}
    fields.update({"turn_id": invocation})
    if invocation:
        fields["result_chars"] = 1
    _logger.info("tool.invocation", extra=fields)
"""


def is_log_call(node: ast.AST) -> bool:
    """The rule `logcalls.py` hands over: a call on a method named for a level."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in LEVELS
    )


def log_calls(text: str) -> tuple[ast.Module, list[ast.Call]]:
    """The parsed module and its log calls in source order."""
    tree = ast.parse(text)
    found = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and is_log_call(node)]
    return tree, sorted(found, key=lambda call: call.lineno)


def attached(text: str, which: int = 0) -> tuple[str, ...]:
    """The fields of the ``which``th log call in ``text``, counted in source order."""
    tree, calls = log_calls(text)
    return logfields.attached(calls[which], tree, "m.py", is_log_call=is_log_call)


def refused(text: str, which: int = 0) -> str:
    """What the reader says when asked about that call, which it has to refuse."""
    with pytest.raises(logfields.FieldError) as caught:
        attached(text, which)
    return str(caught.value)


# ── the three spellings ────────────────────────────────────────────────────────


def test_a_mapping_written_out_at_the_call_is_read_in_name_order() -> None:
    assert attached(PHASE, 0) == ("model", "turn_id")


def test_a_name_bound_above_the_call_is_followed_to_its_mapping() -> None:
    """The decode reading's shape: the mapping is built once above the call and handed bare."""
    assert attached(PHASE, 2) == ("model", "tokens_per_second", "turn_id")


def test_a_name_unioned_with_a_mapping_at_the_call_carries_both() -> None:
    """The spill warning's shape: the bound mapping plus one key written out at the call."""
    assert attached(PHASE, 1) == ("model", "shortfall", "tokens_per_second", "turn_id")


def test_a_key_both_halves_of_a_union_carry_is_one_field() -> None:
    """The formatter prints a record's keys, and a key the union overwrites is one key."""
    text = (
        'def f(r):\n    extra = {"model": r}\n    _logger.info("m", extra=extra | {"model": r})\n'
    )
    assert attached(text) == ("model",)


def test_a_call_attaching_nothing_reports_no_fields() -> None:
    assert attached('def f():\n    _logger.info("bare")\n') == ()


def test_an_async_function_is_a_scope_like_any_other() -> None:
    text = 'async def f(r):\n    extra = {"ok": r}\n    _logger.info("m", extra=extra)\n'
    assert attached(text) == ("ok",)


# ── where a name is followed to, and where it is not ───────────────────────────


def test_a_name_is_followed_inside_the_innermost_function_only() -> None:
    """A binding in the function around the call's own is not the mapping the call is handed."""
    text = (
        'def outer(r):\n    extra = {"outer": r}\n\n    def inner():\n'
        '        extra = {"inner": r}\n        _logger.info("m", extra=extra)\n'
    )
    assert attached(text) == ("inner",)
    tree, calls = log_calls(text)
    function = logfields.enclosing(tree, calls[0])
    assert function is not None
    assert function.name == "inner"


def test_a_name_bound_only_in_the_function_around_the_call_is_refused() -> None:
    """Following it outward would be reading a mapping the call's own function never bound."""
    text = (
        'def outer(r):\n    extra = {"outer": r}\n\n    def inner():\n'
        '        _logger.info("m", extra=extra)\n'
    )
    assert "which the enclosing function does not bind above the call" in refused(text)


def test_a_call_at_the_module_top_level_has_no_function_to_follow_a_name_in() -> None:
    text = 'extra = {"ok": True}\n_logger.info("m", extra=extra)\n'
    assert "not a mapping written out at the call, nor a name" in refused(text)
    assert logfields.enclosing(ast.parse(text), log_calls(text)[1][0]) is None


def test_a_name_bound_at_the_module_top_level_is_not_followed_from_a_function() -> None:
    """The reader stops at the function; a module-level mapping could be grown by any function."""
    text = 'extra = {"ok": True}\n\n\ndef f():\n    _logger.info("m", extra=extra)\n'
    assert "which the enclosing function does not bind above the call" in refused(text)


def test_a_parameter_is_not_a_mapping_written_out() -> None:
    text = 'def f(extra):\n    _logger.info("m", extra=extra)\n'
    assert refused(text) == (
        "m.py:2: extra= names extra, which the enclosing function does not bind above the call "
        "to a mapping written out"
    )


def test_a_name_bound_below_the_call_is_not_bound_above_it() -> None:
    text = 'def f(r):\n    _logger.info("m", extra=extra)\n    extra = {"ok": r}\n'
    assert "does not bind above the call" in refused(text)


def test_a_name_bound_only_inside_a_branch_is_refused() -> None:
    """A mapping bound in a branch is the mapping of the runs that took it, and the reader has no
    way to say which those are."""
    text = 'def f(r):\n    if r:\n        extra = {"ok": r}\n    _logger.info("m", extra=extra)\n'
    assert "does not bind above the call" in refused(text)


def test_a_name_bound_to_something_other_than_a_mapping_written_out_is_refused() -> None:
    text = 'def f(r):\n    extra = dict(ok=r)\n    _logger.info("m", extra=extra)\n'
    assert "does not bind above the call to a mapping written out" in refused(text)


def test_a_name_bound_twice_above_the_call_is_refused_naming_both_lines() -> None:
    text = (
        'def f(r):\n    extra = {"a": r}\n    extra = {"b": r}\n'
        '    _logger.info("m", extra=extra)\n'
    )
    assert "binds more than once above the call (lines 2, 3)" in refused(text)


# ── a mapping something else may have changed ──────────────────────────────────


def test_the_tool_audit_shape_is_refused_at_the_first_use_after_its_binding() -> None:
    """Grown by a call on it and by a key set under a condition, the mapping reaching the call is
    not the one written out, and the reader says so rather than reading the literal."""
    assert refused(AUDIT) == (
        "m.py:6: extra= names fields, bound at line 2 and used again at line 3, so the mapping "
        "reaching the call is not the one written out"
    )


def test_a_key_set_on_the_mapping_after_its_binding_is_a_use() -> None:
    text = (
        'def f(r):\n    extra = {"a": r}\n    extra["b"] = r\n    _logger.info("m", extra=extra)\n'
    )
    assert "used again at line 3" in refused(text)


def test_a_rebinding_inside_a_branch_after_the_binding_is_a_use() -> None:
    text = (
        'def f(r):\n    extra = {"a": r}\n    if r:\n        extra = {"b": r}\n'
        '    _logger.info("m", extra=extra)\n'
    )
    assert "used again at line 4" in refused(text)


def test_a_name_declared_global_or_nonlocal_is_a_use() -> None:
    """Either declaration makes the binding somebody else's to change."""
    shared = (
        'def f(r):\n    global extra\n    extra = {"a": r}\n    _logger.info("m", extra=extra)\n'
    )
    assert "used again at line 2" in refused(shared)
    closed = (
        "def outer(r):\n    extra = {}\n\n    def inner():\n        nonlocal extra\n"
        '        extra = {"a": r}\n        _logger.info("m", extra=extra)\n'
    )
    assert "used again at line 5" in refused(closed)


def test_a_name_handed_to_a_call_that_is_not_a_log_call_is_a_use() -> None:
    """A helper handed the mapping may grow it; only a log call is a use this reader accounts
    for."""
    text = (
        'def f(r):\n    extra = {"a": r}\n    helper(extra=extra)\n'
        '    _logger.info("m", extra=extra)\n'
    )
    assert "used again at line 3" in refused(text)


def test_a_name_handed_to_two_log_calls_is_read_at_each() -> None:
    """The deep phase's two calls share one binding, and neither use refuses the other."""
    assert attached(PHASE, 1) != attached(PHASE, 2)


# ── spellings that are none of the three ───────────────────────────────────────


@pytest.mark.parametrize(
    "value",
    [
        "make()",
        '{"a": r} | {"b": r}',
        "extra | other",
        '{"a": r} | extra',
    ],
)
def test_a_shape_that_is_none_of_the_three_is_refused(value: str) -> None:
    text = f'def f(r, other):\n    extra = {{"a": r}}\n    _logger.info("m", extra={value})\n'
    assert refused(text) == (
        "m.py:3: extra= is not a mapping written out at the call, nor a name the enclosing "
        "function binds to one"
    )


def test_a_key_in_the_bound_mapping_that_is_not_a_plain_string_is_refused_at_its_line() -> None:
    text = 'def f(r):\n    extra = {KEY: r}\n    _logger.info("m", extra=extra)\n'
    assert refused(text) == "m.py:2: a field name here is not a plain string"


def test_a_spread_in_the_unioned_mapping_is_refused() -> None:
    text = 'def f(r):\n    extra = {"a": r}\n    _logger.info("m", extra=extra | {**r})\n'
    assert "not a plain string" in refused(text)


# ── the committed brain ────────────────────────────────────────────────────────


def _real(shown: str) -> tuple[str, dict[str, str]]:
    source = (REPO_ROOT / shown).read_text(encoding="utf-8")
    return source, constants(ast.parse(source))[0]


def test_the_real_deep_phase_attaches_nine_fields_to_its_spill_warning() -> None:
    source, strings = _real(BRAIN_PHASE)
    call = logcalls.logged(source, strings["SPILLED_LOG_MSG"], BRAIN_PHASE)
    assert (call.level, call.fields) == (
        "WARNING",
        (
            "floor_tokens_per_second",
            "judged",
            "model",
            "samples",
            "session_id",
            "shortfall",
            "tokens",
            "tokens_per_second",
            "turn_id",
        ),
    )


def test_the_real_deep_phase_attaches_the_same_fields_but_one_to_its_decode_reading() -> None:
    source, strings = _real(BRAIN_PHASE)
    warning = logcalls.logged(source, strings["SPILLED_LOG_MSG"], BRAIN_PHASE)
    reading = logcalls.logged(source, strings["_MEASURED_LOG_MSG"], BRAIN_PHASE)
    assert reading.level == "INFO"
    assert set(warning.fields) - set(reading.fields) == {"shortfall"}


def test_the_real_tool_audit_stays_unquotable() -> None:
    """Its mapping grows by condition, so no one sample could print what it attaches."""
    source, _ = _real(TOOL_AUDIT)
    with pytest.raises(logcalls.LogCallError, match="used again at line"):
        logcalls.logged(source, "tool.invocation", TOOL_AUDIT)
