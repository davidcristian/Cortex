"""Behavior of the pure session-summary derivation (ADR-0021, cortex_core.sessions)."""

from datetime import UTC, datetime

from cortex_core import Message, Role, SessionSummary, summarize_session
from cortex_core.sessions import PREVIEW_MAX, TITLE_MAX

_EARLY = datetime(2026, 7, 8, 9, 0, tzinfo=UTC)
_LATE = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)


def _msg(role: Role, text: str, at: datetime) -> Message:
    return Message(role=role, text=text, at=at, turn_id="t")


def test_title_is_the_first_message_and_preview_is_the_last() -> None:
    summary = summarize_session(
        "s1",
        [
            _msg(Role.USER, "what is a cortex", _EARLY),
            _msg(Role.ASSISTANT, "a resident model", _LATE),
        ],
    )
    assert summary == SessionSummary(
        session_id="s1",
        title="what is a cortex",
        preview="a resident model",
        last_activity=_LATE,
    )


def test_single_message_session_uses_it_for_both_title_and_preview() -> None:
    summary = summarize_session("s1", [_msg(Role.USER, "lone question", _EARLY)])
    assert summary.title == "lone question"
    assert summary.preview == "lone question"
    assert summary.last_activity == _EARLY


def test_whitespace_is_collapsed_to_single_spaces() -> None:
    summary = summarize_session("s1", [_msg(Role.USER, "  hello \n\t world  ", _EARLY)])
    assert summary.title == "hello world"


def test_long_title_and_preview_are_truncated_with_an_ellipsis() -> None:
    long_title = "T" * (TITLE_MAX + 20)
    long_preview = "P" * (PREVIEW_MAX + 20)
    summary = summarize_session(
        "s1",
        [_msg(Role.USER, long_title, _EARLY), _msg(Role.ASSISTANT, long_preview, _LATE)],
    )
    assert summary.title == "T" * TITLE_MAX + "…"
    assert summary.preview == "P" * PREVIEW_MAX + "…"


def test_title_exactly_at_the_limit_is_not_truncated() -> None:
    exact = "E" * TITLE_MAX
    summary = summarize_session("s1", [_msg(Role.USER, exact, _EARLY)])
    assert summary.title == exact
