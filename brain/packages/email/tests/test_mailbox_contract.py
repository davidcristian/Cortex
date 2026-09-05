from collections.abc import Callable
from imaplib import IMAP4

import pytest
from imap_stub import (
    DECLINED_READ_ANSWER,
    UNOPENABLE_FOLDER_ANSWER,
    FakeBox,
    Msg,
    config,
    patch_box,
)
from imap_tools import MailboxFolderSelectError
from mailbox_contract import ALL_CHECKS, WIRE_ANSWER, Check, MailboxUnderTest
from mailbox_fake import FakeMailbox

from cortex_email import ImapMailbox, RawEmail

_FOLDER = "INBOX"
_NODE = "Parent"
_EMPTY = "Archive"
_SIMPLE = (
    b"From: Alice <alice@example.com>\r\nSubject: Lunch\r\n"
    b"Date: Fri, 03 Jul 2026 12:00:00 +0000\r\n\r\nLet's do lunch.\r\n"
)

type Build = Callable[[pytest.MonkeyPatch], MailboxUnderTest]


def _fake(_monkeypatch: pytest.MonkeyPatch) -> MailboxUnderTest:
    mailbox = FakeMailbox(folders=[_FOLDER, _EMPTY], nodes=[_NODE], found=[RawEmail("7", _SIMPLE)])
    return MailboxUnderTest(
        mailbox=mailbox,
        folder=_FOLDER,
        refuse_searches=mailbox.refuse,
        break_folder_opening=mailbox.break_folder_opening,
        decline_reads=mailbox.decline_reads,
        hierarchy_node=_NODE,
        empty_folder=_EMPTY,
    )


def _imap(monkeypatch: pytest.MonkeyPatch) -> MailboxUnderTest:
    """The real adapter over a stand-in box whose server can be made to answer BAD."""
    box = FakeBox(names=[_FOLDER, _EMPTY], messages=[Msg("7", _SIMPLE)], nodes=[_NODE])

    def refuse() -> None:
        box.fetch_error = IMAP4.error(WIRE_ANSWER)

    def break_folder_opening() -> None:
        box.folder.select_error = MailboxFolderSelectError(UNOPENABLE_FOLDER_ANSWER, "OK")

    def decline_reads() -> None:
        box.fetch_answer = DECLINED_READ_ANSWER

    patch_box(monkeypatch, box)
    return MailboxUnderTest(
        mailbox=ImapMailbox(config()),
        folder=_FOLDER,
        refuse_searches=refuse,
        break_folder_opening=break_folder_opening,
        decline_reads=decline_reads,
        hierarchy_node=_NODE,
        empty_folder=_EMPTY,
    )


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda check: check.__name__)
@pytest.mark.parametrize("build", [_fake, _imap], ids=["fake", "imap"])
def test_the_contract_holds(check: Check, build: Build, monkeypatch: pytest.MonkeyPatch) -> None:
    check(build(monkeypatch))
