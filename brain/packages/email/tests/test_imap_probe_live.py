"""ImapMailbox against a second real IMAP server, the local probe (ADR-0022 two-server addendum).

Integration-marked: needs the probe stack up (`just up-imap-probe`), never runs in CI. Run it
with `just email-folder-probe`, which finds where the server answers and passes host and port in;
CORTEX_EMAIL_PROBE_PORT unset means the stack is not up and every test here skips. The stack is
docker/docker-compose.imap-probe.yml, and its four listed names, of which three are mailboxes and
one is a `\\Noselect` node that is not, are built by docker/dovecot/probe-mailboxes.sh, whose
header says what each is for. A fifth name is subscribed and not there, which is the one way to
make this server send RFC 5258's newer word for a name that is not a mailbox.

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
    ""            NO [CANNOT] Invalid mailbox name: Name is empty (0.001 + 0.000 secs).

with no RFC 5530 response code on the missing one, exactly as the Bridge sends none, and one on
the name it will not read as a name, where the Bridge says `no such mailbox` instead.
"""

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
# Four shapes of name this server refuses to read as a mailbox name at all, each answered with
# RFC 5530's `[CANNOT]` and its own reason: a trailing separator, a leading one, two of them
# together, and a relative path. They are here rather than in the unit suite because they are
# the realistic half of that refusal, a model writing `Folders/` from a prefix it saw in a list.
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
    """The same server over raw imaplib, for the one question imap-tools cannot be asked.

    `folder.list()` sends the plain `LIST "" "*"` and nothing else, so a listing carrying a
    selection option has to be composed here. Everything else in this file goes through the port,
    which is the point of the file; this reaches past it to measure what the server itself sends.
    """
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
def test_a_listed_node_that_is_not_a_mailbox_is_never_offered_as_a_folder() -> None:
    """The fix, against the server that made it necessary, and the fact underneath it.

    This server's LIST answers with a Noselect parent and then refuses a SELECT of it exactly as
    it refuses a name no mailbox has, so nothing in the refusal could tell them apart and the
    filtering has to happen on the call that offers the names. `list_folders` drops it; naming it
    anyway is still refused, because the name really is not a mailbox; and its child is offered
    in its own right, so the tree stays reachable and only the unusable name is gone. The
    Bridge's own Noselect parents open instead, which is why this is measured here.

    The port's own two checks run over the live server rather than being restated, with the
    fixture's knobs doing nothing: this server needs no arranging for any of it.
    """
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
    """A third fact the same `NO` carries, and the second of the two answers it gets.

    The Bridge answers an empty folder name with the same `no such mailbox` it gives every other
    wrong name, and this server refuses to read it as a name at all. Nothing in its prose says
    anything about a mailbox, so the classification turns on RFC 5530's `[CANNOT]` instead, and
    the port's own check runs over the live refusal rather than restating it. The code stays on
    the chained cause, where the operator's traceback keeps everything the model is not told.
    """
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

    # The empty name is the least likely of these to be sent. The others are shapes a model
    # really would write, and this server answers every one of them with the same code and a
    # different reason, each of them about the name and none about the mailbox: a name no
    # mailbox could have is exactly the class `[CANNOT]` marks out.
    for name in IMPOSSIBLE_NAMES:
        with pytest.raises(FolderUnknownError) as refused:
            mailbox.fetch(name, "1")
        assert refused.value.folder == name
        assert "Invalid mailbox name" in str(refused.value.__cause__)


@pytest.mark.integration
def test_the_newer_spelling_of_unselectable_is_a_word_this_server_really_sends() -> None:
    """Where RFC 5258's `\\NonExistent` comes from on a real server, and where it does not.

    Half the unselectable filter was read off a standard and from no server. This is the dialogue
    that settles it, and it is a raw one because imap-tools never asks the question: `folder.list`
    sends the plain `LIST "" "*"` of RFC 3501, and a server may only send the newer word to a LIST
    that carries a selection option (RFC 5258). So three things are asserted at once. The word is
    real and is spelled the way the filter spells it. It arrives instead of `\\Noselect` rather
    than beside it, and on a different name: the hierarchy node keeps the older word even when the
    LIST asks for return options, while the newer one belongs to a subscribed name no mailbox has.
    And the listing the adapter really makes carries neither that name nor that word, which is why
    reading it is a defence against a server this repo has not met rather than a live code path.
    """
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
    """The flags a LIST answered with, per name, read off the wire lines imaplib hands back.

    Raw rather than through `FolderInfo` on purpose: what is being measured here is what the
    server sent, and imap-tools cannot be asked the question at all. imaplib splits a line whose
    name arrived as a literal into a pair, which this server never does for the plain names it
    holds; such a pair is skipped rather than guessed at, so a fixture that grew a quoted name
    would go missing from this reading instead of being misread into it.
    """
    lines = (line.decode() for line in answer[1] if isinstance(line, bytes))
    return {line.rsplit(" ", 1)[-1]: line.split(") ", 1)[0] + ")" for line in lines}


def _nothing() -> None:
    """Do nothing, for a contract knob whose state this server is already in."""
