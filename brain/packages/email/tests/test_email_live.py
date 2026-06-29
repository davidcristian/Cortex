"""EmailReader + ImapMailbox against a live ProtonMail Bridge (host-only, ADR-0009).

Integration-marked: needs a running Bridge with credentials in the env (CORTEX_EMAIL_IMAP_*),
never run in CI. Run per docs/runbooks/email-imap.md, e.g. with ~/.cortex/email.env sourced:
`cd brain && uv run pytest -m integration --no-cov packages/email`.
"""

import pytest

from cortex_email import EmailConfig, EmailReader, ImapMailbox


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
