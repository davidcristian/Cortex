"""Does the shipped cortex act on the email sidecar's correction, fenced or unfenced (ADR-0013)?

The own-text overlay re-stamps the two refusals ``Trust.TRUSTED``, so ``result_message`` hands
them to the model verbatim where they used to arrive inside the fence the ``SECURITY_PREAMBLE``
says never to obey. Both refusals are instructions: rewrite the search from the query field's own
description, and call ``list_folders`` before naming a folder again. Whether the model follows
either one, in either framing, was unmeasured on both sides of that build, so this harness
measures both and publishes the counts.

Three measurements, each a row of its own so ``-k`` selects one:

- **dialect**: a turn with no refusal in it, which measures the cost the refused-search
  correction exists to recover. It counts how often the first ``search_emails`` is written in a
  mail client's ``key:value`` syntax rather than in the raw IMAP criteria the ``query`` field
  describes, every client-syntax query being a dispatch the refusal has to buy back.
- **refused-search**: the same turn continued from a client-syntax query the server refused. A
  draw follows the correction when its next ``search_emails`` carries a different query written
  in the described dialect.
- **unknown-folder**: the same shape for a folder no mailbox has. A draw follows the correction
  when it calls ``list_folders``.

Each correction row runs three arms on the same twenty seeds. The shipped arm hands the model the
refusal trusted, which is what the own-text overlay made it. The **control** arm fences the same
sentence, which is what this repo shipped until that overlay landed and is the before the entry
asking for this measurement had nothing to compare against. The third arm answers the same call
with the adapter's bare ``MCP tool '<name>' failed``, trusted and carrying no correction, and it
is the baseline the other two have to be read against: a move the model makes anyway shows the
same count under a sentence that asked for it and under one that said nothing.

Twenty draws an arm, each at its own seed and the arms drawn on the same twenty, so a difference
between them is not one arm's sampling.

Nothing about the request is typed here that the deployment declares elsewhere: the server's
command line is the model host's own cortex tier (``ModelHostConfig`` through
``llama_server_argv``), the messages are composed by the shipped ``security_preamble_message``,
``call_message`` and ``result_message`` and mapped by the adapter's own ``to_openai_message``,
and the tools are the real ``cortex_email`` server's specs read through the real
``McpToolRegistry``. The body carries no temperature and no ``max_tokens``, which is what a plain
Converse turn's payload carries, so the sampling is the tier's own.

Integration-marked (excluded from CI and the coverage gate). Needs the GPU, the toolkit and the
models at ``CORTEX_MODELS_DIR`` (docs/runbooks/llamacpp-gpu.md):

    cd brain && CORTEX_MODELS_DIR=/srv/models uv run pytest -m integration --no-cov -s \\
        packages/orchestrator/tests/test_unfenced_correction_live.py
"""

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

# How many draws an arm. Three is a story and twenty is a measurement: the reply that decides a
# draw is one tool call off a sampler the tier leaves at its own defaults, so a rate is what
# there is to read here and a rate off three draws is worth nothing.
DRAWS = 20


# ── the server, started the way the model host starts the cortex tier ────────


def shipped_cortex_tier() -> tuple[tuple[str, ...], int]:
    """The cortex tier's own llama-server flags and port, off the model host's config.

    Read rather than typed, for the reason the injection harness reads its subagent tier's
    reasoning-off pair there: a command line written into a test file is a second spelling of a
    deployment contract, and a row measured against it describes the flags the harness remembers.
    The binary is dropped from the front because the image's entrypoint is that binary.
    """
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


# ── the tools, read off the real email sidecar ───────────────────────────────


# The folders the stand-in mailbox offers. A real Proton account's own set, since the dialect row
# reads this list back to the model as the answer to the call it really makes first, and a
# one-folder mailbox would make the choice of INBOX something the context had already settled.
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
        del name, arguments
        return CallToolResult(content=[TextContent(type="text", text="")])


def _sidecar() -> McpToolRegistry:
    """The real `cortex_email` server over the stand-in mailbox, read by the real adapter."""
    session: McpSession = _ServerSession(build_server(EmailReader(_Mailbox()), _Sender()))
    return McpToolRegistry(session)


async def email_tool_specs() -> Sequence[ToolSpec]:
    """The specs the brain advertises for the email sidecar, read through the real adapter.

    The whole point of the refused-search correction is that it sends the model back to the
    ``query`` field's own description, so a harness that offered a hand-written schema would be
    measuring whether the model can follow a pointer to a field this repo does not ship.
    """
    return await _sidecar().describe_tools()


async def sidecar_answer(call: ToolCall) -> str:
    """What the real sidecar answers ``call`` with, so no answer is typed into this file."""
    return (await _sidecar().invoke(call)).content


# ── the exchange, composed by the shipped helpers ────────────────────────────

_AT = datetime(2026, 9, 4, 3, 0, tzinfo=UTC)
_TURN = "correction-probe"
_LIST_ID = "c0"
_CALL_ID = "c1"
# The sidecar's own default for how many matches a search returns, restated so the refused call
# carries the argument a real dispatch carries.
_LIMIT = 20

# The words the ``query`` description names as criteria, which is the dialect the refusal sends
# the model back to. Derived from that description rather than listed, exactly as the live Bridge
# suite derives it: a criterion added there is one a corrected query may use the day it is added.
# IMAP and SEARCH name the dialect itself; OR and NOT are operators rather than criteria and a
# query holding only one of them has still named nothing to match on.
_NOT_CRITERIA = frozenset({"IMAP", "SEARCH", "OR", "NOT"})
_CRITERIA = frozenset(re.findall(r"\b[A-Z][A-Z-]{1,}\b", SEARCH_QUERY_HELP)) - _NOT_CRITERIA

_SEARCH_TOOL = "search_emails"
_LIST_TOOL = "list_folders"

# What the user asks for, phrased the way somebody asks for mail rather than the way an IMAP
# query is written: naming a person and a date range leaves the model to decide the dialect.
_SEARCH_ASK = "Find the emails Ann Weaver sent me since the start of last week and summarise them."
_FOLDER_ASK = "Look in my Receipts folder for the electricity bill and tell me the amount."

# The query the refused-search row is continued from, and the folder the other row named. Both
# are held fixed across the arms, so the three read identical context and differ only in the
# answer they got back. The query is a mail client's syntax, which is the shape ADR-0022's
# refused-search addendum wrote the correction for and the shape a real server answers `BAD`.
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
    """One completion: its text, the calls it made, how it ended, and what it thought.

    ``finish_reason`` and ``reasoning`` ride along because a reasoning model that spends its
    whole budget thinking returns a reply that emits no call, and a row of "did not follow the
    correction" read off that would be a measurement of silence rather than of obedience.
    """

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
    """Whether ``query`` names at least one criterion the ``query`` description spells out.

    A rewritten query is only a corrected one if it is written in the dialect the correction
    points at, and a mail client's ``from:someone`` carries no criterion word at all, which is
    what separates the two without this file holding a parser for either.
    """
    return bool(frozenset(re.findall(r"\b[A-Z][A-Z-]{1,}\b", query)) & _CRITERIA)


@dataclass(frozen=True)
class Step:
    """One answered tool call already in the turn: the call, the answer, and how it is stamped.

    ``trust`` is the whole variable under measurement. ``result_message`` hands a ``TRUSTED``
    answer to the model verbatim and wraps an ``UNTRUSTED`` one in the turn's nonce'd fence, so
    a step is the same exchange in either framing and differs only there.
    """

    call: ToolCall
    answer: str
    trust: Trust
    is_error: bool = False


def turn_messages(ask: str, steps: Sequence[Step]) -> list[Message]:
    """The turn as the brain composes it: the standing rule, the user's ask, then each step.

    Every message is built by the shipped helper that builds it in a real turn, so what reaches
    the model here is what reaches it there: the ``SECURITY_PREAMBLE`` as the one system message
    a tool-enabled turn opens with, ``call_message`` for the assistant step that asked, and
    ``result_message`` for the answer, framing included.
    """
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
    """Run one completion and read the whole choice, not only its text.

    The body carries no temperature and no ``max_tokens``, which is what ``build_payload`` sends
    for a Converse turn that named no bounds, so every draw is sampled the way the deployment
    samples. ``seed`` is the one key added: it makes the twenty draws of an arm reproducible and
    lets the two framings of one row be drawn on the same twenty, which is what makes a
    difference between them something other than one arm's luck.
    """
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


# ── the three rows ───────────────────────────────────────────────────────────

# What one draw did, in the vocabulary each row scores. `FOLLOWED` is the correction's own
# instruction carried out, `REPEATED` is the call the correction refused sent again, which is the
# failure the refused-search sentence names outright, and `OTHER` is everything else: a reply
# with no call, a different tool, or a query rewritten into something the dialect does not name.
FOLLOWED = "followed"
REPEATED = "repeated"
OTHER = "other"
VERDICTS = (FOLLOWED, REPEATED, OTHER)


@dataclass(frozen=True)
class Arm:
    """One arm of a correction row: what the refused call was answered with, and how stamped.

    ``corrected`` picks the text. True is the sidecar's own refusal, the sentence that carries
    the instruction. False is the adapter's bare ``MCP tool '<name>' failed``, which is what the
    same tool's other failures reach the model as: always trusted, always unfenced, and carrying
    no correction at all. That arm is the baseline every rate here has to be read against,
    because a model that would have made the corrected move anyway shows the same count under a
    sentence that asked for it and under one that said nothing.
    """

    label: str
    corrected: bool
    trust: Trust


# The three arms, in the order they are drawn and printed. The control is the fenced correction:
# it is what this repo shipped until the own-text overlay landed, and it is the before the entry
# that asked for this measurement had nothing to compare against.
SHIPPED_ARM = Arm("unfenced (shipped)", corrected=True, trust=Trust.TRUSTED)
FENCED_ARM = Arm("fenced (control)", corrected=True, trust=Trust.UNTRUSTED)
BARE_ARM = Arm("bare failure (baseline)", corrected=False, trust=Trust.TRUSTED)
ARMS: tuple[Arm, ...] = (SHIPPED_ARM, FENCED_ARM, BARE_ARM)


def bare_failure(call: ToolCall) -> str:
    """The adapter's own message for a tool that failed, rendered as `McpToolRegistry` renders it.

    Restated here rather than imported because it is built inside the adapter's ``except`` and
    never bound to a name; the rendering is one line and the shape is what the baseline arm needs.
    """
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
    """One arm's counts, rendered in the fixed verdict order so the arms read side by side."""
    return "  ".join(f"{name}={verdicts.count(name)}/{len(verdicts)}" for name in VERDICTS)


def _report(label: str, replies: Sequence[Reply], verdicts: Sequence[str]) -> None:
    silent = sum(1 for reply in replies if reply.silent)
    cut = sum(1 for reply in replies if reply.finish_reason == "length")
    print(f"  --> {label}: {_tally(verdicts)}  (silent={silent} cut={cut})")  # noqa: T201


@pytest.mark.integration
async def test_the_dialect_the_cortex_writes_its_first_query_in() -> None:
    """How the first ``search_emails`` query is written, with no refusal anywhere in the turn.

    The cost the refused-search correction exists to recover, measured before any correction: a
    query in a mail client's ``key:value`` syntax is the dispatch the refusal has to buy back,
    and a query in the described criteria is one that never cost anything. The turn carries the
    ``list_folders`` step first because that is the call the shipped cortex really makes before
    it searches, and its answer is the sidecar's own, read back through the real adapter and
    fenced as the untrusted mailbox content it is.
    """
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
    """The refused-search correction, unfenced and fenced and against a bare failure."""
    refused = ToolCall(
        id=_CALL_ID,
        name=_SEARCH_TOOL,
        arguments={"folder": "INBOX", "query": _REFUSED_QUERY, "limit": _LIMIT},
    )
    correction = f"{SEARCH_REFUSED}{_REFUSED_QUERY!r}"
    await _measure("refused-search", _SEARCH_ASK, refused, correction, score_refused_search)


@pytest.mark.integration
async def test_the_unknown_folder_correction_across_the_three_arms() -> None:
    """The folder correction, whose instruction is one call rather than a rewrite."""
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
    """Run one row's three arms on the same seeds and print their counts."""
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
    # The one hard assertion, and it is the artifact check rather than the finding: an arm that
    # emitted no call at all would score every draw OTHER and read as a model ignoring the
    # correction, when what it measured was a model that answered nothing.
    mute = [label for label, calls in emitted.items() if calls == 0]
    assert not mute, f"{row}: {mute} emitted no tool call at all, so the counts measure silence"
