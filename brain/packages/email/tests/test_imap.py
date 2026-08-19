"""Behavior tests for ImapMailbox over a fake imap-tools MailBox (no server, no network).

Proves the read-only discipline (EXAMINE via readonly=True, mark_seen=False), the TLS-mode
selection, and that no exception of the IMAP stack escapes the port. The shared `Mailbox`
promises live in `mailbox_contract.py`, which this adapter is driven through too; the live
contract against a real Bridge is `test_email_live.py`.
"""

import ssl
from imaplib import IMAP4

import pytest
from imap_stub import FakeBox, Msg, config, patch_box
from imap_tools import MailboxFolderSelectError

from cortex_email import ImapMailbox, MailboxError, RawEmail, SearchRefusedError


def test_list_folders_logs_in_and_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    box = FakeBox(names=["INBOX", "Archive"])
    captured = patch_box(monkeypatch, box)
    assert list(ImapMailbox(config()).list_folders()) == ["INBOX", "Archive"]
    assert box.login_calls == [("bridge-user", "bridge-pass")]
    assert (captured["host"], captured["port"]) == ("mail.local", 1143)


def test_search_is_headers_only_read_only_and_unseen(monkeypatch: pytest.MonkeyPatch) -> None:
    box = FakeBox(messages=[Msg("7", b"raw7"), Msg("8", b"raw8")])
    patch_box(monkeypatch, box)
    result = ImapMailbox(config()).search("INBOX", "ALL", 5)
    assert list(result) == [RawEmail("7", b"raw7"), RawEmail("8", b"raw8")]
    assert box.set_calls == [("INBOX", True)]  # EXAMINE, never SELECT
    ((_, limit, headers_only, mark_seen),) = box.fetch_calls
    assert (limit, headers_only, mark_seen) == (5, True, False)


def test_fetch_one_found_is_read_only_and_unseen(monkeypatch: pytest.MonkeyPatch) -> None:
    box = FakeBox(messages=[Msg("7", b"full7")])
    patch_box(monkeypatch, box)
    assert ImapMailbox(config()).fetch("INBOX", "7") == RawEmail("7", b"full7")
    assert box.set_calls == [("INBOX", True)]
    ((_, limit, _headers, mark_seen),) = box.fetch_calls
    assert (limit, mark_seen) == (1, False)


def test_fetch_one_missing_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_box(monkeypatch, FakeBox(messages=[]))
    assert ImapMailbox(config()).fetch("INBOX", "999") is None


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


def test_a_folder_no_mailbox_has_fails_without_leaking_the_library(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A NO to SELECT is imap-tools' own exception rather than imaplib's, and it is not a refused
    # query either: the mailbox could not answer, which is what the base type says.
    def refuse_select(*_args: object, **_kwargs: object) -> None:
        raise MailboxFolderSelectError(("NO", [b"no such mailbox"]), "OK")

    box = FakeBox(names=["INBOX"])
    monkeypatch.setattr(box.folder, "set", refuse_select)
    patch_box(monkeypatch, box)
    with pytest.raises(MailboxError) as raised:
        ImapMailbox(config()).search("Invented", "ALL", 5)
    assert not isinstance(raised.value, SearchRefusedError)
    assert "could not run that search" in str(raised.value)


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
