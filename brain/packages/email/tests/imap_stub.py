"""A stand-in for the imap-tools ``MailBox``: what `ImapMailbox` talks to when no server exists.

Shared by the adapter's own behavior tests and by the `Mailbox` contract driver, so the real
adapter is driven over one stand-in rather than two that could drift apart on what an IMAP
library does. It is scriptable in the two directions a test cannot otherwise reach: `FakeBox`
takes the exception the *server* side of a fetch raises, which is how a refused query and a
dropped connection are both reproduced without a Bridge, and `FolderManager.select_error` is the
same knob for a SELECT. Unscripted, the folder manager answers a name it does not list exactly as
a real Bridge does, so the common case needs no script at all.
"""

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
# A NO that is not either of those: the mailbox is there, is listed, and will not open. Measured
# on the same Dovecot against a mailbox whose ACL leaves the account lookup rights only
# (docker/docker-compose.imap-probe.yml), so the fail-safe branch is scripted here from a
# sentence a real server really sent.
UNOPENABLE_FOLDER_ANSWER = ("NO", [b"[NOPERM] Permission denied (0.001 + 0.000 secs)."])
# A NO to a name that is not one a mailbox could have, rather than one no mailbox happens to
# have. Measured verbatim on the same Dovecot against the empty folder name, where the Bridge
# answers `MISSING_FOLDER_ANSWER` instead: RFC 5530's code for a request that can never succeed,
# and the only refusal in this file whose prose says nothing about a mailbox (ADR-0022
# refused-name addendum).
REFUSED_NAME_ANSWER = (
    "NO",
    [b"[CANNOT] Invalid mailbox name: Name is empty (0.001 + 0.000 secs)."],
)


# The LIST attributes a real server sends with a name that is only a point in the hierarchy,
# measured verbatim against the probe's `Parent`, which has a child and is not a mailbox:
# `FolderInfo(name='Parent', delim='/', flags=('\\Noselect', '\\HasChildren'))`.
NODE_FLAGS = ("\\Noselect", "\\HasChildren")
# What the same server sends with an ordinary leaf mailbox, so the adapter's filter is driven
# over both answers rather than over one and an empty tuple.
MAILBOX_FLAGS = ("\\HasNoChildren",)
# The same claim on the other server, measured verbatim on a live ProtonMail Bridge, which
# flags the two parents of its own hierarchy and then opens both:
# `FolderInfo(name='Folders', delim='/', flags=('\\Noselect', '\\Unmarked'))`.
OPEN_NODE_FLAGS = ("\\Noselect", "\\Unmarked")
# RFC 5258's newer word for the same claim, measured on the same Dovecot rather than read off
# the standard, verbatim from `LIST (SUBSCRIBED) "" "*"`: `(\Subscribed \NonExistent) "/" Ghost`.
# It arrives instead of `\Noselect` and never beside it, and only in a listing that asks for
# subscriptions, which imap-tools' `folder.list()` does not ask for. So what this scripts is the
# answer a server would hand an adapter that asked, which is why the filter reads the word at all
# (ADR-0022 newer-spelling addendum).
NONEXISTENT_NODE_FLAGS = ("\\Subscribed", "\\NonExistent")


class Folder:
    """One name as ``folder.list()`` returns it: the name and the server's own LIST flags."""

    def __init__(self, name: str, flags: Sequence[str] = MAILBOX_FLAGS) -> None:
        self.name = name
        self.flags = tuple(flags)


class FolderManager:
    """The ``box.folder`` manager: lists names and records every ``set`` (folder, readonly).

    A name it does not list is refused the way a real Bridge refuses one, verbatim from a live
    measurement (`MISSING_FOLDER_ANSWER`), so the adapter's classification is driven over the
    answer it will really meet. ``select_error``, when set, replaces that with whatever a test
    wants a refused SELECT to say instead, which is how this suite reaches the other kind of
    ``NO``; the live one is a server run for the purpose (`test_imap_probe_live.py`).

    ``nodes`` are listed and are not mailboxes, the way a real server lists a `\\Noselect`
    parent: they come back from `list` carrying `NODE_FLAGS` and are refused by `set` exactly
    as a name no mailbox has is, because that is what the probe measured Dovecot doing.
    ``open_nodes`` are the Bridge's answer to the same question: listed with the same flags and
    opening anyway, which is why the adapter selects the folder rather than trusting the flags.
    """

    def __init__(
        self,
        names: Sequence[str],
        set_calls: list[tuple[str, bool]],
        nodes: Sequence[str] = (),
        node_flags: Sequence[str] = NODE_FLAGS,
        open_nodes: Sequence[str] = (),
    ) -> None:
        self._names = names
        self._nodes = nodes
        self._node_flags = node_flags
        self._open_nodes = open_nodes
        self._set_calls = set_calls
        self.select_error: BaseException | None = None

    def list(self) -> list[Folder]:
        listed = [Folder(name) for name in self._names]
        flagged = [*self._nodes, *self._open_nodes]
        return listed + [Folder(name, self._node_flags) for name in flagged]

    def set(self, folder: str, readonly: bool = False) -> None:  # noqa: FBT001, FBT002
        self._set_calls.append((folder, readonly))
        if self.select_error is not None:
            raise self.select_error
        if folder not in self._names and folder not in self._open_nodes:
            raise MailboxFolderSelectError(MISSING_FOLDER_ANSWER, "OK")


class FakeBox:
    """Stands in for an imap-tools MailBox: login/context-manager/folder/fetch.

    ``fetch_error``, when set, is raised out of ``fetch`` the way the IMAP stack raises out of a
    real one. Settable after construction so a test can let a call succeed and then take the
    server away, or hand the same box to a contract check that refuses on demand.
    """

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
        self.folder = FolderManager(names, self.set_calls, nodes, node_flags, open_nodes)
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
