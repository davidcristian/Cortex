"""EmailReader + ImapMailbox against a live ProtonMail Bridge (host-only, ADR-0009).

Integration-marked: needs a running Bridge with credentials in the env (CORTEX_EMAIL_IMAP_*),
never run in CI. Run per docs/runbooks/email-imap.md, e.g. with ~/.cortex/email.env sourced:
`cd brain && uv run pytest -m integration --no-cov packages/email`.
"""

import os
import re
import time
import uuid
from email import message_from_bytes, policy
from email.message import EmailMessage
from typing import cast

import pytest

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
    if summaries:  # a fresh mailbox may be empty; only assert the read path when there's mail
        detail = reader.read("INBOX", summaries[0].uid)
        assert detail is not None
        assert detail.subject == summaries[0].subject


# One query per criterion family the `query` description names, written the way it tells a model
# to write them. The folder is INBOX and the limit is 1 because this asserts the SERVER parses
# each criterion, which it answers before it counts a single message, so the pass says the same
# thing against a full mailbox and an empty one.
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
# The words in the description that are criteria rather than prose. IMAP and SEARCH name the
# dialect itself, and OR/NOT are exercised inside the composed queries above rather than alone.
_NOT_CRITERIA = frozenset({"IMAP", "SEARCH", "OR", "NOT"})


@pytest.mark.integration
def test_every_advertised_search_criterion_is_one_the_bridge_accepts() -> None:
    """The guard on what `search_emails` tells a model: only criteria that work may be named.

    The description was written from a live pass rather than from the RFC, against a server
    whose SEARCH support is partial by reputation, so this is the test that keeps the two
    together: name a criterion in `SEARCH_QUERY_HELP` and it is run here, and a server that
    stops accepting one fails the run instead of quietly answering the model with a parse error.
    """
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
        reader.search("INBOX", query, 1)  # a criterion the server refuses raises out of here

    # And the premise the description exists to remove: the client syntax really is refused,
    # rather than being interpreted as a subject search or quietly matching nothing. The type is
    # the port's, not imaplib's, and this is the live half of that: a real Bridge answering BAD
    # is what `ImapMailbox` classifies as a refusal, and only a live run proves the branch is
    # taken on the answer a real server sends rather than on the one the stand-in was scripted
    # with (ADR-0022 refused-search addendum).
    with pytest.raises(SearchRefusedError) as raised:
        reader.search("INBOX", "from:someone@example.com", 1)
    assert raised.value.query == "from:someone@example.com"
    assert "offset" not in str(raised.value)


@pytest.mark.integration
def test_a_folder_no_mailbox_has_is_refused_by_name_and_by_the_folder_list() -> None:
    """The live half of the unknown-folder classification, and the premise it rests on.

    Two facts only a real server can settle. Every name no mailbox has is refused the same way,
    whatever shape the wrong name takes, so the classification is not reading one accident of one
    spelling; and every name `list_folders` returns really does open, so nothing the tool tells a
    model to use comes back as the refusal it warns about. The `NO` the Bridge sends carries no
    RFC 5530 response code, only the words, which is why the words are what is read
    (ADR-0022 unknown-folder addendum).
    """
    config = EmailConfig()
    if not config.user:
        pytest.skip("set CORTEX_EMAIL_IMAP_USER/PASSWORD (~/.cortex/email.env) to run")
    mailbox = ImapMailbox(config)
    for name in ("Receipts", "INBOX/Receipts", "inbox/", '"Receipts"'):
        with pytest.raises(FolderUnknownError) as raised:
            mailbox.search(name, "ALL", 1)
        assert raised.value.folder == name
        assert "list_folders" in str(raised.value)
        assert "Response status" not in str(raised.value)  # nothing of imap-tools reaches a model
    with pytest.raises(FolderUnknownError):
        mailbox.fetch("Receipts", "1")  # the other tool that takes a folder, same answer

    for folder in mailbox.list_folders():
        mailbox.search(folder, "ALL", 1)  # a listed name that would not open raises out of here


@pytest.mark.integration
def test_send_round_trips_between_the_two_test_addresses() -> None:
    """The ADR-0022 live send: SMTP out over the Bridge, arrival verified over IMAP.

    Needs CORTEX_EMAIL_SMTP_* + CORTEX_EMAIL_SEND_ENABLED and a recipient address in
    CORTEX_EMAIL_LIVE_SEND_TO (the second example.com address; both Bridge-hosted, so the
    message lands in the same account's mailbox). Outbound and irreversible. This test
    really sends one small message.
    """
    smtp_config = SmtpConfig()
    to = os.environ.get("CORTEX_EMAIL_LIVE_SEND_TO", "")
    if not (smtp_config.enabled and to):
        pytest.skip("set CORTEX_EMAIL_SEND_ENABLED/SMTP_* and CORTEX_EMAIL_LIVE_SEND_TO to run")
    stamp = uuid.uuid4().hex[:12]
    subject = f"cortex live send {stamp}"
    # Exercise the richer shapes on the real Bridge: an html alternative plus a cc back to the
    # sending account, so a live run validates cc/html composition end to end, not just plain.
    # The attachment rides along for the same reason (ADR-0022 attachments addendum), and it is
    # the shape a fake smtplib cannot prove: that a real server accepts the multipart/mixed.
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

    # Search server-side BY the unique stamp, not the oldest N of the folder: a populated
    # mailbox would never surface a just-arrived message in its oldest 20 (IMAP fetch is
    # ascending-UID). The subject is unique per run, so the IMAP SUBJECT filter finds exactly it.
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
