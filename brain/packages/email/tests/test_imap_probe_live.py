"""ImapMailbox against a second real IMAP server, the local probe (ADR-0022 two-server addendum).

Integration-marked: needs the probe stack up (`just up-imap-probe`), never runs in CI. Run it
with `just email-folder-probe`, which finds where the server answers and passes host and port in;
CORTEX_EMAIL_PROBE_PORT unset means the stack is not up and every test here skips. The stack is
docker/docker-compose.imap-probe.yml, and its four listed names, of which three are mailboxes and
one is a `\\Noselect` node that is not, are built by docker/dovecot/probe-mailboxes.sh, whose
header says what each is for.

Why a second server. A `NO` to `SELECT` covers two facts, a mailbox that does not exist and a
mailbox that does and cannot be opened, and `ImapMailbox` types the first and only the first.
The Bridge in `test_email_live.py` can produce only the first: every wrong name is refused in
the same words and every folder it lists opens. This server produces both, so what was an
assumption (a real "there but shut" refusal says none of the things a missing one says) is
measured here instead. It is also a second wording for the missing case, which is why the
classification reads two measured phrases rather than one.

Every answer asserted on below was measured through `ImapMailbox` against dovecot/dovecot
2.3.21 (47349e2482), verbatim:

    Nonexistent   NO Mailbox doesn't exist: Nonexistent (0.001 + 0.000 secs).
    Guarded       NO [NOPERM] Permission denied (0.001 + 0.000 secs).
    Parent        NO Mailbox doesn't exist: Parent (0.001 + 0.000 secs).

with no RFC 5530 response code on the missing one, exactly as the Bridge sends none.
"""

import os

import pytest
from mailbox_contract import (
    MailboxUnderTest,
    a_folder_that_could_not_be_opened_is_not_reported_missing,
)
from pydantic import SecretStr

from cortex_email import EmailConfig, FolderUnknownError, ImapMailbox, MailboxError

# The mailbox the probe leaves this account lookup rights only: listed, real, and refusing to
# open. It is the whole reason the stack exists.
GUARDED_FOLDER = "Guarded"
# A hierarchy node with a child and no mailbox of its own, which this server lists and then
# refuses as missing. The Bridge's own \Noselect parents open instead.
NOSELECT_PARENT = "Parent"
# A name no mailbox has, and the shape of guess `FOLDER_HELP` warns a model against.
INVENTED_FOLDER = "Nonexistent"
# The one folder the probe leaves openable, so a run proves the login and the read path before
# it asks about any refusal.
REAL_FOLDER = "INBOX"


def probe_mailbox() -> ImapMailbox:
    """The probe as `ImapMailbox` sees it, or a skip when the stack is not up.

    No password is checked (docker/dovecot/probe.conf), so the credentials here are a
    formality the IMAP dialogue requires rather than a secret of anything. The self-signed cert
    is accepted the same way the Bridge's is.
    """
    port = os.environ.get("CORTEX_EMAIL_PROBE_PORT", "")
    if not port:
        pytest.skip("run `just up-imap-probe`, then `just email-folder-probe` to reach the probe")
    config = EmailConfig(
        host=os.environ.get("CORTEX_EMAIL_PROBE_HOST", "127.0.0.1"),
        port=int(port),
        user="probe",
        password=SecretStr("probe"),
        security="starttls",
        tls_insecure=True,
    )
    return ImapMailbox(config)


@pytest.mark.integration
def test_a_mailbox_that_exists_and_will_not_open_is_never_reported_missing() -> None:
    """The contrast case, live: the assumption the whole classification rests on.

    A real server refusing a real mailbox that a real ACL has shut. Three things have to hold
    at once for the fail-safe rule to mean anything, and only a server that can produce this
    refusal can show them: the folder is listed, so it demonstrably exists; opening it is
    refused; and the refusal is not typed as a missing folder, because none of the phrases that
    prove a folder missing appears in what the server said. The port contract's own check runs
    over it rather than being restated, with nothing to break the folder first: this server has
    it broken already.
    """
    mailbox = probe_mailbox()
    assert GUARDED_FOLDER in list(mailbox.list_folders())
    a_folder_that_could_not_be_opened_is_not_reported_missing(
        MailboxUnderTest(
            mailbox=mailbox,
            folder=GUARDED_FOLDER,
            refuse_searches=_nothing,
            break_folder_opening=_nothing,
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
    """The missing case in a second server's wording, which shares no word with the first.

    The Bridge says `no such mailbox`; this one names the folder and says it doesn't exist.
    Both are read, so a model that invents a name is corrected on either server rather than only
    on the one the phrase was first measured against.
    """
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

    # And the premise the phrase-matching rests on: this server, like the Bridge, sends no
    # response code with a missing mailbox, so there is no machine-readable signal the two
    # share to read instead of their words. The answer itself is on the chained cause, which is
    # the only place any of the library's text survives.
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
def test_a_listed_node_that_is_not_a_mailbox_is_refused_as_missing_here() -> None:
    """Measured, and the one place the two servers disagree about a fact rather than a wording.

    This server lists a Noselect parent and then answers a SELECT of it exactly as it answers a
    name no mailbox has, so the port types it `FolderUnknownError` and sends the model to the
    list that the name is on. The Bridge's own Noselect parents open instead, so the loop cannot
    happen there. It is recorded rather than worked around because the refusal carries nothing
    that could tell it apart: the fix is for `list_folders` to stop offering a name that is not
    a mailbox, which is a change to another call.
    """
    mailbox = probe_mailbox()
    assert NOSELECT_PARENT in list(mailbox.list_folders())
    with pytest.raises(FolderUnknownError):
        mailbox.search(NOSELECT_PARENT, "ALL", 1)


@pytest.mark.integration
def test_a_name_this_server_will_not_even_consider_is_a_third_answer() -> None:
    """A third fact the same `NO` carries: the name is not one a mailbox could have.

    The Bridge answers an empty folder name with the same `no such mailbox` it gives every other
    wrong name, and this server refuses to read it as a name at all. It is neither missing nor
    shut, nothing proves a folder missing in what it says, and so it stays the base error. Pinned
    because it is the case a rule written from one server would not have known existed.
    """
    mailbox = probe_mailbox()
    with pytest.raises(MailboxError) as raised:
        mailbox.search("", "ALL", 1)
    assert not isinstance(raised.value, FolderUnknownError)
    assert "[CANNOT] Invalid mailbox name" in str(raised.value)


def _nothing() -> None:
    """Do nothing, for a contract knob whose state this server is already in."""
