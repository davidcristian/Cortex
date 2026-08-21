"""Both `Mailbox` implementations against the same checks (`mailbox_contract.py`).

The fake the reader and server tests run on, and the real `ImapMailbox` over a stand-in
imap-tools ``MailBox``: only the socket is faked, so the adapter's connection building, folder
discipline, message mapping and error classification are exercised by the same checks the fake
passes. The stand-in raises the exception imaplib really raises on a refused query, which is
what makes the refusal check a statement about the adapter rather than about the stub.

The live half against a real Bridge is `test_email_live.py`, integration-marked per AGENTS.md
gate 3.
"""

from collections.abc import Callable
from imaplib import IMAP4

import pytest
from imap_stub import UNOPENABLE_FOLDER_ANSWER, FakeBox, Msg, config, patch_box
from imap_tools import MailboxFolderSelectError
from mailbox_contract import ALL_CHECKS, WIRE_ANSWER, Check, MailboxUnderTest
from mailbox_fake import FakeMailbox

from cortex_email import ImapMailbox, RawEmail

_FOLDER = "INBOX"
# The name each fixture's server lists and no mailbox has, spelled as a parent so it reads as
# what it is; the live probe's own is a real one a real Dovecot builds.
_NODE = "Parent"
_SIMPLE = (
    b"From: Alice <alice@example.com>\r\nSubject: Lunch\r\n"
    b"Date: Fri, 03 Jul 2026 12:00:00 +0000\r\n\r\nLet's do lunch.\r\n"
)

type Build = Callable[[pytest.MonkeyPatch], MailboxUnderTest]


def _fake(_monkeypatch: pytest.MonkeyPatch) -> MailboxUnderTest:
    mailbox = FakeMailbox(folders=[_FOLDER], nodes=[_NODE], found=[RawEmail("7", _SIMPLE)])
    return MailboxUnderTest(
        mailbox=mailbox,
        folder=_FOLDER,
        refuse_searches=mailbox.refuse,
        break_folder_opening=mailbox.break_folder_opening,
        hierarchy_node=_NODE,
    )


def _imap(monkeypatch: pytest.MonkeyPatch) -> MailboxUnderTest:
    """The real adapter over a stand-in box whose server can be made to refuse."""
    box = FakeBox(names=[_FOLDER], messages=[Msg("7", _SIMPLE)], nodes=[_NODE])

    def refuse() -> None:
        # What imaplib raises out of `UID SEARCH` when the tagged response is BAD.
        box.fetch_error = IMAP4.error(WIRE_ANSWER)

    def break_folder_opening() -> None:
        # A NO to SELECT that is not the missing-mailbox one, which is the only way to reach the
        # fail-safe branch: no server this repo can reach refuses a select for any other reason.
        box.folder.select_error = MailboxFolderSelectError(UNOPENABLE_FOLDER_ANSWER, "OK")

    patch_box(monkeypatch, box)
    return MailboxUnderTest(
        mailbox=ImapMailbox(config()),
        folder=_FOLDER,
        refuse_searches=refuse,
        break_folder_opening=break_folder_opening,
        hierarchy_node=_NODE,
    )


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda check: check.__name__)
@pytest.mark.parametrize("build", [_fake, _imap], ids=["fake", "imap"])
def test_the_contract_holds(check: Check, build: Build, monkeypatch: pytest.MonkeyPatch) -> None:
    check(build(monkeypatch))
