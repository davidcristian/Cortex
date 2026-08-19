"""EmailReader + ImapMailbox against a live ProtonMail Bridge (host-only, ADR-0009)."""

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
    """The guard on what `search_emails` tells a model: only criteria that work may be named."""
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

    with pytest.raises(SearchRefusedError) as raised:
        reader.search("INBOX", "from:someone@example.com", 1)
    assert raised.value.query == "from:someone@example.com"
    assert "offset" not in str(raised.value)


@pytest.mark.integration
def test_send_round_trips_between_the_two_test_addresses() -> None:
    """The ADR-0022 live send: SMTP out over the Bridge, arrival verified over IMAP."""
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
