import os
import re
import time
import uuid
from email import message_from_bytes, policy
from email.message import EmailMessage
from typing import cast

import pytest
from imap_tools import MailboxFolderSelectError
from mailbox_contract import (
    IMPOSSIBLE_UIDS,
    MISSING_UID,
    MailboxUnderTest,
    a_search_of_a_folder_holding_no_mail_matches_nothing,
)

from cortex_email import (
    EmailAttachment,
    EmailConfig,
    EmailDraft,
    EmailReader,
    FolderUnknownError,
    ImapMailbox,
    SearchRefusedError,
    SmtpConfig,
    SmtpSender,
)
from cortex_email.values import SEARCH_QUERY_HELP


@pytest.mark.integration
def test_reader_lists_and_reads_from_a_live_bridge() -> None:
    config = EmailConfig()
    if not config.user:
        pytest.skip("set CORTEX_EMAIL_IMAP_USER/PASSWORD (~/.cortex/email.env) to run")
    reader = EmailReader(ImapMailbox(config))
    folders = list(reader.folders())
    assert "INBOX" in folders
    summaries = list(reader.search("INBOX", "ALL", 3))
    if summaries:
        detail = reader.read("INBOX", summaries[0].uid)
        assert detail is not None
        assert detail.subject == summaries[0].subject


_ADVERTISED_QUERIES = (
    "ALL",
    'SUBJECT "cortex"',
    'FROM "someone@example.com"',
    'TO "someone@example.com"',
    'CC "someone@example.com"',
    'BCC "someone@example.com"',
    'BODY "cortex"',
    'TEXT "cortex"',
    'HEADER "Message-Id" "cortex"',
    "SINCE 01-Jan-2026",
    "BEFORE 01-Jan-2026",
    "ON 01-Jan-2026",
    "SENTSINCE 01-Jan-2026",
    "SENTBEFORE 01-Jan-2026",
    "SENTON 01-Jan-2026",
    "SEEN",
    "UNSEEN",
    "ANSWERED",
    "UNANSWERED",
    "FLAGGED",
    "UNFLAGGED",
    "DRAFT",
    "UNDRAFT",
    "DELETED",
    "UNDELETED",
    "LARGER 1000",
    "SMALLER 1000000",
    'UNSEEN SINCE 01-Jan-2026 OR SUBJECT "invoice" SUBJECT "receipt"',
    'NOT SUBJECT "cortex"',
    '(FROM "someone@example.com" SINCE 01-Jan-2026)',
)
_NOT_CRITERIA = frozenset({"IMAP", "SEARCH", "OR", "NOT"})


@pytest.mark.integration
def test_every_advertised_search_criterion_is_one_the_bridge_accepts() -> None:
    config = EmailConfig()
    if not config.user:
        pytest.skip("set CORTEX_EMAIL_IMAP_USER/PASSWORD (~/.cortex/email.env) to run")
    named = set(re.findall(r"\b[A-Z][A-Z-]{1,}\b", SEARCH_QUERY_HELP)) - _NOT_CRITERIA
    exercised = {
        word for query in _ADVERTISED_QUERIES for word in re.findall(r"\b[A-Z-]{2,}\b", query)
    }
    assert named <= exercised, f"described but never run live: {sorted(named - exercised)}"

    reader = EmailReader(ImapMailbox(config))
    for query in _ADVERTISED_QUERIES:
        reader.search("INBOX", query, 1)

    with pytest.raises(SearchRefusedError) as raised:
        reader.search("INBOX", "from:someone@example.com", 1)
    assert raised.value.query == "from:someone@example.com"
    assert "offset" not in str(raised.value)


@pytest.mark.integration
def test_a_folder_no_mailbox_has_is_refused_by_name_and_by_the_folder_list() -> None:
    config = EmailConfig()
    if not config.user:
        pytest.skip("set CORTEX_EMAIL_IMAP_USER/PASSWORD (~/.cortex/email.env) to run")
    mailbox = ImapMailbox(config)
    for name in ("Receipts", "INBOX/Receipts", "inbox/", '"Receipts"', ""):
        with pytest.raises(FolderUnknownError) as raised:
            mailbox.search(name, "ALL", 1)
        assert raised.value.folder == name
        assert "list_folders" in str(raised.value)
        assert "Response status" not in str(raised.value)
    with pytest.raises(FolderUnknownError):
        mailbox.fetch("Receipts", "1")

    for folder in mailbox.list_folders():
        mailbox.search(folder, "ALL", 1)

    _assert_no_name_this_server_opens_is_withheld(mailbox)


def _assert_no_name_this_server_opens_is_withheld(mailbox: ImapMailbox) -> None:
    """Assert that every name this server opens is one `list_folders` offers."""
    offered = set(mailbox.list_folders())
    # Reaching past the port is what both suppressions are for: this asks about the names
    # the port did not return, which nothing on the port can show.
    connection = mailbox._open()  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
    with connection as box:
        listed = [folder.name for folder in box.folder.list()]
        opens: set[str] = set()
        for name in listed:
            try:
                box.folder.set(name, readonly=True)  # pyright: ignore[reportUnknownMemberType]
            except MailboxFolderSelectError:
                continue
            opens.add(name)
    assert opens, "the account listed nothing that opens, so this proves nothing"
    assert offered == opens, f"withheld: {sorted(opens - offered)}; offered shut: {offered - opens}"


@pytest.mark.integration
def test_a_uid_no_message_has_is_not_there_whichever_kind_of_folder_is_asked() -> None:
    config = EmailConfig()
    if not config.user:
        pytest.skip("set CORTEX_EMAIL_IMAP_USER/PASSWORD (~/.cortex/email.env) to run")
    mailbox = ImapMailbox(config)
    with_mail, without = _one_folder_of_each_kind(mailbox)
    if with_mail is None:
        pytest.skip("no folder in this mailbox holds mail, so the read by uid cannot be shown")
    assert mailbox.fetch(with_mail, MISSING_UID) is None
    for uid in IMPOSSIBLE_UIDS:
        assert mailbox.fetch(with_mail, uid) is None, uid
    if without is None:
        pytest.skip("every folder in this mailbox holds mail, so the empty-folder read cannot run")
    assert mailbox.fetch(without, MISSING_UID) is None
    connection = mailbox._open()  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
    with connection as box:
        for folder in (with_mail, without):
            box.folder.set(folder, readonly=True)  # pyright: ignore[reportUnknownMemberType]
            assert box.client.uid("FETCH", MISSING_UID, "(UID)") == ("OK", [None]), folder


@pytest.mark.integration
def test_a_uid_criterion_in_a_folder_holding_no_mail_matches_nothing() -> None:
    config = EmailConfig()
    if not config.user:
        pytest.skip("set CORTEX_EMAIL_IMAP_USER/PASSWORD (~/.cortex/email.env) to run")
    mailbox = ImapMailbox(config)
    with_mail, without = _one_folder_of_each_kind(mailbox)
    if without is None:
        pytest.skip("every folder in this mailbox holds mail, so the empty-folder search is moot")
    a_search_of_a_folder_holding_no_mail_matches_nothing(
        MailboxUnderTest(
            mailbox=mailbox,
            folder=with_mail or without,
            refuse_searches=_unreachable,
            break_folder_opening=_unreachable,
            decline_reads=_unreachable,
            hierarchy_node="",
            empty_folder=without,
        )
    )
    connection = mailbox._open()  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
    with connection as box:
        assert box.folder.set(without, readonly=True) == (  # pyright: ignore[reportUnknownMemberType]
            "OK",
            [b"0"],
        )
        status, answer = box.client.uid("SEARCH", "CHARSET", "US-ASCII", "UID", MISSING_UID)
        assert (status, answer) == ("NO", [b"no such message"])


def _unreachable() -> None:
    """Fail a contract condition this account cannot set up and the check here never asks for."""
    pytest.fail("this check arranges nothing on a live server")


def _one_folder_of_each_kind(mailbox: ImapMailbox) -> tuple[str | None, str | None]:
    """One folder of this account holding mail and one holding none, or ``None`` for either."""
    with_mail: str | None = None
    without: str | None = None
    for folder in mailbox.list_folders():
        if mailbox.search(folder, "ALL", 1):
            with_mail = with_mail or folder
        else:
            without = without or folder
        if with_mail is not None and without is not None:
            break
    return with_mail, without


@pytest.mark.integration
def test_send_round_trips_between_the_two_test_addresses() -> None:
    smtp_config = SmtpConfig()
    to = os.environ.get("CORTEX_EMAIL_LIVE_SEND_TO", "")
    if not (smtp_config.enabled and to):
        pytest.skip("set CORTEX_EMAIL_SEND_ENABLED/SMTP_* and CORTEX_EMAIL_LIVE_SEND_TO to run")
    stamp = uuid.uuid4().hex[:12]
    subject = f"cortex live send {stamp}"
    line = SmtpSender(smtp_config).send(
        EmailDraft(
            to,
            subject,
            "live round-trip (plain fallback)",
            cc=smtp_config.user,
            html="<p>live round-trip (rich)</p>",
            attachments=(EmailAttachment("notes.md", f"# live {stamp}\n", "markdown"),),
        )
    )
    assert to in line

    mailbox = ImapMailbox(EmailConfig())
    reader = EmailReader(mailbox)
    query = f'SUBJECT "{stamp}"'
    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
        for folder in ("INBOX", "Sent"):
            hits = list(reader.search(folder, query, 5))
            if hits:
                _assert_attachment_survived(mailbox, folder, hits[0].uid, stamp)
                return
        time.sleep(3.0)
    pytest.fail(f"sent message {stamp!r} did not appear over IMAP within 60s")


def _assert_attachment_survived(mailbox: ImapMailbox, folder: str, uid: str, stamp: str) -> None:
    """Parse the delivered message and prove the attachment came back off the wire intact."""
    raw = mailbox.fetch(folder, uid)
    assert raw is not None
    delivered = message_from_bytes(raw.raw, EmailMessage, policy=policy.default)
    attachments = list(delivered.iter_attachments())
    assert [part.get_filename() for part in attachments] == ["notes.md"]
    assert attachments[0].get_content_type() == "text/markdown"
    assert cast("str", attachments[0].get_content()).strip() == f"# live {stamp}"
