"""The `Confirmer` contract, checked against every implementation of the port."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from cortex_core import ConfirmationRequest, Confirmer

_SEND = ConfirmationRequest(
    tool_name="send_email",
    arguments={"to": "someone@example.com", "subject": "hi"},
    reason="sends mail nobody can unsend",
)
_WRITE = ConfirmationRequest(
    tool_name="write_file", arguments={"path": "/projects/notes.txt"}, reason="writes to disk"
)


@dataclass(frozen=True, slots=True)
class ConfirmerUnderTest:
    """One implementation, what the person on the other side will say, and what they were shown."""

    confirmer: Confirmer
    will_approve: Callable[[], None]
    will_refuse: Callable[[], None]
    will_say_nothing: Callable[[], None]
    shown: Callable[[], Sequence[ConfirmationRequest]]


type Check = Callable[[ConfirmerUnderTest], Awaitable[None]]


async def an_explicit_approval_is_the_only_true(under_test: ConfirmerUnderTest) -> None:
    """A yes from the person allows the call, and it is the only thing that does."""
    under_test.will_approve()
    assert await under_test.confirmer.confirm(_SEND) is True


async def an_explicit_refusal_blocks_the_call(under_test: ConfirmerUnderTest) -> None:
    """A refusal is returned rather than raised, so the turn continues and the tool does not."""
    under_test.will_refuse()
    assert await under_test.confirmer.confirm(_SEND) is False


async def a_person_who_never_answers_denies(under_test: ConfirmerUnderTest) -> None:
    """A person who never answers is read as a refusal, which is the fail-closed half."""
    under_test.will_say_nothing()
    assert await under_test.confirmer.confirm(_SEND) is False


async def the_person_is_shown_the_call_that_would_run(under_test: ConfirmerUnderTest) -> None:
    """The draft shown is the draft executed: name, arguments and reason all reach the decider."""
    under_test.will_approve()
    await under_test.confirmer.confirm(_SEND)
    assert list(under_test.shown()) == [_SEND]


async def each_ask_is_answered_on_its_own(under_test: ConfirmerUnderTest) -> None:
    """One answer settles one ask, and never the next one."""
    under_test.will_approve()
    assert await under_test.confirmer.confirm(_SEND) is True
    under_test.will_refuse()
    assert await under_test.confirmer.confirm(_WRITE) is False
    assert list(under_test.shown()) == [_SEND, _WRITE]


ALL_CHECKS: Sequence[Check] = (
    an_explicit_approval_is_the_only_true,
    an_explicit_refusal_blocks_the_call,
    a_person_who_never_answers_denies,
    the_person_is_shown_the_call_that_would_run,
    each_ask_is_answered_on_its_own,
)
