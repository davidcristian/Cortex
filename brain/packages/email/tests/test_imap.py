"""Behavior tests for ImapMailbox over a fake imap-tools MailBox (no server, no network).

Proves the read-only discipline (EXAMINE via readonly=True, mark_seen=False), the TLS-mode
selection, and that no exception of the IMAP stack escapes the port. The shared `Mailbox`
promises live in `mailbox_contract.py`, which this adapter is driven through too; the live
contract against a real Bridge is `test_email_live.py`.
"""

import ssl
from imaplib import IMAP4

import pytest
from imap_stub import (
    DECLINED_READ_ANSWER,
    DROPPED_READ,
    NONEXISTENT_NODE_FLAGS,
    OPEN_NODE_FLAGS,
    OTHER_MISSING_FOLDER_ANSWER,
    REFUSED_NAME_ANSWER,
    UNOPENABLE_FOLDER_ANSWER,
    FakeBox,
    Msg,
    config,
    patch_box,
)
from imap_tools import MailboxFolderSelectError
from mailbox_contract import IMPOSSIBLE_UIDS

from cortex_email import (
    FolderUnknownError,
    ImapMailbox,
    MailboxError,
    RawEmail,
    SearchRefusedError,
)

_SIMPLE = (
    b"From: Alice <alice@example.com>\r\nSubject: Lunch\r\n"
    b"Date: Fri, 03 Jul 2026 12:00:00 +0000\r\n\r\nLet's do lunch.\r\n"
)


def test_list_folders_logs_in_and_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    box = FakeBox(names=["INBOX", "Archive"])
    captured = patch_box(monkeypatch, box)
    assert list(ImapMailbox(config()).list_folders()) == ["INBOX", "Archive"]
    assert box.login_calls == [("bridge-user", "bridge-pass")]
    assert (captured["host"], captured["port"]) == ("mail.local", 1143)


def test_the_newer_spelling_of_unselectable_is_dropped_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # One server has two words for it: the probe's Dovecot flags a hierarchy node `\Noselect`
    # and keeps RFC 5258's `\NonExistent` for a subscribed name no mailbox has, which it sends
    # only to a LIST that asks for subscriptions. The flags here are that answer verbatim, so
    # the newer spelling is read from a server rather than from the standard, and it is read
    # case-folded because the attribute is an IMAP atom and no server promises its casing.
    box = FakeBox(names=["INBOX"], nodes=["Ghost"], node_flags=NONEXISTENT_NODE_FLAGS)
    patch_box(monkeypatch, box)
    assert list(ImapMailbox(config()).list_folders()) == ["INBOX"]
    assert box.set_calls == [("Ghost", True)]  # the newer word leads to the same single probe


def test_a_flagged_name_the_server_opens_is_still_offered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The Bridge flags the parents of its own hierarchy and opens them, so dropping every flagged
    # name would withhold names that work. The flag only selects which names are probed, and
    # whether the server opens the name is what decides if it is offered.
    box = FakeBox(names=["INBOX"], open_nodes=["Folders"], node_flags=OPEN_NODE_FLAGS)
    patch_box(monkeypatch, box)
    assert list(ImapMailbox(config()).list_folders()) == ["INBOX", "Folders"]
    assert box.set_calls == [("Folders", True)]  # asked once, and only about the flagged name


def test_a_flagged_name_the_server_refuses_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    # Dovecot lists a hierarchy node and then refuses to open it in the words that mean a folder
    # is missing, so an offered name would send the caller straight back to the same refusal.
    box = FakeBox(names=["INBOX"], nodes=["Parent"])
    patch_box(monkeypatch, box)
    assert list(ImapMailbox(config()).list_folders()) == ["INBOX"]
    assert box.set_calls == [("Parent", True)]


def test_search_is_headers_only_read_only_and_unseen(monkeypatch: pytest.MonkeyPatch) -> None:
    box = FakeBox(messages=[Msg("7", b"raw7"), Msg("8", b"raw8")])
    patch_box(monkeypatch, box)
    result = ImapMailbox(config()).search("INBOX", "ALL", 5)
    assert list(result) == [RawEmail("7", b"raw7"), RawEmail("8", b"raw8")]
    assert box.set_calls == [("INBOX", True)]  # EXAMINE, never SELECT
    ((_, limit, headers_only, mark_seen),) = box.fetch_calls
    assert (limit, headers_only, mark_seen) == (5, True, False)


def test_fetch_one_found_is_read_only_and_unseen(monkeypatch: pytest.MonkeyPatch) -> None:
    # One UID FETCH and no search before it, asking for the whole message with PEEK, which is
    # what leaves the Seen flag alone; the uid comes back parsed off the server's own item.
    box = FakeBox(messages=[Msg("7", _SIMPLE)])
    patch_box(monkeypatch, box)
    read = ImapMailbox(config()).fetch("INBOX", "7")
    assert read is not None
    assert (read.uid, read.raw[:6]) == ("7", b"From: ")
    assert box.set_calls == [("INBOX", True)]  # EXAMINE, never SELECT
    assert box.fetch_calls == []  # by uid, with no search for the uid first
    ((command, uid, parts),) = box.client.uid_calls
    assert (command, uid) == ("FETCH", "7")
    assert "BODY.PEEK[]" in parts
    assert "UID" in parts.split()


def test_fetch_one_missing_is_asked_and_answered_with_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The FETCH is sent and the server's OK carries no data, which is the standard's own answer
    # for a uid no message has, so None is read off that rather than off any words.
    box = FakeBox(messages=[])
    patch_box(monkeypatch, box)
    assert ImapMailbox(config()).fetch("INBOX", "999") is None
    assert [call[:2] for call in box.client.uid_calls] == [("FETCH", "999")]


def test_a_read_the_server_declined_keeps_the_library_s_account_of_why(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A NO to the FETCH is the one answer that must not become None, scripted here from the one
    # the probe's Dovecot sends over a message it cannot open. That it is not reported absent is a
    # contract check; what this adds is that the base error carries the server's own text, the
    # only explanation an operator gets for a mailbox that could not answer.
    box = FakeBox(messages=[Msg("7", _SIMPLE)])
    box.fetch_answer = DECLINED_READ_ANSWER
    patch_box(monkeypatch, box)
    with pytest.raises(MailboxError) as raised:
        ImapMailbox(config()).fetch("INBOX", "7")
    assert "could not read that message" in str(raised.value)
    assert "[SERVERBUG]" in str(raised.value)


def test_a_read_the_server_dropped_the_connection_on_is_not_reported_as_not_there(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Under Dovecot's default fetch-failure setting the same declined read is a BYE and a closed
    # connection rather than a NO: the probe's Dovecot, over a message file it cannot open, which
    # imaplib raises as its abort. It crosses the port as the base error carrying that text and
    # never as None, since nothing about a connection that went away says the message is absent.
    box = FakeBox(messages=[Msg("7", _SIMPLE)], fetch_error=DROPPED_READ)
    patch_box(monkeypatch, box)
    with pytest.raises(MailboxError) as raised:
        ImapMailbox(config()).fetch("INBOX", "7")
    assert not isinstance(raised.value, FolderUnknownError)
    assert "Internal error occurred" in str(raised.value)


def test_a_uid_no_message_could_have_sends_no_command(monkeypatch: pytest.MonkeyPatch) -> None:
    # A string that is not a uid is answered here, because the two servers read each of these
    # shapes differently and one of them reads a set or a range as several messages. Nothing
    # reaches the wire, so nothing a server would have answered can leak into the answer.
    box = FakeBox(messages=[Msg("7", _SIMPLE)])
    patch_box(monkeypatch, box)
    for uid in IMPOSSIBLE_UIDS:
        assert ImapMailbox(config()).fetch("INBOX", uid) is None, uid
    assert box.client.uid_calls == []


def test_the_folder_is_checked_before_the_uid(monkeypatch: pytest.MonkeyPatch) -> None:
    # Both arguments can be wrong at once, and the folder correction is the one a model can act
    # on, so a guessed folder is refused before the uid is looked at, as the search refuses it.
    patch_box(monkeypatch, FakeBox(names=["INBOX"]))
    with pytest.raises(FolderUnknownError) as raised:
        ImapMailbox(config()).fetch("Receipts", "abc")
    assert raised.value.folder == "Receipts"


def test_ssl_mode_uses_the_implicit_tls_box(monkeypatch: pytest.MonkeyPatch) -> None:
    box = FakeBox(names=["INBOX"])
    captured = patch_box(monkeypatch, box, "ssl")
    ImapMailbox(config(security="ssl")).list_folders()
    assert captured["host"] == "mail.local"


def test_default_tls_verifies_the_certificate(monkeypatch: pytest.MonkeyPatch) -> None:
    box = FakeBox(names=["INBOX"])
    captured = patch_box(monkeypatch, box)
    ImapMailbox(config()).list_folders()
    context = captured["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED


def test_insecure_tls_disables_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    box = FakeBox(names=["INBOX"])
    captured = patch_box(monkeypatch, box)
    ImapMailbox(config(tls_insecure=True)).list_folders()
    context = captured["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_NONE
    assert context.check_hostname is False


def test_a_connection_lost_mid_search_is_not_reported_as_a_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # imaplib's abort is a subclass of its error, so the classification has to look: a server
    # that went away says nothing about the query, and answering it with "rewrite the search"
    # would send the model round a loop that cannot end.
    box = FakeBox(messages=[], fetch_error=IMAP4.abort("socket error: EOF"))
    patch_box(monkeypatch, box)
    with pytest.raises(MailboxError) as raised:
        ImapMailbox(config()).search("INBOX", "ALL", 5)
    assert not isinstance(raised.value, SearchRefusedError)
    assert "connection dropped" in str(raised.value)


def test_a_select_refused_for_another_reason_keeps_the_library_s_account_of_why(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A Bridge refuses a SELECT only for a name no mailbox has, so the other NO is scripted here
    # from what a Dovecot with an ACL-shut mailbox really answers (the live half is
    # `test_imap_probe_live.py`). That such a folder is not reported missing is a contract check;
    # what this adds is that the base error still carries the server's own text, which is the
    # only explanation available for a mailbox that could not answer.
    box = FakeBox(names=["INBOX"])
    box.folder.select_error = MailboxFolderSelectError(UNOPENABLE_FOLDER_ANSWER, "OK")
    patch_box(monkeypatch, box)
    with pytest.raises(MailboxError) as raised:
        ImapMailbox(config()).search("INBOX", "ALL", 5)
    assert not isinstance(raised.value, FolderUnknownError)
    assert "could not run that search" in str(raised.value)
    assert "NOPERM" in str(raised.value)


def test_the_second_server_s_own_words_for_a_missing_mailbox_are_read_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Two servers say the same fact in no shared word: where the Bridge says `no such mailbox`,
    # Dovecot names the folder it refused and says it doesn't exist. Neither sends a response
    # code, so both phrases are read (ADR-0022 two-server addendum), and a rule that held only
    # the first would leave a model on that server with an untyped refusal for a name it
    # invented.
    box = FakeBox(names=["INBOX"])
    box.folder.select_error = MailboxFolderSelectError(OTHER_MISSING_FOLDER_ANSWER, "OK")
    patch_box(monkeypatch, box)
    with pytest.raises(FolderUnknownError) as raised:
        ImapMailbox(config()).search("Receipts", "ALL", 5)
    assert raised.value.folder == "Receipts"


def test_a_name_no_mailbox_could_have_is_read_off_the_code_and_not_the_prose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A NO can also mean the server rejected the string as a mailbox name, and its words say
    # nothing about a mailbox. Nothing in `Invalid mailbox name: Name is empty` matches a
    # measured phrase, so the classification turns on RFC 5530's `[CANNOT]`, which is a claim the
    # server made rather than a sentence it happened to phrase that way (ADR-0022 refused-name
    # addendum). The correction is the folder one because a name no mailbox could have is a name
    # `list_folders` never offered.
    box = FakeBox(names=["INBOX"])
    box.folder.select_error = MailboxFolderSelectError(REFUSED_NAME_ANSWER, "OK")
    patch_box(monkeypatch, box)
    with pytest.raises(FolderUnknownError) as raised:
        ImapMailbox(config()).search("", "ALL", 5)
    assert raised.value.folder == ""
    assert "list_folders" in str(raised.value)
    assert "CANNOT" not in str(raised.value)  # the code is read, never passed on


def test_the_bracketed_code_is_read_and_not_the_english_word_inside_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The fixture is the measured refusal with its brackets taken off. No server here sent that
    # sentence, and it is not offered as one: it isolates the difference the rule turns on. A
    # response code is a claim the server made in a form ordinary prose cannot imitate, while
    # `cannot` is a word a refusal about a mailbox that is merely shut could easily contain, so
    # reading the word rather than the code would report such a mailbox missing, which is the
    # error this classification must not make (ADR-0022 unknown-folder addendum).
    box = FakeBox(names=["INBOX"])
    box.folder.select_error = MailboxFolderSelectError(
        ("NO", [b"CANNOT Invalid mailbox name: Name is empty (0.001 + 0.000 secs)."]), "OK"
    )
    patch_box(monkeypatch, box)
    with pytest.raises(MailboxError) as raised:
        ImapMailbox(config()).search("INBOX", "ALL", 5)
    assert not isinstance(raised.value, FolderUnknownError)


def test_the_other_server_reaches_that_same_answer_through_its_words(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The port absorbs a disagreement between the two servers here: a Bridge has no response code
    # for this and answers the empty name with the `no such mailbox` it gives every other wrong
    # name, which the measured phrases already read. Each server states a different fact, and
    # both reach the same correction, so a model that sent a name no mailbox could have is sent
    # to `list_folders` on either of them.
    box = FakeBox(names=["INBOX"])
    patch_box(monkeypatch, box)
    with pytest.raises(FolderUnknownError) as raised:
        ImapMailbox(config()).fetch("", "7")
    assert raised.value.folder == ""


def test_the_standard_s_own_word_for_a_missing_mailbox_is_read_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The Bridge answers a name no mailbox has in plain words rather than with a response code,
    # so this is the portable half of the same fact: a server that sends RFC 5530's NONEXISTENT
    # is saying exactly what the Bridge spells out, and the classification reads either.
    box = FakeBox(names=["INBOX"])
    box.folder.select_error = MailboxFolderSelectError(
        ("NO", [b"[NONEXISTENT] Mailbox does not exist"]), "OK"
    )
    patch_box(monkeypatch, box)
    with pytest.raises(FolderUnknownError) as raised:
        ImapMailbox(config()).fetch("INBOX", "7")
    assert raised.value.folder == "INBOX"


def test_an_unreachable_bridge_crosses_the_port_as_a_mailbox_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The dial itself fails before any box exists, so this is the one failure that happens
    # outside the `with`. It must still be typed: an OSError out of `list_folders` would make
    # "the Bridge is not running" indistinguishable from a bug in this adapter.
    def refuse_dial(host: str, port: int, ssl_context: ssl.SSLContext) -> FakeBox:
        del host, port, ssl_context
        raise ConnectionRefusedError(111, "Connection refused")

    monkeypatch.setattr("cortex_email.imap.MailBoxStartTls", refuse_dial)
    with pytest.raises(MailboxError, match="could not list the folders"):
        ImapMailbox(config()).list_folders()


def test_reading_one_message_wraps_a_failure_the_same_way(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `fetch` names its own action, so an operator reading the message knows which call failed.
    patch_box(monkeypatch, FakeBox(fetch_error=IMAP4.error("FETCH command error: BAD")))
    with pytest.raises(MailboxError, match="could not read that message"):
        ImapMailbox(config()).fetch("INBOX", "7")
