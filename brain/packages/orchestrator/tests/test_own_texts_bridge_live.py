"""The own-text overlay against a real ProtonMail Bridge, through the root's own wiring."""

import contextlib
import subprocess
import sys
import time
import uuid
from collections.abc import Generator, Mapping, Sequence
from datetime import UTC, datetime

import httpx
import pytest

from cortex_core import (
    DENIED_MSG,
    USER_DECLINED_MSG,
    ConfirmationRequest,
    TaintLedger,
    ToolCall,
    ToolDispatcher,
    ToolInvocation,
    ToolRegistry,
    Trust,
    TurnStamp,
)
from cortex_email import EmailConfig
from cortex_orchestrator import ToolsConfig, build_tool_registry
from cortex_orchestrator.own_texts import folder_unknown, no_matches, not_found, search_refused

# The port and path `cortex_email` serves on, and the URL a deployment points the brain at. The
# sidecar reads its own bind from its module, so this is the address rather than a second
# configuration of it.
_ENDPOINT = "http://127.0.0.1:9100/mcp"
_START_TIMEOUT_S = 60

# The two arguments that make a real server answer with a correction rather than with mail. The
# query is the client syntax ADR-0022's refused-search addendum wrote the correction for, which a
# Bridge answers `BAD`; the folder is a name no mailbox has, which it answers `NO`.
_CLIENT_SYNTAX = "from:someone@example.com"
_MISSING_FOLDER = "Receipts-no-mailbox-has-this"
# A uid past anything a mailbox has assigned, so the fetch finds nothing and the sidecar composes
# its own not-found answer rather than reading a message.
_MISSING_UID = "4294967290"

_SEARCH_TOOL = "search_emails"
_LIST_TOOL = "list_folders"
_READ_TOOL = "read_email"
_SEND_TOOL = "send_email"
_INBOX = "INBOX"


def _reachable() -> bool:
    with contextlib.suppress(httpx.HTTPError):
        httpx.get(_ENDPOINT, timeout=2)
        return True
    return False


@pytest.fixture(scope="module")
def sidecar() -> Generator[None, None, None]:
    """Run the shipped sidecar against the live Bridge for this module, then stop it."""
    if not EmailConfig().user:
        pytest.skip("set CORTEX_EMAIL_IMAP_USER/PASSWORD (~/.cortex/email.env) to run")
    process = subprocess.Popen([sys.executable, "-m", "cortex_email"])
    deadline = time.monotonic() + _START_TIMEOUT_S
    try:
        while time.monotonic() < deadline and not _reachable():
            time.sleep(1)
        if not _reachable():
            pytest.fail(f"the email sidecar did not answer on {_ENDPOINT} in {_START_TIMEOUT_S}s")
        yield
    finally:
        process.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=10)
        process.kill()


@pytest.fixture
def registry(sidecar: None) -> ToolRegistry:
    """The tool registry the composition root builds, pointed at the running sidecar."""
    del sidecar
    built, _ = build_tool_registry(ToolsConfig(backend="mcp", endpoint=_ENDPOINT))
    assert built is not None
    return built


def _empty_query() -> str:
    """A search a real mailbox answers with no matches, on a subject nothing can carry."""
    return f'SUBJECT "cortex-{uuid.uuid4().hex}"'


async def _folders(registry: ToolRegistry) -> tuple[str | None, str | None]:
    """One folder of this mailbox holding mail and one holding none, or ``None`` for either."""
    listed = await registry.invoke(ToolCall(id="f-0", name=_LIST_TOOL, arguments={}))
    with_mail: str | None = None
    without: str | None = None
    for index, folder in enumerate(listed.content.splitlines()):
        found = await registry.invoke(
            ToolCall(
                id=f"f-{index + 1}",
                name=_SEARCH_TOOL,
                arguments={"folder": folder, "query": "ALL", "limit": 1},
            )
        )
        if found.content == no_matches({}):
            without = without or folder
        elif not found.is_error:
            with_mail = with_mail or folder
        if with_mail is not None and without is not None:
            break
    return with_mail, without


@pytest.mark.integration
async def test_the_five_own_answers_off_a_real_bridge_come_back_trusted(
    registry: ToolRegistry,
) -> None:
    """Each answer the sidecar composes itself, driven by the Bridge's own reply, is re-stamped."""
    with_mail, _ = await _folders(registry)
    if with_mail is None:
        pytest.skip("no folder in this mailbox holds mail, so the not-found row cannot run")
    empty = _empty_query()
    cases: Sequence[tuple[str, Mapping[str, object], str | None]] = (
        (
            _SEARCH_TOOL,
            {"folder": with_mail, "query": _CLIENT_SYNTAX},
            search_refused({"query": _CLIENT_SYNTAX}),
        ),
        (
            _SEARCH_TOOL,
            {"folder": _MISSING_FOLDER, "query": "ALL"},
            folder_unknown({"folder": _MISSING_FOLDER}),
        ),
        (
            _READ_TOOL,
            {"folder": _MISSING_FOLDER, "uid": _MISSING_UID},
            folder_unknown({"folder": _MISSING_FOLDER}),
        ),
        (_SEARCH_TOOL, {"folder": with_mail, "query": empty}, no_matches({})),
        (
            _READ_TOOL,
            {"folder": with_mail, "uid": _MISSING_UID},
            not_found({"uid": _MISSING_UID, "folder": with_mail}),
        ),
    )
    for index, (tool, arguments, expected) in enumerate(cases):
        result = await registry.invoke(ToolCall(id=f"c-{index}", name=tool, arguments=arguments))
        assert (result.trust, result.content) == (Trust.TRUSTED, expected), (
            f"{tool} {arguments} came back {result.trust} with {result.content!r}"
        )


@pytest.mark.integration
async def test_a_read_of_an_empty_folder_never_reaches_the_not_found_answer(
    registry: ToolRegistry,
) -> None:
    """A ``read_email`` of a folder holding no mail raises here, so the own text is unreached."""
    _, without = await _folders(registry)
    if without is None:
        pytest.skip("every folder in this mailbox holds mail, so the empty-folder read cannot run")
    result = await registry.invoke(
        ToolCall(id="u-1", name=_READ_TOOL, arguments={"folder": without, "uid": _MISSING_UID})
    )
    assert result.trust is Trust.UNTRUSTED
    assert result.content != not_found({"uid": _MISSING_UID, "folder": without})
    assert result.is_error


@pytest.mark.integration
async def test_a_message_the_bridge_read_stays_untrusted(registry: ToolRegistry) -> None:
    """Mail is what the overlay must not re-stamp, and only a real mailbox can hand it over."""
    with_mail, _ = await _folders(registry)
    if with_mail is None:
        pytest.skip("no folder in this mailbox holds mail, so there is nothing to read")
    found = await registry.invoke(
        ToolCall(
            id="s-1", name=_SEARCH_TOOL, arguments={"folder": with_mail, "query": "ALL", "limit": 1}
        )
    )
    assert found.trust is Trust.UNTRUSTED
    uid = found.content.split("]")[0].removeprefix("[")
    read = await registry.invoke(
        ToolCall(id="r-1", name=_READ_TOOL, arguments={"folder": with_mail, "uid": uid})
    )
    assert read.trust is Trust.UNTRUSTED
    assert read.source is not None


class _Recorder:
    """A `ToolAuditSink` keeping the invocations, which is what the audit line is rendered from."""

    def __init__(self) -> None:
        self.lines: list[ToolInvocation] = []

    async def record(self, invocation: ToolInvocation) -> None:
        self.lines.append(invocation)


class _Declining:
    """A `Confirmer` that says no, so a send reaching the card is observed without one going out."""

    def __init__(self) -> None:
        self.asked: list[ConfirmationRequest] = []

    async def confirm(self, request: ConfirmationRequest) -> bool:
        self.asked.append(request)
        return False


class _Clock:
    """A `Clock` for the audit line's timestamp; the value is not what this measures."""

    def now(self) -> datetime:
        return datetime(2026, 9, 4, 4, 0, tzinfo=UTC)


@pytest.mark.integration
async def test_a_refused_search_is_audited_trusted_and_leaves_the_send_confirmable(
    registry: ToolRegistry,
) -> None:
    """The whole live claim of the overlay, in one turn: the audit line, the ledger, the gate."""
    audit, confirmer, ledger = _Recorder(), _Declining(), TaintLedger()
    dispatcher = ToolDispatcher(registry, audit, _Clock(), confirmer=confirmer)
    refused = await dispatcher.dispatch(
        ToolCall(id="d-1", name=_SEARCH_TOOL, arguments={"folder": _INBOX, "query": _CLIENT_SYNTAX})
    )
    ledger.observe(refused)
    assert refused.content == search_refused({"query": _CLIENT_SYNTAX})
    assert (audit.lines[-1].ok, audit.lines[-1].trust) == (False, Trust.TRUSTED)
    assert not ledger.tainted

    send = next(
        (spec for spec in await dispatcher.describe_tools() if spec.name == _SEND_TOOL), None
    )
    if send is None:
        pytest.skip("the sidecar is read-only here; set CORTEX_EMAIL_SEND_ENABLED=true to run")
    assert send.gated, "the wiring must stamp the sidecar's send gated, whatever it advertises"
    sent = await dispatcher.dispatch(
        ToolCall(
            id="d-2",
            name=_SEND_TOOL,
            arguments={"to": "nobody@example.com", "subject": "x", "body": "x"},
        ),
        stamp=TurnStamp(tainted=ledger.tainted),
        gated=send.gated,
    )
    assert sent.content == USER_DECLINED_MSG
    assert sent.content != DENIED_MSG
    assert [request.tool_name for request in confirmer.asked] == [_SEND_TOOL]
