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
    REFUSED_UID_SEARCH,
    UNOPENABLE_FOLDER_ANSWER,
    Answer,
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


def test_the_newer_form_of_unselectable_is_dropped_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    box = FakeBox(names=["INBOX"], nodes=["Ghost"], node_flags=NONEXISTENT_NODE_FLAGS)
    patch_box(monkeypatch, box)
    assert list(ImapMailbox(config()).list_folders()) == ["INBOX"]
    assert box.set_calls == [("Ghost", True)]


def test_a_flagged_name_the_server_opens_is_still_offered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    box = FakeBox(names=["INBOX"], open_nodes=["Folders"], node_flags=OPEN_NODE_FLAGS)
    patch_box(monkeypatch, box)
    assert list(ImapMailbox(config()).list_folders()) == ["INBOX", "Folders"]
    assert box.set_calls == [("Folders", True)]


def test_a_flagged_name_the_server_calls_missing_is_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    box = FakeBox(names=["INBOX"], nodes=["Parent"])
    patch_box(monkeypatch, box)
    assert list(ImapMailbox(config()).list_folders()) == ["INBOX"]
    assert box.set_calls == [("Parent", True)]


def test_a_flagged_name_refused_for_a_reason_that_is_not_its_name_stays_offered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    box = FakeBox(names=["INBOX"], nodes=["Shut"])
    box.folder.select_error = MailboxFolderSelectError(UNOPENABLE_FOLDER_ANSWER, "OK")
    patch_box(monkeypatch, box)
    assert list(ImapMailbox(config()).list_folders()) == ["INBOX", "Shut"]
    assert box.set_calls == [("Shut", True)]


def test_search_is_headers_only_read_only_and_unseen(monkeypatch: pytest.MonkeyPatch) -> None:
    box = FakeBox(messages=[Msg("7", b"raw7"), Msg("8", b"raw8")])
    patch_box(monkeypatch, box)
    result = ImapMailbox(config()).search("INBOX", "ALL", 5)
    assert list(result) == [RawEmail("7", b"raw7"), RawEmail("8", b"raw8")]
    assert box.set_calls == [("INBOX", True)]
    ((_, limit, headers_only, mark_seen),) = box.fetch_calls
    assert (limit, headers_only, mark_seen) == (5, True, False)


def test_a_search_refused_in_a_folder_holding_no_mail_answers_with_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    box = FakeBox(names=["INBOX", "Archive"], messages=[Msg("7", _SIMPLE)])
    patch_box(monkeypatch, box)
    assert list(ImapMailbox(config()).search("Archive", "UID 999", 5)) == []
    assert box.set_calls == [("Archive", True)]
    assert [call[0] for call in box.fetch_calls] == ["UID 999"]


def test_the_same_refusal_in_a_folder_holding_mail_is_still_the_base_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    box = FakeBox(messages=[Msg("7", _SIMPLE)], fetch_error=REFUSED_UID_SEARCH)
    patch_box(monkeypatch, box)
    with pytest.raises(MailboxError) as raised:
        ImapMailbox(config()).search("INBOX", "UID 999", 5)
    assert "could not run that search" in str(raised.value)


def test_a_refusal_is_not_answered_when_the_select_reported_no_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    box = FakeBox(names=["INBOX", "Archive"], messages=[Msg("7", _SIMPLE)])
    patch_box(monkeypatch, box)
    uncountable: tuple[Answer, ...] = (("OK", []), ("OK", [None]), ("OK", [b"not a number"]))
    for answer in uncountable:
        box.folder.select_answer = answer
        with pytest.raises(MailboxError):
            ImapMailbox(config()).search("Archive", "UID 999", 5)


def test_fetch_one_found_is_read_only_and_unseen(monkeypatch: pytest.MonkeyPatch) -> None:
    box = FakeBox(messages=[Msg("7", _SIMPLE)])
    patch_box(monkeypatch, box)
    read = ImapMailbox(config()).fetch("INBOX", "7")
    assert read is not None
    assert (read.uid, read.raw[:6]) == ("7", b"From: ")
    assert box.set_calls == [("INBOX", True)]
    assert box.fetch_calls == []
    ((command, uid, parts),) = box.client.uid_calls
    assert (command, uid) == ("FETCH", "7")
    assert "BODY.PEEK[]" in parts
    assert "UID" in parts.split()


def test_fetch_one_missing_is_asked_and_answered_with_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    box = FakeBox(messages=[])
    patch_box(monkeypatch, box)
    assert ImapMailbox(config()).fetch("INBOX", "999") is None
    assert [call[:2] for call in box.client.uid_calls] == [("FETCH", "999")]


def test_a_read_the_server_declined_keeps_the_library_s_account_of_why(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    box = FakeBox(messages=[Msg("7", _SIMPLE)], fetch_error=DROPPED_READ)
    patch_box(monkeypatch, box)
    with pytest.raises(MailboxError) as raised:
        ImapMailbox(config()).fetch("INBOX", "7")
    assert not isinstance(raised.value, FolderUnknownError)
    assert "Internal error occurred" in str(raised.value)


def test_a_uid_no_message_could_have_sends_no_command(monkeypatch: pytest.MonkeyPatch) -> None:
    box = FakeBox(messages=[Msg("7", _SIMPLE)])
    patch_box(monkeypatch, box)
    for uid in IMPOSSIBLE_UIDS:
        assert ImapMailbox(config()).fetch("INBOX", uid) is None, uid
    assert box.client.uid_calls == []


def test_the_folder_is_checked_before_the_uid(monkeypatch: pytest.MonkeyPatch) -> None:
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
    box = FakeBox(messages=[Msg("7", _SIMPLE)], fetch_error=IMAP4.abort("socket error: EOF"))
    patch_box(monkeypatch, box)
    with pytest.raises(MailboxError) as raised:
        ImapMailbox(config()).search("INBOX", "ALL", 5)
    assert not isinstance(raised.value, SearchRefusedError)
    assert "connection dropped" in str(raised.value)


def test_a_select_refused_for_another_reason_keeps_the_library_s_account_of_why(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    box = FakeBox(names=["INBOX"])
    box.folder.select_error = MailboxFolderSelectError(OTHER_MISSING_FOLDER_ANSWER, "OK")
    patch_box(monkeypatch, box)
    with pytest.raises(FolderUnknownError) as raised:
        ImapMailbox(config()).search("Receipts", "ALL", 5)
    assert raised.value.folder == "Receipts"


def test_a_name_no_mailbox_could_have_is_read_off_the_code_and_not_the_prose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    box = FakeBox(names=["INBOX"])
    box.folder.select_error = MailboxFolderSelectError(REFUSED_NAME_ANSWER, "OK")
    patch_box(monkeypatch, box)
    with pytest.raises(FolderUnknownError) as raised:
        ImapMailbox(config()).search("", "ALL", 5)
    assert raised.value.folder == ""
    assert "list_folders" in str(raised.value)
    assert "CANNOT" not in str(raised.value)


def test_the_bracketed_code_is_read_and_not_the_english_word_inside_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    box = FakeBox(names=["INBOX"])
    patch_box(monkeypatch, box)
    with pytest.raises(FolderUnknownError) as raised:
        ImapMailbox(config()).fetch("", "7")
    assert raised.value.folder == ""


def test_the_standard_s_own_word_for_a_missing_mailbox_is_read_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    def refuse_dial(host: str, port: int, ssl_context: ssl.SSLContext) -> FakeBox:
        del host, port, ssl_context
        raise ConnectionRefusedError(111, "Connection refused")

    monkeypatch.setattr("cortex_email.imap.MailBoxStartTls", refuse_dial)
    with pytest.raises(MailboxError, match="could not list the folders"):
        ImapMailbox(config()).list_folders()


def test_reading_one_message_wraps_a_failure_the_same_way(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_box(monkeypatch, FakeBox(fetch_error=IMAP4.error("FETCH command error: BAD")))
    with pytest.raises(MailboxError, match="could not read that message"):
        ImapMailbox(config()).fetch("INBOX", "7")
