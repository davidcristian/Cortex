"""EmailReader + ImapMailbox against a live ProtonMail Bridge (host-only, ADR-0009).

Integration-marked: needs a running Bridge with credentials in the env (CORTEX_EMAIL_IMAP_*),
never run in CI. Run per docs/runbooks/email-imap.md, e.g. with ~/.cortex/email.env sourced:
`cd brain && uv run pytest -m integration --no-cov packages/email`.
"""

import os
import time
import uuid

import pytest

from cortex_email import EmailConfig, EmailReader, ImapMailbox, SmtpConfig, SmtpSender


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
    line = SmtpSender(smtp_config).send(to, subject, "slice 8.8 live round-trip")
    assert to in line

    # Search server-side BY the unique stamp, not the oldest N of the folder: a populated
    # mailbox would never surface a just-arrived message in its oldest 20 (IMAP fetch is
    # ascending-UID). The subject is unique per run, so the IMAP SUBJECT filter finds exactly it.
    reader = EmailReader(ImapMailbox(EmailConfig()))
    query = f'SUBJECT "{stamp}"'
    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
        hits = [s for folder in ("INBOX", "Sent") for s in reader.search(folder, query, 5)]
        if hits:
            return
        time.sleep(3.0)
    pytest.fail(f"sent message {stamp!r} did not appear over IMAP within 60s")
