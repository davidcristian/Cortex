"""A stand-in for the imap-tools ``MailBox``: what `ImapMailbox` talks to when no server exists."""

import ssl
from collections.abc import Sequence
from typing import Self

import pytest
from imap_tools import MailboxFolderSelectError
from pydantic import SecretStr

import cortex_email.imap as imap_module
from cortex_email import EmailConfig
from cortex_email.config import ImapSecurity


class Obj:
    """The parsed message an imap-tools ``MailMessage`` exposes as ``.obj``."""

    def __init__(self, raw: bytes) -> None:
        self._raw = raw

    def as_bytes(self) -> bytes:
        return self._raw


class Msg:
    """One fetched message: its uid and the RFC822 bytes behind ``.obj``."""

    def __init__(self, uid: str, raw: bytes) -> None:
        self.uid = uid
        self.obj = Obj(raw)


# What a real ProtonMail Bridge answers to a SELECT of a name no mailbox has, measured verbatim
# and identically for every shape of wrong name (ADR-0022 unknown-folder addendum).
MISSING_FOLDER_ANSWER = ("NO", [b"no such mailbox"])
# The same fact in another server's words: Dovecot 2.3.21 names the folder it refused and shares
# not one word with the Bridge, which is why the classification holds two measured phrases rather
# than one (ADR-0022 two-server addendum).
OTHER_MISSING_FOLDER_ANSWER = ("NO", [b"Mailbox doesn't exist: Receipts (0.001 + 0.000 secs)."])
UNOPENABLE_FOLDER_ANSWER = ("NO", [b"[NOPERM] Permission denied (0.001 + 0.000 secs)."])


class Folder:
    """One named folder, as ``folder.list()`` returns it."""

    def __init__(self, name: str) -> None:
        self.name = name


class FolderManager:
    """The ``box.folder`` manager: lists names and records every ``set`` (folder, readonly)."""

    def __init__(self, names: Sequence[str], set_calls: list[tuple[str, bool]]) -> None:
        self._names = names
        self._set_calls = set_calls
        self.select_error: BaseException | None = None

    def list(self) -> list[Folder]:
        return [Folder(name) for name in self._names]

    def set(self, folder: str, readonly: bool = False) -> None:  # noqa: FBT001, FBT002
        self._set_calls.append((folder, readonly))
        if self.select_error is not None:
            raise self.select_error
        if folder not in self._names:
            raise MailboxFolderSelectError(MISSING_FOLDER_ANSWER, "OK")


class FakeBox:
    """Stands in for an imap-tools MailBox: login/context-manager/folder/fetch."""

    def __init__(
        self,
        names: Sequence[str] = ("INBOX",),
        messages: Sequence[Msg] = (),
        fetch_error: BaseException | None = None,
    ) -> None:
        self.set_calls: list[tuple[str, bool]] = []
        self.login_calls: list[tuple[str, str]] = []
        self.fetch_calls: list[tuple[object, int | None, bool, bool]] = []
        self.folder = FolderManager(names, self.set_calls)
        self.fetch_error = fetch_error
        self._messages = list(messages)

    def login(self, user: str, password: str) -> Self:
        self.login_calls.append((user, password))
        return self

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def fetch(
        self,
        criteria: object,
        limit: int | None = None,
        headers_only: bool = False,  # noqa: FBT001, FBT002
        mark_seen: bool = True,  # noqa: FBT001, FBT002
    ) -> list[Msg]:
        self.fetch_calls.append((criteria, limit, headers_only, mark_seen))
        if self.fetch_error is not None:
            raise self.fetch_error
        return self._messages


def config(*, security: ImapSecurity = "starttls", tls_insecure: bool = False) -> EmailConfig:
    """The reader config the stand-in answers to; no env is read (every field is given)."""
    return EmailConfig(
        host="mail.local",
        port=1143,
        user="bridge-user",
        password=SecretStr("bridge-pass"),
        security=security,
        tls_insecure=tls_insecure,
    )


def patch_box(
    monkeypatch: pytest.MonkeyPatch, box: FakeBox, security: ImapSecurity = "starttls"
) -> dict[str, object]:
    """Make `ImapMailbox` open ``box``, returning what it was constructed with."""
    captured: dict[str, object] = {}

    def factory(host: str, port: int, ssl_context: ssl.SSLContext) -> FakeBox:
        captured["host"], captured["port"], captured["ssl"] = host, port, ssl_context
        return box

    monkeypatch.setattr(
        imap_module, "MailBoxStartTls" if security == "starttls" else "MailBox", factory
    )
    return captured
