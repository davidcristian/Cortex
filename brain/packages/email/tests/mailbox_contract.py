"""The `Mailbox` contract, run over every implementation (AGENTS.md: ports before adapters).

The port returns messages, and until a call cannot be answered as asked that is all any check can
see. The failures are the other half of the port, and two of the three are ones a caller can act
on, one per argument it guessed. A folder no mailbox has needs no arrangement, only
a name `list_folders` did not return, which is exactly the mistake the tool descriptions warn
about. The other two are conditions of the world no method can create, so each fixture supplies
them as knobs: **the server refuses the next search**, and **the next folder cannot be opened for
a reason that is not its name**. A third condition is no knob at all, because nothing can make a
server grow one mid-test: **a name its LIST answers with that is only a node in the hierarchy**,
which every fixture is built over and names as `hierarchy_node`.

A fake has no server to do any of that, so it satisfies the knobs by being scripted to raise what
the port owes, the same honest widening the `Embedder` contract's broken-backend knob uses: the
checks state what an implementation must *do* when an answer comes back, not what the wire said.

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
# A name no mailbox could have rather than one no mailbox happens to have, which is the other
# way a folder argument goes wrong and the one the two servers describe differently: a Bridge
# calls the empty name no such mailbox and the probe's Dovecot refuses to read it as a name.
IMPOSSIBLE_FOLDER = ""
# The pieces of what imap-tools says when a real Bridge refuses the SELECT of that name. It reads
# `Response status "OK" expected, but "NO" received. Data: [b'no such mailbox']` in full, verbatim
# from a live pass: a command status reported to a caller that sent no command, so no
# implementation may pass any of it on either.
SELECT_ANSWER_FRAGMENTS = ("Response status", "no such mailbox", "Data:")


@dataclass(frozen=True, slots=True)
class MailboxUnderTest:
    """One implementation, the folder it has messages in, and what the checks need arranged."""

    mailbox: Mailbox
    folder: str
    refuse_searches: Callable[[], None]
    break_folder_opening: Callable[[], None]
    # A name this implementation's server lists and no mailbox has: a node in the hierarchy.
    # It is not a knob, because no method can make a server grow one; each fixture is built
    # over a server that already has it, the live one included.
    hierarchy_node: str


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


def a_listed_name_is_never_one_the_port_calls_unknown(under_test: MailboxUnderTest) -> None:
    """`list_folders` offers no name that a later call would refuse as a folder no mailbox has.

    The loop this closes: a server lists a node of its folder hierarchy, which is a name and not
    a mailbox, and refuses to open it in the very words that prove a folder missing. A caller
    handed that name is told the folder does not exist and told to read `list_folders`, which is
    where the name came from. So the filtering belongs to the implementation, on the call that
    offers the names, and every name offered has to survive being used.
    """
    folders = list(under_test.mailbox.list_folders())
    assert under_test.hierarchy_node not in folders
    for name in folders:
        try:
            under_test.mailbox.search(name, "ALL", 1)
        except FolderUnknownError as unknown:
            pytest.fail(f"list_folders offered {unknown.folder}, which the port calls unknown")
        except MailboxError:
            pass  # A mailbox that is really there and will not open is not this check's subject.


def a_hierarchy_node_is_still_refused_when_a_caller_names_it(under_test: MailboxUnderTest) -> None:
    """Dropping the node from the list does not make the name work, and must not pretend it does.

    A caller can still arrive with the name, out of an old list or a guess, and the honest answer
    is the one a server gives: no mailbox has it. This is the half of the fix that stays true
    whatever `list_folders` does, and it is why the filtering is a correction to the list rather
    than to the classification.
    """
    with pytest.raises(FolderUnknownError) as raised:
        under_test.mailbox.search(under_test.hierarchy_node, "ALL", 5)
    assert raised.value.folder == under_test.hierarchy_node


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


def a_name_no_mailbox_could_have_is_one_no_mailbox_has(under_test: MailboxUnderTest) -> None:
    """A folder argument that could never name a mailbox is the same correction as a wrong one.

    The port owes one answer here even though the servers behind it give two. A ProtonMail
    Bridge refuses the empty name with the `no such mailbox` it gives every other wrong name,
    and the probe's Dovecot refuses to read it as a mailbox name at all, `[CANNOT] Invalid
    mailbox name: Name is empty`, which is RFC 5530 for a request that can never succeed. Both
    are a name `list_folders` did not return and never could, so a caller is owed the correction
    that names the list rather than a base error indistinguishable from the mailbox being down
    (ADR-0022 refused-name addendum).
    """
    assert IMPOSSIBLE_FOLDER not in list(under_test.mailbox.list_folders())
    with pytest.raises(FolderUnknownError) as searched:
        under_test.mailbox.search(IMPOSSIBLE_FOLDER, "ALL", 5)
    assert searched.value.folder == IMPOSSIBLE_FOLDER
    with pytest.raises(FolderUnknownError) as read:
        under_test.mailbox.fetch(IMPOSSIBLE_FOLDER, "1")
    assert read.value.folder == IMPOSSIBLE_FOLDER


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
    a_listed_name_is_never_one_the_port_calls_unknown,
    a_hierarchy_node_is_still_refused_when_a_caller_names_it,
    a_search_answers_with_the_raw_messages_it_matched,
    a_refused_search_raises_the_port_s_own_error,
    a_refusal_says_what_to_do_and_never_what_the_wire_said,
    a_folder_no_mailbox_has_raises_the_port_s_own_error,
    an_unknown_folder_says_where_the_real_names_are,
    a_name_no_mailbox_could_have_is_one_no_mailbox_has,
    a_folder_that_could_not_be_opened_is_not_reported_missing,
)
