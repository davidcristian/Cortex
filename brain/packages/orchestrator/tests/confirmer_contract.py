"""The `Confirmer` contract, run over every implementation (AGENTS.md: ports before adapters).

The port is one method wide and every one of its promises is a safety property: a gated tool call
runs only if a human said yes, out of band, and the model can neither forge that yes nor route
around it. So the checks below are short, and each of them is a sentence about what may become
`True`.

Each fixture supplies the conditions of the world no method of the port can create: what the
person on the other side will do when the next card reaches them. A fake has nobody on the other
side, so it satisfies `will_say_nothing` by being scripted with the answer the port owes when no
one answers, which is the honest widening the vision probe's contract already uses: the check
states what an implementation must *return*, not how the silence arose.
"""

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
    """A no is a no, answered rather than raised, so the turn continues and the tool does not."""
    under_test.will_refuse()
    assert await under_test.confirmer.confirm(_SEND) is False


async def a_person_who_never_answers_denies(under_test: ConfirmerUnderTest) -> None:
    """Silence is a denial. This is the fail-closed half and the reason the port exists.

    An irreversible action must never run because nobody was there to object: a confirmer that
    defaulted to yes, or that waited forever, would turn an unattended overlay into permission.
    """
    under_test.will_say_nothing()
    assert await under_test.confirmer.confirm(_SEND) is False


async def the_person_is_shown_the_call_that_would_run(under_test: ConfirmerUnderTest) -> None:
    """The draft shown is the draft executed: name, arguments and reason all reach the decider.

    An approval means nothing if the card described a different call from the one that then runs,
    so every field of the request has to survive the trip to whoever decides. The reason is part
    of it: it is the sentence saying why this call needs a human at all.
    """
    under_test.will_approve()
    await under_test.confirmer.confirm(_SEND)
    assert list(under_test.shown()) == [_SEND]


async def each_ask_is_answered_on_its_own(under_test: ConfirmerUnderTest) -> None:
    """One answer settles one ask, and never the next one.

    Two gated calls in a turn are two questions. An implementation that let an answer stand for
    later asks would spend one yes on an action the person never saw, which is the same defect as
    forging the yes outright.
    """
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
