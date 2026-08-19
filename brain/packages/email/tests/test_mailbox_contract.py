"""Both `Mailbox` implementations against the same checks (`mailbox_contract.py`)."""

from collections.abc import Callable
from imaplib import IMAP4

import pytest
from imap_stub import FakeBox, Msg, config, patch_box
from mailbox_contract import ALL_CHECKS, WIRE_ANSWER, Check, MailboxUnderTest
from mailbox_fake import FakeMailbox

from cortex_email import ImapMailbox, RawEmail

_FOLDER = "INBOX"
_SIMPLE = (
    b"From: Alice <alice@example.com>\r\nSubject: Lunch\r\n"
    b"Date: Fri, 03 Jul 2026 12:00:00 +0000\r\n\r\nLet's do lunch.\r\n"
)

type Build = Callable[[pytest.MonkeyPatch], MailboxUnderTest]


def _fake(_monkeypatch: pytest.MonkeyPatch) -> MailboxUnderTest:
    mailbox = FakeMailbox(folders=[_FOLDER], found=[RawEmail("7", _SIMPLE)])
    return MailboxUnderTest(mailbox=mailbox, folder=_FOLDER, refuse_searches=mailbox.refuse)


def _imap(monkeypatch: pytest.MonkeyPatch) -> MailboxUnderTest:
    """The real adapter over a stand-in box whose server can be made to refuse."""
    box = FakeBox(names=[_FOLDER], messages=[Msg("7", _SIMPLE)])

    def refuse() -> None:
        # What imaplib raises out of `UID SEARCH` when the tagged response is BAD.
        box.fetch_error = IMAP4.error(WIRE_ANSWER)

    patch_box(monkeypatch, box)
    return MailboxUnderTest(mailbox=ImapMailbox(config()), folder=_FOLDER, refuse_searches=refuse)


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda check: check.__name__)
@pytest.mark.parametrize("build", [_fake, _imap], ids=["fake", "imap"])
def test_the_contract_holds(check: Check, build: Build, monkeypatch: pytest.MonkeyPatch) -> None:
    check(build(monkeypatch))
