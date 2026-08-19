"""The `Mailbox` contract, run over every implementation (AGENTS.md: ports before adapters).

The port returns messages, and until a query is refused that is all any check can see. The
refusal is the other half of the port and the half a caller must be able to act on, so each
fixture supplies the one condition of the world no method can create: **the server refuses the
next search**. A fake has no server to refuse, so it satisfies the knob by being scripted to
raise what the port owes, the same honest widening the `Embedder` contract's broken-backend knob
uses: the checks state what an implementation must *do* when a query comes back refused, not
what the wire said.

Driven over the fake and over `ImapMailbox` by `test_mailbox_contract.py`.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import pytest

from cortex_email import Mailbox, SearchRefusedError

# The client syntax a model reaches for, which is what a real Bridge answers BAD to.
REFUSED_QUERY = "from:someone@example.com"
# What imaplib puts in the exception a refused search raises, verbatim from a live Bridge. No
# implementation may pass any of it on: it is an offset into a wire command the model never saw.
WIRE_ANSWER = "UID command error: BAD [b'[Error offset=38]: expected space']"


@dataclass(frozen=True, slots=True)
class MailboxUnderTest:
    """One implementation, the folder it has messages in, and the one knob a check needs."""

    mailbox: Mailbox
    folder: str
    refuse_searches: Callable[[], None]


type Check = Callable[[MailboxUnderTest], None]


def folders_come_back_as_plain_names(under_test: MailboxUnderTest) -> None:
    """`list_folders` answers with the names a later call may be given, and nothing else.

    The folder argument of both other methods is spelled exactly as this returned it, which the
    tool description promises the model outright, so a folder object, a path, or a decorated
    name here would be a name no search could use.
    """
    folders = list(under_test.mailbox.list_folders())
    assert folders
    assert all(type(name) is str for name in folders)
    assert under_test.folder in folders


def a_search_answers_with_the_raw_messages_it_matched(under_test: MailboxUnderTest) -> None:
    """A search the server accepts returns `RawEmail`s: a uid and the bytes to parse.

    The reader parses these with the stdlib, so raw must really be the RFC822 message and the
    uid must be the string a later `fetch` is given back.
    """
    found = list(under_test.mailbox.search(under_test.folder, "ALL", 5))
    assert found
    assert all(item.uid and item.raw.startswith(b"From:") for item in found)


def a_refused_search_raises_the_port_s_own_error(under_test: MailboxUnderTest) -> None:
    """A query the server refuses crosses the port as `SearchRefusedError`, carrying that query.

    The type is the contract: an implementation letting its library's exception out makes a
    query the model can fix indistinguishable from a mailbox that is down, and a caller cannot
    catch what it cannot name. The `query` field is what makes the refusal answerable, since the
    text the server was given is not otherwise anywhere the caller can reach.
    """
    under_test.refuse_searches()
    with pytest.raises(SearchRefusedError) as raised:
        under_test.mailbox.search(under_test.folder, REFUSED_QUERY, 5)
    assert raised.value.query == REFUSED_QUERY


def a_refusal_says_what_to_do_and_never_what_the_wire_said(under_test: MailboxUnderTest) -> None:
    """The refusal a model reads names the query and the dialect, never the server's answer.

    Two halves, and the port owes both. What must be there is the correction: the refused query
    and where the dialect is written down, so the next attempt is a rewrite rather than a second
    guess. What must not be there is any fragment of `WIRE_ANSWER`, an offset into a command the
    model never composed, from a library nothing ever told it about.
    """
    under_test.refuse_searches()
    with pytest.raises(SearchRefusedError) as raised:
        under_test.mailbox.search(under_test.folder, REFUSED_QUERY, 5)
    message = str(raised.value)
    assert REFUSED_QUERY in message
    assert "query field's own description" in message
    for fragment in ("offset", "expected space", "UID command"):
        assert fragment not in message


ALL_CHECKS: Sequence[Check] = (
    folders_come_back_as_plain_names,
    a_search_answers_with_the_raw_messages_it_matched,
    a_refused_search_raises_the_port_s_own_error,
    a_refusal_says_what_to_do_and_never_what_the_wire_said,
)
