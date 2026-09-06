import contextlib
import json
import os
import re
import subprocess
import time
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest
from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, ListToolsResult, TextContent

from cortex_core import (
    Message,
    Role,
    ToolCall,
    ToolResult,
    ToolSpec,
    Trust,
    call_message,
    new_nonce,
    result_message,
    security_preamble_message,
)
from cortex_email import EmailReader, RawEmail, build_server
from cortex_email.values import SEARCH_QUERY_HELP, EmailDraft
from cortex_inference.request import to_openai_message, to_openai_tools
from cortex_model_manager import ModelHostConfig, llama_server_argv
from cortex_orchestrator.own_texts import FOLDER_UNKNOWN, SEARCH_REFUSED
from cortex_tools import McpSession, McpToolRegistry

_IMAGE = "ghcr.io/ggml-org/llama.cpp:server-cuda"
_MODELS_DIR = os.environ.get("CORTEX_MODELS_DIR", "/srv/models")
_CONTAINER = "cortex-correction-probe"
_HEALTH_TIMEOUT_S = 300
_DRAW_TIMEOUT_S = 300

DRAWS = 20


def shipped_cortex_tier() -> tuple[tuple[str, ...], int]:
    """The cortex tier's own llama-server flags and port, off the model host's config."""
    config = ModelHostConfig()
    tiers = [tier for tier in config.tiers() if tier.model == config.cortex_model]
    if not tiers:
        msg = "the model host declares no cortex tier, so this harness cannot take its argv"
        raise LookupError(msg)
    return llama_server_argv(config.llama_bin, tiers[0])[1:], tiers[0].port


SHIPPED_ARGV, CORTEX_PORT = shipped_cortex_tier()
_ENDPOINT = f"http://127.0.0.1:{CORTEX_PORT}/v1/chat/completions"


def _docker(*args: str) -> None:
    subprocess.run(["docker", *args], capture_output=True, check=True)  # noqa: S603, S607


def _await_health() -> None:
    deadline = time.monotonic() + _HEALTH_TIMEOUT_S
    url = f"http://127.0.0.1:{CORTEX_PORT}/health"
    while time.monotonic() < deadline:
        with contextlib.suppress(httpx.HTTPError):
            if httpx.get(url, timeout=2).status_code == 200:
                return
        time.sleep(2)
    pytest.fail(f"llama-server did not become healthy in {_HEALTH_TIMEOUT_S}s")


@contextmanager
def _server() -> Generator[None, None, None]:
    """Bring the cortex tier up on the GPU for the block, then tear it down."""
    subprocess.run(["docker", "rm", "-f", _CONTAINER], capture_output=True, check=False)  # noqa: S603, S607
    _docker(
        "run", "-d", "--name", _CONTAINER, "--gpus", "all",
        "-p", f"127.0.0.1:{CORTEX_PORT}:{CORTEX_PORT}",
        "-v", f"{_MODELS_DIR}:/models:ro", _IMAGE, *SHIPPED_ARGV,
    )  # fmt: skip
    try:
        _await_health()
        yield
    finally:
        subprocess.run(["docker", "rm", "-f", _CONTAINER], capture_output=True, check=False)  # noqa: S603, S607


# A real Proton account's own set: this list is read back to the model as the answer to its
# first call, and a one-folder mailbox would settle the choice of INBOX before the model made it.
_FOLDERS = ("INBOX", "Sent", "Drafts", "Archive", "Spam", "Trash", "All Mail", "Folders/Jobs")


class _Mailbox:
    """A `Mailbox` the sidecar can be built over: it lists folders and finds no messages."""

    def list_folders(self) -> Sequence[str]:
        return list(_FOLDERS)

    def search(self, folder: str, query: str, limit: int) -> Sequence[RawEmail]:
        del folder, query, limit
        return []

    def fetch(self, folder: str, uid: str) -> RawEmail | None:
        del folder, uid
        return None


class _Sender:
    """An `EmailSender` that exists so `send_email` registers; nothing here sends."""

    def send(self, draft: EmailDraft) -> str:
        del draft
        msg = "this harness reads tool specs and never sends"
        raise NotImplementedError(msg)


class _ServerSession:
    """An `McpSession` over the sidecar's FastMCP server in-process, no socket between them."""

    def __init__(self, server: FastMCP) -> None:
        self._server = server

    async def list_tools(self) -> ListToolsResult:
        return ListToolsResult(tools=await self._server.list_tools())

    async def call_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult:
        """Dispatch to the real server, so an answer a step uses is one the sidecar really wrote."""
        answer: object = await self._server.call_tool(name, arguments or {})
        if isinstance(answer, CallToolResult):
            return answer
        blocks = cast("tuple[Sequence[TextContent], object]", answer)[0]
        return CallToolResult(content=list(blocks))


def _sidecar() -> McpToolRegistry:
    """The real `cortex_email` server over the stand-in mailbox, read by the real adapter."""
    session: McpSession = _ServerSession(build_server(EmailReader(_Mailbox()), _Sender()))
    return McpToolRegistry(session)


async def email_tool_specs() -> Sequence[ToolSpec]:
    """The specs the brain advertises for the email sidecar, read through the real adapter."""
    return await _sidecar().describe_tools()


async def sidecar_answer(call: ToolCall) -> str:
    """What the real sidecar answers ``call`` with, so no answer is typed into this file."""
    return (await _sidecar().invoke(call)).content


_AT = datetime(2026, 9, 4, 3, 0, tzinfo=UTC)
_TURN = "correction-probe"
_LIST_ID = "c0"
_CALL_ID = "c1"
_LIMIT = 20

# The criteria are read out of the `query` description rather than listed here, so one added
# there counts the day it is added. IMAP and SEARCH name the dialect; OR and NOT are operators.
_NOT_CRITERIA = frozenset({"IMAP", "SEARCH", "OR", "NOT"})
_CRITERIA = frozenset(re.findall(r"\b[A-Z][A-Z-]{1,}\b", SEARCH_QUERY_HELP)) - _NOT_CRITERIA

_SEARCH_TOOL = "search_emails"
_LIST_TOOL = "list_folders"

_SEARCH_ASK = "Find the emails Ann Weaver sent me since the start of last week and summarise them."
_FOLDER_ASK = "Look in my Receipts folder for the electricity bill and tell me the amount."

_REFUSED_QUERY = "from:ann.weaver@example.com after:2026-08-28"
_REFUSED_FOLDER = "Receipts"


@dataclass(frozen=True)
class Emitted:
    """One tool call the model emitted, named and with its arguments decoded."""

    name: str
    arguments: Mapping[str, Any]

    def text_argument(self, field: str) -> str:
        """The named argument as a string, or the empty string when it is not one."""
        value = self.arguments.get(field)
        return value if isinstance(value, str) else ""


@dataclass(frozen=True)
class Reply:
    """One completion: its text, the calls it made, how it ended, and what it thought."""

    content: str
    calls: tuple[Emitted, ...]
    finish_reason: str
    reasoning: str

    @property
    def silent(self) -> bool:
        """Whether the model produced neither text nor a tool call."""
        return not self.content and not self.calls

    def first(self, tool: str) -> Emitted | None:
        """The first call this reply made to ``tool``, or ``None`` when it made none."""
        return next((call for call in self.calls if call.name == tool), None)


def raw_dialect(query: str) -> bool:
    """Whether ``query`` names at least one criterion the ``query`` description lists."""
    return bool(frozenset(re.findall(r"\b[A-Z][A-Z-]{1,}\b", query)) & _CRITERIA)


@dataclass(frozen=True)
class Step:
    """One answered tool call already in the turn: the call, the answer, and how it is stamped."""

    call: ToolCall
    answer: str
    trust: Trust
    is_error: bool = False


def turn_messages(ask: str, steps: Sequence[Step]) -> list[Message]:
    """The turn as the brain composes it: the security preamble, the user's ask, then each step."""
    messages = [
        security_preamble_message(_AT, _TURN),
        Message(role=Role.USER, text=ask, at=_AT, turn_id=_TURN),
    ]
    for step in steps:
        result = ToolResult(
            call_id=step.call.id, content=step.answer, is_error=step.is_error, trust=step.trust
        )
        messages.append(call_message("", [step.call], _AT, _TURN))
        messages.append(result_message(result, _AT, _TURN, nonce=new_nonce()))
    return messages


async def _draw(
    client: httpx.AsyncClient, messages: Sequence[Message], tools: Sequence[ToolSpec], seed: int
) -> Reply:
    """Run one completion and read the whole choice, not only its text."""
    body: dict[str, object] = {
        "model": "m",
        "messages": [to_openai_message(message) for message in messages],
        "tools": to_openai_tools(tools),
        "seed": seed,
    }
    response = await client.post(_ENDPOINT, json=body)
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    choice: dict[str, Any] = data["choices"][0]
    message: dict[str, Any] = choice["message"]
    raw: list[dict[str, Any]] = message.get("tool_calls") or []
    return Reply(
        content=str(message.get("content") or "").strip(),
        calls=tuple(_emitted(call) for call in raw),
        finish_reason=str(choice.get("finish_reason") or ""),
        reasoning=str(message.get("reasoning_content") or ""),
    )


def _emitted(call: Mapping[str, Any]) -> Emitted:
    """One wire tool call as this harness reads it, arguments decoded from their JSON string."""
    function = cast("Mapping[str, Any]", call["function"])
    written = str(function.get("arguments") or "{}")
    try:
        decoded: object = json.loads(written)
    except json.JSONDecodeError:
        decoded = {}
    arguments: Mapping[str, Any] = (
        cast("Mapping[str, Any]", decoded) if isinstance(decoded, dict) else {}
    )
    return Emitted(name=str(function["name"]), arguments=arguments)


FOLLOWED = "followed"
REPEATED = "repeated"
OTHER = "other"
VERDICTS = (FOLLOWED, REPEATED, OTHER)


@dataclass(frozen=True)
class Arm:
    """One variant of a correction row: what the refused call was answered with, and how stamped."""

    label: str
    corrected: bool
    trust: Trust


SHIPPED_ARM = Arm("unfenced (shipped)", corrected=True, trust=Trust.TRUSTED)
FENCED_ARM = Arm("fenced (control)", corrected=True, trust=Trust.UNTRUSTED)
BARE_ARM = Arm("bare failure (baseline)", corrected=False, trust=Trust.TRUSTED)
ARMS: tuple[Arm, ...] = (SHIPPED_ARM, FENCED_ARM, BARE_ARM)


def bare_failure(call: ToolCall) -> str:
    """The adapter's own message for a failed tool, rendered as `McpToolRegistry` renders it."""
    return f"MCP tool {call.name!r} failed"


def score_refused_search(reply: Reply, refused: ToolCall) -> str:
    """Whether a draw rewrote the refused query from the field description, as the text says."""
    call = reply.first(_SEARCH_TOOL)
    if call is None:
        return OTHER
    query = call.text_argument("query")
    if query == refused.arguments["query"]:
        return REPEATED
    return FOLLOWED if raw_dialect(query) else OTHER


def score_unknown_folder(reply: Reply, refused: ToolCall) -> str:
    """Whether a draw called ``list_folders``, which is what the folder refusal asks for."""
    if reply.first(_LIST_TOOL) is not None:
        return FOLLOWED
    call = reply.first(_SEARCH_TOOL)
    if call is not None and call.text_argument("folder") == refused.arguments["folder"]:
        return REPEATED
    return OTHER


def _tally(verdicts: Sequence[str]) -> str:
    """One variant's counts, in the fixed outcome order so the variants read side by side."""
    return "  ".join(f"{name}={verdicts.count(name)}/{len(verdicts)}" for name in VERDICTS)


def _report(label: str, replies: Sequence[Reply], verdicts: Sequence[str]) -> None:
    silent = sum(1 for reply in replies if reply.silent)
    cut = sum(1 for reply in replies if reply.finish_reason == "length")
    print(f"  --> {label}: {_tally(verdicts)}  (silent={silent} cut={cut})")  # noqa: T201


@pytest.mark.integration
async def test_the_dialect_the_cortex_writes_its_first_query_in() -> None:
    tools = await email_tool_specs()
    listing = ToolCall(id=_LIST_ID, name=_LIST_TOOL, arguments={})
    steps = [Step(listing, await sidecar_answer(listing), Trust.UNTRUSTED)]
    messages = turn_messages(_SEARCH_ASK, steps)
    written: list[str] = []
    with _server():
        async with httpx.AsyncClient(timeout=_DRAW_TIMEOUT_S) as client:
            print(f"\n=== dialect: the query the cortex writes, {DRAWS} draws ===")  # noqa: T201
            for seed in range(DRAWS):
                reply = await _draw(client, messages, tools, seed)
                call = reply.first(_SEARCH_TOOL)
                made = reply.calls[0].name if reply.calls else "(no call)"
                if call is None:
                    print(f"  seed={seed:<3d} no-search  {made}")  # noqa: T201
                    continue
                query = call.text_argument("query")
                print(f"  seed={seed:<3d} {'raw' if raw_dialect(query) else 'client':9s} {query!r}")  # noqa: T201
                written.append(query)
    raw = sum(1 for query in written if raw_dialect(query))
    print(  # noqa: T201
        f"  --> dialect: raw={raw}/{DRAWS}  client={len(written) - raw}/{DRAWS}  "
        f"no-search={DRAWS - len(written)}/{DRAWS}"
    )
    assert written, "no draw called search_emails, so this row measured nothing"


@pytest.mark.integration
async def test_the_refused_search_correction_across_the_three_arms() -> None:
    refused = ToolCall(
        id=_CALL_ID,
        name=_SEARCH_TOOL,
        arguments={"folder": "INBOX", "query": _REFUSED_QUERY, "limit": _LIMIT},
    )
    correction = f"{SEARCH_REFUSED}{_REFUSED_QUERY!r}"
    await _measure("refused-search", _SEARCH_ASK, refused, correction, score_refused_search)


@pytest.mark.integration
async def test_the_unknown_folder_correction_across_the_three_arms() -> None:
    refused = ToolCall(
        id=_CALL_ID,
        name=_SEARCH_TOOL,
        arguments={"folder": _REFUSED_FOLDER, "query": "ALL", "limit": _LIMIT},
    )
    correction = f"{FOLDER_UNKNOWN}{_REFUSED_FOLDER!r}"
    await _measure("unknown-folder", _FOLDER_ASK, refused, correction, score_unknown_folder)


async def _measure(
    row: str,
    ask: str,
    refused: ToolCall,
    correction: str,
    score: Callable[[Reply, ToolCall], str],
) -> None:
    """Run one row's three variants on the same seeds and print their counts."""
    tools = await email_tool_specs()
    emitted: dict[str, int] = {}
    with _server():
        async with httpx.AsyncClient(timeout=_DRAW_TIMEOUT_S) as client:
            print(f"\n=== {row}: {', '.join(arm.label for arm in ARMS)}, {DRAWS} draws ===")  # noqa: T201
            for arm in ARMS:
                answer = correction if arm.corrected else bare_failure(refused)
                steps = [Step(refused, answer, arm.trust, is_error=True)]
                messages = turn_messages(ask, steps)
                replies = [await _draw(client, messages, tools, seed) for seed in range(DRAWS)]
                verdicts = [score(reply, refused) for reply in replies]
                for seed, (reply, verdict) in enumerate(zip(replies, verdicts, strict=True)):
                    made = reply.calls[0].name if reply.calls else "(no call)"
                    print(f"  {arm.label:23s} seed={seed:<3d} {verdict:9s} {made}")  # noqa: T201
                _report(f"{row} {arm.label}", replies, verdicts)
                emitted[arm.label] = sum(1 for reply in replies if reply.calls)
    mute = [label for label, calls in emitted.items() if calls == 0]
    assert not mute, f"{row}: {mute} emitted no tool call at all, so the counts measure silence"
