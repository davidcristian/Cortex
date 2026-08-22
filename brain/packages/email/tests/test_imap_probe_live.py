"""ImapMailbox against a second real IMAP server, the local probe (ADR-0022 two-server addendum)."""

import imaplib
import os
import ssl
from collections.abc import Sequence

import pytest
from mailbox_contract import (
    MailboxUnderTest,
    a_folder_that_could_not_be_opened_is_not_reported_missing,
    a_hierarchy_node_is_still_refused_when_a_caller_names_it,
    a_listed_name_is_never_one_the_port_calls_unknown,
    a_name_no_mailbox_could_have_is_one_no_mailbox_has,
)
from pydantic import SecretStr

from cortex_email import EmailConfig, FolderUnknownError, ImapMailbox, MailboxError

# The mailbox the probe leaves this account lookup rights only: listed, real, and refusing to
# open. It is the whole reason the stack exists.
GUARDED_FOLDER = "Guarded"
# A hierarchy node with a child and no mailbox of its own, which this server lists and then
# refuses as missing. The Bridge's own \Noselect parents open instead.
NOSELECT_PARENT = "Parent"
# That node's child, which is a real mailbox and opens. It is what makes dropping the parent
# lossless: the prefix is still on the list, spelled as part of a name that works.
NODE_CHILD = "Parent/Child"
# A name no mailbox has, and the shape of guess `FOLDER_HELP` warns a model against.
INVENTED_FOLDER = "Nonexistent"
# The one folder the probe leaves openable, so a run proves the login and the read path before
# it asks about any refusal.
REAL_FOLDER = "INBOX"
# The name the fixture subscribes the account to without building a mailbox for it, which is the
# only way to make this server send RFC 5258's `\NonExistent`: it refuses a SUBSCRIBE of a name
# no mailbox has, so the subscription is written into its own file rather than asked for here.
GHOST_SUBSCRIPTION = "Ghost"
IMPOSSIBLE_NAMES = ("Parent/", "/Parent", "Parent//Child", "INBOX/../etc")
# No password is checked (docker/dovecot/probe.conf), so this is a formality the IMAP dialogue
# requires rather than a secret of anything, and it is one word because both halves of a login
# that nothing verifies are the same nothing.
PROBE_LOGIN = "probe"


def _probe_address() -> tuple[str, int]:
    """Where the probe answers, or a skip when the stack is not up."""
    port = os.environ.get("CORTEX_EMAIL_PROBE_PORT", "")
    if not port:
        pytest.skip("run `just up-imap-probe`, then `just email-folder-probe` to reach the probe")
    return os.environ.get("CORTEX_EMAIL_PROBE_HOST", "127.0.0.1"), int(port)


def probe_mailbox() -> ImapMailbox:
    """The probe as `ImapMailbox` sees it. The self-signed cert is accepted as the Bridge's is."""
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
    """The same server over raw imaplib, for the one question imap-tools cannot be asked."""
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
    """The contrast case, live: the assumption the whole classification rests on."""
    mailbox = probe_mailbox()
    assert GUARDED_FOLDER in list(mailbox.list_folders())
    a_folder_that_could_not_be_opened_is_not_reported_missing(
        MailboxUnderTest(
            mailbox=mailbox,
            folder=GUARDED_FOLDER,
            refuse_searches=_nothing,
            break_folder_opening=_nothing,
            hierarchy_node=NOSELECT_PARENT,
        )
    )
    with pytest.raises(MailboxError) as searched:
        mailbox.search(GUARDED_FOLDER, "ALL", 1)
    with pytest.raises(MailboxError) as read:
        mailbox.fetch(GUARDED_FOLDER, "1")
    for raised in (searched, read):
        assert not isinstance(raised.value, FolderUnknownError)
        # The words themselves, which are the evidence: RFC 5530's code for a mailbox that is
        # there and not available to this account, and nothing a missing folder ever says.
        assert "[NOPERM] Permission denied" in str(raised.value)


@pytest.mark.integration
def test_this_server_says_a_folder_is_missing_in_its_own_words_and_is_still_understood() -> None:
    """The missing case in a second server's wording, which shares no word with the first."""
    mailbox = probe_mailbox()
    assert INVENTED_FOLDER not in list(mailbox.list_folders())
    with pytest.raises(FolderUnknownError) as searched:
        mailbox.search(INVENTED_FOLDER, "ALL", 1)
    with pytest.raises(FolderUnknownError) as read:
        mailbox.fetch(INVENTED_FOLDER, "1")
    for raised in (searched, read):
        assert raised.value.folder == INVENTED_FOLDER
        assert "list_folders" in str(raised.value)
        assert "Response status" not in str(raised.value)  # nothing of imap-tools reaches a model

    assert "NONEXISTENT" not in str(searched.value.__cause__)
    assert "doesn't exist" in str(searched.value.__cause__)


@pytest.mark.integration
def test_the_folder_the_probe_leaves_open_still_opens() -> None:
    """The control: the login, the EXAMINE and the search path all work against this server.

    Without it a refusal proves nothing, since a server that refused everything would pass
    every other test in this file.
    """
    mailbox = probe_mailbox()
    assert REAL_FOLDER in list(mailbox.list_folders())
    assert list(mailbox.search(REAL_FOLDER, "ALL", 1)) == []


@pytest.mark.integration
def test_a_listed_node_that_is_not_a_mailbox_is_never_offered_as_a_folder() -> None:
    """The fix, against the server that made it necessary, and the fact underneath it."""
    mailbox = probe_mailbox()
    under_test = MailboxUnderTest(
        mailbox=mailbox,
        folder=REAL_FOLDER,
        refuse_searches=_nothing,
        break_folder_opening=_nothing,
        hierarchy_node=NOSELECT_PARENT,
    )
    a_listed_name_is_never_one_the_port_calls_unknown(under_test)
    a_hierarchy_node_is_still_refused_when_a_caller_names_it(under_test)
    assert NODE_CHILD in list(mailbox.list_folders())


@pytest.mark.integration
def test_a_name_this_server_will_not_even_consider_is_still_the_folder_correction() -> None:
    """A third fact the same `NO` carries, and the second of the two answers it gets."""
    mailbox = probe_mailbox()
    a_name_no_mailbox_could_have_is_one_no_mailbox_has(
        MailboxUnderTest(
            mailbox=mailbox,
            folder=REAL_FOLDER,
            refuse_searches=_nothing,
            break_folder_opening=_nothing,
            hierarchy_node=NOSELECT_PARENT,
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
def test_the_newer_spelling_of_unselectable_is_a_word_this_server_really_sends() -> None:
    """Where RFC 5258's `\\NonExistent` comes from on a real server, and where it does not."""
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


def _named(answer: tuple[str, Sequence[bytes | tuple[bytes, bytes] | None]]) -> dict[str, str]:
    """The flags a LIST answered with, per name, read off the wire lines imaplib hands back."""
    lines = (line.decode() for line in answer[1] if isinstance(line, bytes))
    return {line.rsplit(" ", 1)[-1]: line.split(") ", 1)[0] + ")" for line in lines}


def _nothing() -> None:
    """Do nothing, for a contract knob whose state this server is already in."""
