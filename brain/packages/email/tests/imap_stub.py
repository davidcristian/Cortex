"""A stand-in for the imap-tools ``MailBox``: what `ImapMailbox` talks to with no server."""

import ssl
from collections.abc import Mapping, Sequence
from imaplib import IMAP4
from typing import Self

import pytest
from imap_tools import MailboxFolderSelectError, MailboxUidsError
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


# Refusals measured verbatim on two servers: a ProtonMail Bridge for a name no mailbox has,
# and Dovecot 2.3.21 for the same, for a mailbox whose ACL leaves this account lookup rights
# only, and for a name it will not read as a mailbox name at all.
MISSING_FOLDER_ANSWER = ("NO", [b"no such mailbox"])
OTHER_MISSING_FOLDER_ANSWER = ("NO", [b"Mailbox doesn't exist: Receipts (0.001 + 0.000 secs)."])
UNOPENABLE_FOLDER_ANSWER = ("NO", [b"[NOPERM] Permission denied (0.001 + 0.000 secs)."])
REFUSED_NAME_ANSWER = (
    "NO",
    [b"[CANNOT] Invalid mailbox name: Name is empty (0.001 + 0.000 secs)."],
)

type Answer = tuple[str, list[bytes | tuple[bytes, bytes] | None]]

# Read answers measured verbatim: RFC 3501's OK with no data for a uid no message has, the NO
# Dovecot sends over a message file it cannot open under `imap_fetch_failure = no-after`, the
# BYE and dropped connection its default sends instead, and a refused UID search key.
NOTHING_FETCHED: Answer = ("OK", [None])
DECLINED_READ_ANSWER: Answer = (
    "NO",
    [
        b"[SERVERBUG] Internal error occurred. Refer to server log for more information. "
        b"[2026-09-05 04:43:45] (0.001 + 0.000 secs)."
    ],
)
DROPPED_READ = IMAP4.abort(
    "command: UID => FETCH failed: Internal error occurred. Refer to server log for more "
    "information. [2026-09-05 01:02:49]"
)
REFUSED_UID_SEARCH = MailboxUidsError(("NO", [b"no such message"]), "OK")


# LIST attributes measured verbatim: Dovecot's hierarchy node and its ordinary leaf, the
# Bridge's own flagged parents that still open, and the `\NonExistent` Dovecot sends only to
# a LIST that asks for subscriptions.
NODE_FLAGS = ("\\Noselect", "\\HasChildren")
MAILBOX_FLAGS = ("\\HasNoChildren",)
OPEN_NODE_FLAGS = ("\\Noselect", "\\Unmarked")
NONEXISTENT_NODE_FLAGS = ("\\Subscribed", "\\NonExistent")


class Folder:
    """One name as ``folder.list()`` returns it: the name and the server's own LIST flags."""

    def __init__(self, name: str, flags: Sequence[str] = MAILBOX_FLAGS) -> None:
        self.name = name
        self.flags = tuple(flags)


class FolderManager:
    """The ``box.folder`` manager: lists names and records every ``set`` (folder, readonly)."""

    def __init__(
        self,
        names: Sequence[str],
        set_calls: list[tuple[str, bool]],
        nodes: Sequence[str] = (),
        node_flags: Sequence[str] = NODE_FLAGS,
        open_nodes: Sequence[str] = (),
        counts: Mapping[str, int] | None = None,
    ) -> None:
        self._names = names
        self._nodes = nodes
        self._node_flags = node_flags
        self._open_nodes = open_nodes
        self._set_calls = set_calls
        self._counts = counts or {}
        self.select_error: BaseException | None = None
        self.select_answer: Answer | None = None
        self.current: str | None = None

    def list(self) -> list[Folder]:
        listed = [Folder(name) for name in self._names]
        flagged = [*self._nodes, *self._open_nodes]
        return listed + [Folder(name, self._node_flags) for name in flagged]

    def set(self, folder: str, readonly: bool = False) -> Answer:  # noqa: FBT001, FBT002
        self._set_calls.append((folder, readonly))
        if self.select_error is not None:
            raise self.select_error
        if folder not in self._names and folder not in self._open_nodes:
            raise MailboxFolderSelectError(MISSING_FOLDER_ANSWER, "OK")
        self.current = folder
        if self.select_answer is not None:
            return self.select_answer
        return ("OK", [str(self._counts.get(folder, 0)).encode()])


def _fetched(message: Msg) -> list[bytes | tuple[bytes, bytes] | None]:
    """One message as the Bridge's UID FETCH item reaches imaplib, measured verbatim."""
    raw = message.obj.as_bytes()
    return [
        (f"1 (BODY[] {{{len(raw)}}}".encode(), raw),
        f" UID {message.uid} FLAGS () RFC822.SIZE {len(raw)})".encode(),
    ]


NOT_A_NUMBER = IMAP4.error(
    "UID command error: BAD [b'[Error offset=16]: expected valid digit for number']"
)


class FakeClient:
    """The ``box.client`` the adapter sends its one ``UID FETCH`` through, answering by uid."""

    def __init__(self, box: "FakeBox") -> None:
        self._box = box
        self.uid_calls: list[tuple[str, ...]] = []

    def uid(self, command: str, *args: str) -> Answer:
        self.uid_calls.append((command, *args))
        if self._box.fetch_error is not None:
            raise self._box.fetch_error
        if self._box.fetch_answer is not None:
            return self._box.fetch_answer
        uid = args[0]
        held = self._box.messages_in_open_folder()
        if any(mark in uid for mark in ",:") and held:
            return ("OK", _fetched(held[0]))
        if not uid.replace(",", "").replace(":", "").replace("*", "").isdigit() or uid == "0":
            raise NOT_A_NUMBER
        for message in held:
            if message.uid == uid:
                return ("OK", _fetched(message))
        return NOTHING_FETCHED


class FakeBox:
    """Stands in for an imap-tools MailBox: login/context-manager/folder/fetch/client."""

    def __init__(
        self,
        names: Sequence[str] = ("INBOX",),
        messages: Sequence[Msg] = (),
        fetch_error: BaseException | None = None,
        nodes: Sequence[str] = (),
        node_flags: Sequence[str] = NODE_FLAGS,
        open_nodes: Sequence[str] = (),
    ) -> None:
        self.set_calls: list[tuple[str, bool]] = []
        self.login_calls: list[tuple[str, str]] = []
        self.fetch_calls: list[tuple[object, int | None, bool, bool]] = []
        self._mail_folder = names[0]
        self._messages = list(messages)
        self.folder = FolderManager(
            names, self.set_calls, nodes, node_flags, open_nodes, {names[0]: len(messages)}
        )
        self.client = FakeClient(self)
        self.fetch_error = fetch_error
        self.fetch_answer: Answer | None = None

    def messages_in_open_folder(self) -> list[Msg]:
        """The canned messages when the open folder is the one holding them, else none."""
        return self._messages if self.folder.current == self._mail_folder else []

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
        held = self.messages_in_open_folder()
        if not held and "UID" in str(criteria):
            raise REFUSED_UID_SEARCH
        return held


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
