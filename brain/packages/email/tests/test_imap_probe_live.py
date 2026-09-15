import imaplib
import os
import ssl
from collections.abc import Sequence

import pytest
from mailbox_contract import (
    MISSING_UID,
    MailboxUnderTest,
    a_folder_that_could_not_be_opened_is_not_reported_missing,
    a_hierarchy_node_is_still_refused_when_a_caller_names_it,
    a_listed_name_is_never_one_the_port_calls_unknown,
    a_name_no_mailbox_could_have_is_one_no_mailbox_has,
    a_read_the_server_declined_is_not_reported_as_not_there,
    a_search_of_a_folder_holding_no_mail_matches_nothing,
    a_uid_no_message_could_have_is_answered_as_not_there,
)
from pydantic import SecretStr

from cortex_email import EmailConfig, FolderUnknownError, ImapMailbox, MailboxError

GUARDED_FOLDER = "Guarded"
NOSELECT_PARENT = "Parent"
NODE_CHILD = "Parent/Child"
INVENTED_FOLDER = "Nonexistent"
REAL_FOLDER = "INBOX"
GHOST_SUBSCRIPTION = "Ghost"
FEIGNED_FOLDER = "Feigned"
FOLLOWED_SUBSCRIPTION = "Feigned/Followed"
SEALED_FOLDER = "Sealed"
SEALED_UID = "1"
IMPOSSIBLE_NAMES = ("Parent/", "/Parent", "Parent//Child", "INBOX/../etc")
PROBE_LOGIN = "probe"


def _probe_address() -> tuple[str, int]:
    """Return the host and port the probe answers on, or skip when the stack is not up."""
    port = os.environ.get("CORTEX_EMAIL_PROBE_PORT", "")
    if not port:
        pytest.skip("run `just up-imap-probe`, then `just email-folder-probe` to reach the probe")
    return os.environ.get("CORTEX_EMAIL_PROBE_HOST", "127.0.0.1"), int(port)


def probe_mailbox() -> ImapMailbox:
    """Build an `ImapMailbox` on the probe."""
    host, port = _probe_address()
    config = EmailConfig(
        host=host,
        port=port,
        user=PROBE_LOGIN,
        password=SecretStr(PROBE_LOGIN),
        security="starttls",
        tls_insecure=True,
    )
    return ImapMailbox(config)


def probe_dialogue() -> imaplib.IMAP4:
    """Open the same server over raw imaplib, for the one question imap-tools cannot be asked."""
    host, port = _probe_address()
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    conn = imaplib.IMAP4(host, port)
    conn.starttls(context)
    conn.login(PROBE_LOGIN, PROBE_LOGIN)
    return conn


@pytest.mark.integration
def test_a_mailbox_that_exists_and_will_not_open_is_never_reported_missing() -> None:
    mailbox = probe_mailbox()
    assert GUARDED_FOLDER in list(mailbox.list_folders())
    a_folder_that_could_not_be_opened_is_not_reported_missing(
        MailboxUnderTest(
            mailbox=mailbox,
            folder=GUARDED_FOLDER,
            refuse_searches=_nothing,
            break_folder_opening=_nothing,
            decline_reads=_nothing,
            hierarchy_node=NOSELECT_PARENT,
            empty_folder=REAL_FOLDER,
        )
    )
    with pytest.raises(MailboxError) as searched:
        mailbox.search(GUARDED_FOLDER, "ALL", 1)
    with pytest.raises(MailboxError) as read:
        mailbox.fetch(GUARDED_FOLDER, "1")
    for raised in (searched, read):
        assert not isinstance(raised.value, FolderUnknownError)
        assert "[NOPERM] Permission denied" in str(raised.value)


@pytest.mark.integration
def test_a_message_this_server_will_not_read_is_never_reported_missing() -> None:
    mailbox = probe_mailbox()
    assert SEALED_FOLDER in list(mailbox.list_folders())
    a_read_the_server_declined_is_not_reported_as_not_there(
        MailboxUnderTest(
            mailbox=mailbox,
            folder=SEALED_FOLDER,
            refuse_searches=_nothing,
            break_folder_opening=_nothing,
            decline_reads=_nothing,
            hierarchy_node=NOSELECT_PARENT,
            empty_folder=REAL_FOLDER,
            declined_uid=SEALED_UID,
        )
    )
    with pytest.raises(MailboxError) as read:
        mailbox.fetch(SEALED_FOLDER, SEALED_UID)
    with pytest.raises(MailboxError) as searched:
        mailbox.search(SEALED_FOLDER, "ALL", 1)
    for raised in (read, searched):
        assert not isinstance(raised.value, FolderUnknownError)
        assert "[SERVERBUG] Internal error occurred" in str(raised.value)
    assert mailbox.fetch(SEALED_FOLDER, MISSING_UID) is None
    with probe_dialogue() as conn:
        assert conn.select(f'"{SEALED_FOLDER}"', readonly=True) == ("OK", [b"1"])
        status, data = conn.uid("FETCH", SEALED_UID, "(BODY.PEEK[] UID FLAGS RFC822.SIZE)")
        assert status == "NO"
        assert isinstance(data[0], bytes)
        assert data[0].startswith(b"[SERVERBUG] Internal error occurred")
        assert conn.noop()[0] == "OK"


@pytest.mark.integration
def test_this_server_says_a_folder_is_missing_in_its_own_words_and_is_still_understood() -> None:
    mailbox = probe_mailbox()
    assert INVENTED_FOLDER not in list(mailbox.list_folders())
    with pytest.raises(FolderUnknownError) as searched:
        mailbox.search(INVENTED_FOLDER, "ALL", 1)
    with pytest.raises(FolderUnknownError) as read:
        mailbox.fetch(INVENTED_FOLDER, "1")
    for raised in (searched, read):
        assert raised.value.folder == INVENTED_FOLDER
        assert "list_folders" in str(raised.value)
        assert "Response status" not in str(raised.value)

    assert "NONEXISTENT" not in str(searched.value.__cause__)
    assert "doesn't exist" in str(searched.value.__cause__)


@pytest.mark.integration
def test_the_folder_the_probe_leaves_open_still_opens() -> None:
    mailbox = probe_mailbox()
    assert REAL_FOLDER in list(mailbox.list_folders())
    assert list(mailbox.search(REAL_FOLDER, "ALL", 1)) == []


@pytest.mark.integration
def test_a_listed_node_that_is_not_a_mailbox_is_never_offered_as_a_folder() -> None:
    mailbox = probe_mailbox()
    under_test = MailboxUnderTest(
        mailbox=mailbox,
        folder=REAL_FOLDER,
        refuse_searches=_nothing,
        break_folder_opening=_nothing,
        decline_reads=_nothing,
        hierarchy_node=NOSELECT_PARENT,
        empty_folder=REAL_FOLDER,
    )
    a_listed_name_is_never_one_the_port_calls_unknown(under_test)
    a_hierarchy_node_is_still_refused_when_a_caller_names_it(under_test)
    assert NODE_CHILD in list(mailbox.list_folders())


@pytest.mark.integration
def test_a_name_this_server_will_not_even_consider_is_still_the_folder_correction() -> None:
    mailbox = probe_mailbox()
    a_name_no_mailbox_could_have_is_one_no_mailbox_has(
        MailboxUnderTest(
            mailbox=mailbox,
            folder=REAL_FOLDER,
            refuse_searches=_nothing,
            break_folder_opening=_nothing,
            decline_reads=_nothing,
            hierarchy_node=NOSELECT_PARENT,
            empty_folder=REAL_FOLDER,
        )
    )
    with pytest.raises(FolderUnknownError) as raised:
        mailbox.search("", "ALL", 1)
    assert "[CANNOT] Invalid mailbox name" not in str(raised.value)
    assert "[CANNOT] Invalid mailbox name" in str(raised.value.__cause__)

    for name in IMPOSSIBLE_NAMES:
        with pytest.raises(FolderUnknownError) as refused:
            mailbox.fetch(name, "1")
        assert refused.value.folder == name
        assert "Invalid mailbox name" in str(refused.value.__cause__)


@pytest.mark.integration
def test_a_uid_no_message_has_is_not_there_in_this_server_s_empty_folders() -> None:
    mailbox = probe_mailbox()
    assert list(mailbox.search(REAL_FOLDER, "ALL", 1)) == []
    assert mailbox.fetch(REAL_FOLDER, MISSING_UID) is None
    under_test = MailboxUnderTest(
        mailbox=mailbox,
        folder=REAL_FOLDER,
        refuse_searches=_nothing,
        break_folder_opening=_nothing,
        decline_reads=_nothing,
        hierarchy_node=NOSELECT_PARENT,
        empty_folder=REAL_FOLDER,
    )
    a_uid_no_message_could_have_is_answered_as_not_there(under_test)
    a_search_of_a_folder_holding_no_mail_matches_nothing(under_test)
    with probe_dialogue() as conn:
        assert conn.select(f'"{REAL_FOLDER}"', readonly=True) == ("OK", [b"0"])
        assert conn.uid("SEARCH", "UID", MISSING_UID) == ("OK", [b""])
        assert conn.uid("FETCH", MISSING_UID, "(UID)") == ("OK", [None])


@pytest.mark.integration
def test_the_newer_spelling_of_unselectable_is_a_word_this_server_really_sends() -> None:
    with probe_dialogue() as conn:
        conn.xatom("LIST", "(SUBSCRIBED)", '""', '"*"')
        subscribed = _named(conn.response("LIST"))
        conn.xatom("LIST", '""', '"*"', "RETURN (CHILDREN)")
        extended = _named(conn.response("LIST"))
        plain = _named(conn.list())
    assert subscribed[GHOST_SUBSCRIPTION] == "(\\Subscribed \\NonExistent)"
    assert extended[NOSELECT_PARENT] == "(\\Noselect \\HasChildren)"
    assert GHOST_SUBSCRIPTION not in plain
    assert plain[NOSELECT_PARENT] == "(\\Noselect \\HasChildren)"
    assert GHOST_SUBSCRIPTION not in list(probe_mailbox().list_folders())


@pytest.mark.integration
def test_a_name_this_server_calls_unselectable_and_opens_anyway_is_a_real_thing() -> None:
    with probe_dialogue() as conn:
        subscribed_tree = _named(conn.lsub('""', '"%"'))
        plain = _named(conn.list())
    assert subscribed_tree[FEIGNED_FOLDER] == "(\\Noselect)"
    plain_flags = set(plain[FEIGNED_FOLDER].strip("()").split())
    assert "\\HasChildren" in plain_flags
    assert not plain_flags & {"\\Noselect", "\\NonExistent"}

    mailbox = probe_mailbox()
    offered = list(mailbox.list_folders())
    assert FEIGNED_FOLDER in offered
    assert FOLLOWED_SUBSCRIPTION in offered
    assert list(mailbox.search(FEIGNED_FOLDER, "ALL", 1)) == []


def _named(answer: tuple[str, Sequence[bytes | tuple[bytes, bytes] | None]]) -> dict[str, str]:
    """Read the flags a LIST answered with, per name, off the wire lines imaplib hands back."""
    lines = (line.decode() for line in answer[1] if isinstance(line, bytes))
    return {line.rsplit(" ", 1)[-1]: line.split(") ", 1)[0] + ")" for line in lines}


def _nothing() -> None:
    """Do nothing, for a contract condition this server is already in."""
