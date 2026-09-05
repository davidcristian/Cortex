"""The `Mailbox` contract, run over every implementation (AGENTS.md: ports before adapters)."""

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
SELECT_ANSWER_FRAGMENTS = ("Response status", "no such mailbox", "Data:")
# A uid past anything a mailbox has assigned, so no message in any fixture's folder has it.
MISSING_UID = "4294967290"
IMPOSSIBLE_UIDS = ("abc", "0", "2,1", "1:*", "4294967296", "")


@dataclass(frozen=True, slots=True)
class MailboxUnderTest:
    """One implementation, the folder it has messages in, and what the checks need arranged."""

    mailbox: Mailbox
    folder: str
    refuse_searches: Callable[[], None]
    break_folder_opening: Callable[[], None]
    decline_reads: Callable[[], None]
    # A name this implementation's server lists and no mailbox has: a node in the hierarchy.
    # It is not a knob, because no method can make a server grow one; each fixture is built
    # over a server that already has it, the live one included.
    hierarchy_node: str
    # A folder this implementation's server has that holds no mail, so a read in it is asking
    # about a message in a place that has none. Not a knob either: every fixture is built over
    # a server that has one.
    empty_folder: str
    # The uid of the read `decline_reads` arranges. On the fakes the knob declines every read, so
    # any uid serves and this default is one no message has; on a server that declines one
    # message and no other, the probe's sealed one, it is that message's uid.
    declined_uid: str = MISSING_UID


type Check = Callable[[MailboxUnderTest], None]


def folders_come_back_as_plain_names(under_test: MailboxUnderTest) -> None:
    """`list_folders` answers with the names a later call may be given, and nothing else."""
    folders = list(under_test.mailbox.list_folders())
    assert folders
    assert all(type(name) is str for name in folders)
    assert under_test.folder in folders


def a_listed_name_is_never_one_the_port_calls_unknown(under_test: MailboxUnderTest) -> None:
    """`list_folders` offers no name that a later call would refuse as a folder no mailbox has."""
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
    """Dropping the node from the list does not make the name work, and must not pretend it does."""
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
    """A query the server refuses crosses the port as `SearchRefusedError`, carrying that query."""
    under_test.refuse_searches()
    with pytest.raises(SearchRefusedError) as raised:
        under_test.mailbox.search(under_test.folder, REFUSED_QUERY, 5)
    assert raised.value.query == REFUSED_QUERY


def a_refusal_says_what_to_do_and_never_what_the_wire_said(under_test: MailboxUnderTest) -> None:
    """The refusal a model reads names the query and the dialect, never the server's answer."""
    under_test.refuse_searches()
    with pytest.raises(SearchRefusedError) as raised:
        under_test.mailbox.search(under_test.folder, REFUSED_QUERY, 5)
    message = str(raised.value)
    assert REFUSED_QUERY in message
    assert "query field's own description" in message
    for fragment in ("offset", "expected space", "UID command"):
        assert fragment not in message


def a_folder_no_mailbox_has_raises_the_port_s_own_error(under_test: MailboxUnderTest) -> None:
    """Both calls that take a folder answer an unlisted name with `FolderUnknownError`."""
    assert INVENTED_FOLDER not in list(under_test.mailbox.list_folders())
    with pytest.raises(FolderUnknownError) as searched:
        under_test.mailbox.search(INVENTED_FOLDER, "ALL", 5)
    assert searched.value.folder == INVENTED_FOLDER
    with pytest.raises(FolderUnknownError) as read:
        under_test.mailbox.fetch(INVENTED_FOLDER, "1")
    assert read.value.folder == INVENTED_FOLDER


def an_unknown_folder_says_where_the_real_names_are(under_test: MailboxUnderTest) -> None:
    """The message a model reads names the folder and `list_folders`, never the server's answer."""
    with pytest.raises(FolderUnknownError) as raised:
        under_test.mailbox.search(INVENTED_FOLDER, "ALL", 5)
    message = str(raised.value)
    assert INVENTED_FOLDER in message
    assert "list_folders" in message
    for fragment in SELECT_ANSWER_FRAGMENTS:
        assert fragment not in message


def a_name_no_mailbox_could_have_is_one_no_mailbox_has(under_test: MailboxUnderTest) -> None:
    """A folder argument that could never name a mailbox is the same correction as a wrong one."""
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
    """A folder that fails to open for any other reason stays the base error, never the guess."""
    under_test.break_folder_opening()
    with pytest.raises(MailboxError) as raised:
        under_test.mailbox.search(under_test.folder, "ALL", 5)
    assert not isinstance(raised.value, FolderUnknownError)


def a_fetch_answers_the_message_a_search_named(under_test: MailboxUnderTest) -> None:
    """`fetch` of a uid `search` returned is that message, whole, under that uid."""
    found = list(under_test.mailbox.search(under_test.folder, "ALL", 5))
    assert found
    read = under_test.mailbox.fetch(under_test.folder, found[0].uid)
    assert read is not None
    assert read.uid == found[0].uid
    assert read.raw.startswith(b"From:")


def a_uid_no_message_has_is_answered_as_not_there(under_test: MailboxUnderTest) -> None:
    """A uid nothing in the folder carries comes back ``None``, whichever kind of folder it is."""
    assert list(under_test.mailbox.search(under_test.folder, "ALL", 1))
    assert under_test.mailbox.fetch(under_test.folder, MISSING_UID) is None
    assert list(under_test.mailbox.search(under_test.empty_folder, "ALL", 1)) == []
    assert under_test.mailbox.fetch(under_test.empty_folder, MISSING_UID) is None


def a_uid_no_message_could_have_is_answered_as_not_there(under_test: MailboxUnderTest) -> None:
    """A string that is not a uid names no message, so the answer is that none has it."""
    for uid in IMPOSSIBLE_UIDS:
        assert under_test.mailbox.fetch(under_test.folder, uid) is None, uid


def a_read_the_server_declined_is_not_reported_as_not_there(under_test: MailboxUnderTest) -> None:
    """A read the server would not perform stays the base error, never the not-there answer."""
    under_test.decline_reads()
    with pytest.raises(MailboxError) as raised:
        under_test.mailbox.fetch(under_test.folder, under_test.declined_uid)
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
    a_fetch_answers_the_message_a_search_named,
    a_uid_no_message_has_is_answered_as_not_there,
    a_uid_no_message_could_have_is_answered_as_not_there,
    a_read_the_server_declined_is_not_reported_as_not_there,
)
