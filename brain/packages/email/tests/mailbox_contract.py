"""The `Mailbox` contract, run over every implementation (AGENTS.md: ports before adapters).

The port returns messages, and until a call cannot be answered as asked that is all any check can
see. The failures are the other half of the port, and two of the three are the half a caller must
be able to act on, one per argument it guessed. A folder no mailbox has needs no arrangement, only
a name `list_folders` did not return, which is exactly the mistake the tool descriptions warn
about. The other two are conditions of the world no method can create, so each fixture supplies
them as knobs: **the server refuses the next search**, and **the next folder cannot be opened for
a reason that is not its name**. A fake has no server to do either, so it satisfies the knobs by
being scripted to raise what the port owes, the same honest widening the `Embedder` contract's
broken-backend knob uses: the checks state what an implementation must *do* when an answer comes
back, not what the wire said.

Driven over the fake and over `ImapMailbox` by `test_mailbox_contract.py`.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import pytest

from cortex_email import FolderUnknownError, Mailbox, MailboxError, SearchRefusedError

# The client syntax a model reaches for, which is what a real Bridge answers BAD to.
REFUSED_QUERY = "from:someone@example.com"
# What imaplib puts in the exception a refused search raises, verbatim from a live Bridge. No
# implementation may pass any of it on: it is an offset into a wire command the model never saw.
WIRE_ANSWER = "UID command error: BAD [b'[Error offset=38]: expected space']"
# A folder name a model could plausibly invent from a mailbox's shape, and one no implementation
# under test lists. Every check that uses it asserts that first, so it cannot rot into a name a
# fixture quietly grew.
INVENTED_FOLDER = "Receipts"
# The pieces of what imap-tools says when a real Bridge refuses the SELECT of that name. It reads
# `Response status "OK" expected, but "NO" received. Data: [b'no such mailbox']` in full, verbatim
# from a live pass: a command status reported to a caller that sent no command, so no
# implementation may pass any of it on either.
SELECT_ANSWER_FRAGMENTS = ("Response status", "no such mailbox", "Data:")


@dataclass(frozen=True, slots=True)
class MailboxUnderTest:
    """One implementation, the folder it has messages in, and the two knobs the checks need."""

    mailbox: Mailbox
    folder: str
    refuse_searches: Callable[[], None]
    break_folder_opening: Callable[[], None]


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


def a_folder_no_mailbox_has_raises_the_port_s_own_error(under_test: MailboxUnderTest) -> None:
    """Both calls that take a folder answer an unlisted name with `FolderUnknownError`.

    The type is the contract, for the refused query's reason, and the folder is the guess rather
    than the query, so it reaches every call that takes one. `read_email` fails on it before it
    has looked at a uid, so answering it with "message not found" would send a model hunting
    through a folder that does not exist for a message that may well be there. The `folder` field
    is what makes the correction answerable: it is the name that was refused, and nothing else
    the caller can reach holds it.
    """
    assert INVENTED_FOLDER not in list(under_test.mailbox.list_folders())
    with pytest.raises(FolderUnknownError) as searched:
        under_test.mailbox.search(INVENTED_FOLDER, "ALL", 5)
    assert searched.value.folder == INVENTED_FOLDER
    with pytest.raises(FolderUnknownError) as read:
        under_test.mailbox.fetch(INVENTED_FOLDER, "1")
    assert read.value.folder == INVENTED_FOLDER


def an_unknown_folder_says_where_the_real_names_are(under_test: MailboxUnderTest) -> None:
    """The message a model reads names the folder and `list_folders`, never the server's answer.

    The correction here is one call rather than a rewrite, so the message has to name that call:
    a model told only that the folder was wrong has no reason to prefer the list over another
    plausible name. What must not be there is any of `SELECT_ANSWER_FRAGMENTS`, a command status
    reported to a caller that never sent a command.
    """
    with pytest.raises(FolderUnknownError) as raised:
        under_test.mailbox.search(INVENTED_FOLDER, "ALL", 5)
    message = str(raised.value)
    assert INVENTED_FOLDER in message
    assert "list_folders" in message
    for fragment in SELECT_ANSWER_FRAGMENTS:
        assert fragment not in message


def a_folder_that_could_not_be_opened_is_not_reported_missing(
    under_test: MailboxUnderTest,
) -> None:
    """A folder that fails to open for any other reason stays the base error, never the guess.

    The fail-safe half of the classification. A server refuses to open a folder for reasons that
    have nothing to do with its name, and the folder here is one `list_folders` returned, so it
    demonstrably exists. Reporting it missing would send a model to the list to look for a name it
    read off that same list, which is a loop; the base error says the mailbox could not answer,
    which is true whichever it was.
    """
    under_test.break_folder_opening()
    with pytest.raises(MailboxError) as raised:
        under_test.mailbox.search(under_test.folder, "ALL", 5)
    assert not isinstance(raised.value, FolderUnknownError)


ALL_CHECKS: Sequence[Check] = (
    folders_come_back_as_plain_names,
    a_search_answers_with_the_raw_messages_it_matched,
    a_refused_search_raises_the_port_s_own_error,
    a_refusal_says_what_to_do_and_never_what_the_wire_said,
    a_folder_no_mailbox_has_raises_the_port_s_own_error,
    an_unknown_folder_says_where_the_real_names_are,
    a_folder_that_could_not_be_opened_is_not_reported_missing,
)
