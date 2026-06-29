"""Behavior tests for ImapMailbox over a fake imap-tools MailBox (no server, no network).

Proves the read-only discipline (EXAMINE via readonly=True, mark_seen=False) and the TLS-mode
selection; the live contract against a real Bridge is test_live.py.
"""

import ssl
from collections.abc import Sequence
from typing import Self

import pytest
from pydantic import SecretStr

import cortex_email.imap as imap_module
from cortex_email import EmailConfig, ImapMailbox, RawEmail
from cortex_email.config import ImapSecurity


class _Obj:
    def __init__(self, raw: bytes) -> None:
        self._raw = raw

    def as_bytes(self) -> bytes:
        return self._raw


class _Msg:
    def __init__(self, uid: str, raw: bytes) -> None:
        self.uid = uid
        self.obj = _Obj(raw)


class _Folder:
    def __init__(self, name: str) -> None:
        self.name = name


class _FolderManager:
    def __init__(self, names: Sequence[str], set_calls: list[tuple[str, bool]]) -> None:
        self._names = names
        self._set_calls = set_calls

    def list(self) -> list[_Folder]:
        return [_Folder(name) for name in self._names]

    def set(self, folder: str, readonly: bool = False) -> None:  # noqa: FBT001, FBT002
        self._set_calls.append((folder, readonly))


class _FakeBox:
    """Stands in for an imap-tools MailBox: login/context-manager/folder/fetch."""

    def __init__(self, names: Sequence[str] = (), messages: Sequence[_Msg] = ()) -> None:
        self.set_calls: list[tuple[str, bool]] = []
        self.login_calls: list[tuple[str, str]] = []
        self.fetch_calls: list[tuple[object, int | None, bool, bool]] = []
        self.folder = _FolderManager(names, self.set_calls)
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
    ) -> list[_Msg]:
        self.fetch_calls.append((criteria, limit, headers_only, mark_seen))
        return self._messages


def _config(*, security: ImapSecurity = "starttls", tls_insecure: bool = False) -> EmailConfig:
    return EmailConfig(
        host="mail.local",
        port=1143,
        user="bridge-user",
        password=SecretStr("bridge-pass"),
        security=security,
        tls_insecure=tls_insecure,
    )


def _patch(
    monkeypatch: pytest.MonkeyPatch, box: _FakeBox, security: ImapSecurity
) -> dict[str, object]:
    captured: dict[str, object] = {}

    def factory(host: str, port: int, ssl_context: ssl.SSLContext) -> _FakeBox:
        captured["host"], captured["port"], captured["ssl"] = host, port, ssl_context
        return box

    monkeypatch.setattr(
        imap_module, "MailBoxStartTls" if security == "starttls" else "MailBox", factory
    )
    return captured


def test_list_folders_logs_in_and_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    box = _FakeBox(names=["INBOX", "Archive"])
    captured = _patch(monkeypatch, box, "starttls")
    assert list(ImapMailbox(_config()).list_folders()) == ["INBOX", "Archive"]
    assert box.login_calls == [("bridge-user", "bridge-pass")]
    assert (captured["host"], captured["port"]) == ("mail.local", 1143)


def test_search_is_headers_only_read_only_and_unseen(monkeypatch: pytest.MonkeyPatch) -> None:
    box = _FakeBox(messages=[_Msg("7", b"raw7"), _Msg("8", b"raw8")])
    _patch(monkeypatch, box, "starttls")
    result = ImapMailbox(_config()).search("INBOX", "ALL", 5)
    assert list(result) == [RawEmail("7", b"raw7"), RawEmail("8", b"raw8")]
    assert box.set_calls == [("INBOX", True)]  # EXAMINE, never SELECT
    ((_, limit, headers_only, mark_seen),) = box.fetch_calls
    assert (limit, headers_only, mark_seen) == (5, True, False)


def test_fetch_one_found_is_read_only_and_unseen(monkeypatch: pytest.MonkeyPatch) -> None:
    box = _FakeBox(messages=[_Msg("7", b"full7")])
    _patch(monkeypatch, box, "starttls")
    assert ImapMailbox(_config()).fetch("INBOX", "7") == RawEmail("7", b"full7")
    assert box.set_calls == [("INBOX", True)]
    ((_, limit, _headers, mark_seen),) = box.fetch_calls
    assert (limit, mark_seen) == (1, False)


def test_fetch_one_missing_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _FakeBox(messages=[]), "starttls")
    assert ImapMailbox(_config()).fetch("INBOX", "999") is None


def test_ssl_mode_uses_the_implicit_tls_box(monkeypatch: pytest.MonkeyPatch) -> None:
    box = _FakeBox(names=["INBOX"])
    captured = _patch(monkeypatch, box, "ssl")
    ImapMailbox(_config(security="ssl")).list_folders()
    assert captured["host"] == "mail.local"


def test_default_tls_verifies_the_certificate(monkeypatch: pytest.MonkeyPatch) -> None:
    box = _FakeBox(names=["INBOX"])
    captured = _patch(monkeypatch, box, "starttls")
    ImapMailbox(_config()).list_folders()
    context = captured["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED


def test_insecure_tls_disables_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    box = _FakeBox(names=["INBOX"])
    captured = _patch(monkeypatch, box, "starttls")
    ImapMailbox(_config(tls_insecure=True)).list_folders()
    context = captured["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_NONE
    assert context.check_hostname is False
