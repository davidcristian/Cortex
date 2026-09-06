"""What the cortex does with the uid description and with the not-found answer (ADR-0022).

``UID_HELP`` tells a model where a uid comes from, that it names a message only within the folder
it was listed in, and that a not-found answer is final; ``NOT_FOUND`` says the last of those again
once a read has come back empty. Both are prose written from the standard and from the shape of a
listing line, and neither had been read back off a model. This harness measures three things on
the shipped cortex tier, each a row of its own so ``-k`` selects one:

- **copied**: the uid a ``read_email`` carries after a search the sidecar answered with a real
  listing. It counts the reads whose uid stands on that listing against the reads whose uid does
  not, which is the difference between copying a number and composing one.
- **carried**: the same turn continued into a folder holding no mail. It counts the reads that
  take a uid from the other folder's listing into that folder, the mistake the per-folder sentence
  exists to stop.
- **after-not-found**: what the next call is once a read has been answered not found. Searching
  again is the correction's own instruction; another read in the same folder is the run of nearby
  numbers the sentence says is pointless.

The first two rows run two arms on the same twenty seeds: the shipped ``ToolSpec``, and the same
spec with the ``uid`` description stripped out. The stripped arm is what makes a null readable,
since a model that copies a uid off a listing anyway shows the same count with the sentence and
without it. The third row runs three arms: the answer as it reads since the correction landed, the
answer this repo shipped before that (``message <uid> not found in <folder>``), and the adapter's
bare ``MCP tool 'read_email' failed``, which carries no correction at all and is the baseline the
other two are read against.

Nothing about the request is typed here that the deployment declares elsewhere: the server's
command line is the model host's own cortex tier, the messages are composed by the shipped
``security_preamble_message``, ``call_message`` and ``result_message`` and mapped by the adapter's
own ``to_openai_message``, the tools are the real ``cortex_email`` server's specs read through the
real ``McpToolRegistry``, and every answer a step carries is what that server really returns.

Integration-marked (excluded from CI and the coverage gate). Needs the GPU, the toolkit and the
models at ``CORTEX_MODELS_DIR`` (docs/runbooks/llamacpp-gpu.md):

    cd brain && CORTEX_MODELS_DIR=/srv/models uv run pytest -m integration --no-cov -s \\
        packages/orchestrator/tests/test_uid_reading_live.py
"""

import contextlib
import copy
import json
import os
import subprocess
import time
from collections.abc import Generator, Mapping, Sequence
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
from cortex_inference.request import to_openai_message, to_openai_tools
from cortex_model_manager import ModelHostConfig, llama_server_argv
from cortex_tools import McpSession, McpToolRegistry

_IMAGE = "ghcr.io/ggml-org/llama.cpp:server-cuda"
_MODELS_DIR = os.environ.get("CORTEX_MODELS_DIR", "/srv/models")
_CONTAINER = "cortex-uid-probe"
_HEALTH_TIMEOUT_S = 300
_DRAW_TIMEOUT_S = 300

# How many draws an arm, for the reason the correction harness beside this one draws twenty: the
# reply that decides a draw is one tool call off a sampler the tier leaves at its own defaults.
DRAWS = 20


# ── the server, started the way the model host starts the cortex tier ────────


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


# ── the mailbox, and the real sidecar over it ────────────────────────────────

_FOLDERS = ("INBOX", "Sent", "Drafts", "Archive", "Spam", "Trash", "All Mail", "Folders/Jobs")
_SEARCH_TOOL = "search_emails"
_READ_TOOL = "read_email"

# The folder holding mail and the folder holding none, which is the pair the entry asks for.
WITH_MAIL = "INBOX"
WITHOUT_MAIL = "Archive"

# The uids the listing carries. They are neither consecutive nor round, so a number a model
# composes from the shape of the listing is not one of them by accident, and each gap is wide
# enough that the nearby number the description warns about is off the listing.
LISTED_UIDS = ("1204", "1211", "1223", "1238")
_SUBJECTS = (
    "Invoice for August",
    "Re: the quarterly numbers",
    "Lunch on Thursday",
    "Electricity bill, final notice",
)
# The uid the after-not-found row's read carries: between two listed ones and on neither, which
# is exactly the mistake `UID_HELP` names and the one `NOT_FOUND` answers.
MISSING_UID = "1224"


def _message(index: int) -> bytes:
    """One canned RFC822 message, differing in every header a listing line shows."""
    day = 3 + index
    return (
        f"From: Ann Weaver <ann.weaver@example.com>\r\n"
        f"To: me@example.com\r\n"
        f"Date: Wed, {day:02d} Sep 2026 09:0{index} +0000\r\n"
        f"Subject: {_SUBJECTS[index]}\r\n\r\nbody {index}\r\n"
    ).encode()


class _Mailbox:
    """A `Mailbox` over two folders: one holding four messages, one holding none."""

    def list_folders(self) -> Sequence[str]:
        return list(_FOLDERS)

    def search(self, folder: str, query: str, limit: int) -> Sequence[RawEmail]:
        del query, limit
        if folder != WITH_MAIL:
            return []
        return [RawEmail(uid=uid, raw=_message(i)) for i, uid in enumerate(LISTED_UIDS)]

    def fetch(self, folder: str, uid: str) -> RawEmail | None:
        if folder != WITH_MAIL or uid not in LISTED_UIDS:
            return None
        return RawEmail(uid=uid, raw=_message(LISTED_UIDS.index(uid)))


class _ServerSession:
    """An `McpSession` over the sidecar's FastMCP server in-process, no socket between them."""

    def __init__(self, server: FastMCP) -> None:
        self._server = server

    async def list_tools(self) -> ListToolsResult:
        return ListToolsResult(tools=await self._server.list_tools())

    async def call_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult:
        """Dispatch to the real server, so every answer a step carries is one it really wrote."""
        answer: object = await self._server.call_tool(name, arguments or {})
        if isinstance(answer, CallToolResult):
            return answer
        blocks = cast("tuple[Sequence[TextContent], object]", answer)[0]
        return CallToolResult(content=list(blocks))


def _sidecar() -> McpToolRegistry:
    """The real `cortex_email` server over the mailbox above, read by the real adapter."""
    session: McpSession = _ServerSession(build_server(EmailReader(_Mailbox())))
    return McpToolRegistry(session)


async def email_tool_specs() -> Sequence[ToolSpec]:
    """The specs the brain advertises for the email sidecar, read through the real adapter."""
    return await _sidecar().describe_tools()


async def sidecar_answer(call: ToolCall) -> str:
    """What the real sidecar answers ``call`` with, so no answer is typed into this file."""
    return (await _sidecar().invoke(call)).content


def without_uid_help(specs: Sequence[ToolSpec]) -> Sequence[ToolSpec]:
    """The same specs with `read_email`'s uid description removed and nothing else changed.

    The baseline arm for the two rows that measure what a model does with a listing. A schema is
    passed to the model verbatim, so dropping one description is the whole difference between the
    arms, and a count that does not move across them is a count the sentence did not produce.
    """
    stripped: list[ToolSpec] = []
    for spec in specs:
        if spec.name != _READ_TOOL:
            stripped.append(spec)
            continue
        parameters = copy.deepcopy(dict(spec.parameters))
        properties = cast("dict[str, dict[str, Any]]", parameters["properties"])
        properties["uid"].pop("description")
        stripped.append(ToolSpec(spec.name, spec.description, parameters, spec.gated))
    return stripped


# ── the exchange, composed by the shipped helpers ────────────────────────────

_AT = datetime(2026, 9, 6, 5, 0, tzinfo=UTC)
_TURN = "uid-probe"
_SEARCH_ID = "c0"
_SECOND_ID = "c1"
_READ_ID = "c2"
_LIMIT = 20

_QUERY = 'FROM "ann.weaver@example.com"'
# What the user asks for. The first names a message the listing holds, so the turn's next move is
# a read; the second sends the same turn into the folder holding none.
_READ_ASK = "Find what Ann Weaver sent me and read me her message about the electricity bill."
_ARCHIVE_ASK = (
    "Find Ann Weaver's message about the electricity bill and read it to me. "
    "Look in my Archive folder as well as the inbox."
)


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


@dataclass(frozen=True)
class Step:
    """One answered tool call already in the turn: the call, the answer, and how it is stamped."""

    call: ToolCall
    answer: str
    trust: Trust
    is_error: bool = False


def turn_messages(ask: str, steps: Sequence[Step]) -> list[Message]:
    """The turn as the brain composes it: the standing rule, the user's ask, then each step."""
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


# ── the rows ─────────────────────────────────────────────────────────────────

# What one draw did. The first two rows score where the uid came from; the third scores what the
# next call was. `OTHER` is every draw that made none of the named moves, a reply with no call
# included, and it is reported rather than folded into a rate.
LISTED = "listed"
UNLISTED = "unlisted"
NO_READ = "no-read"
CARRIED = "carried"
CLEAN = "clean"
SEARCHED = "searched"
RETRIED = "retried"
OTHER = "other"
SOURCE_VERDICTS = (LISTED, UNLISTED, NO_READ)
CARRY_VERDICTS = (CARRIED, CLEAN, OTHER)
NEXT_VERDICTS = (SEARCHED, RETRIED, OTHER)


def _tally(verdicts: Sequence[str], names: Sequence[str]) -> str:
    """One arm's counts, in the row's fixed verdict order so the arms read side by side."""
    return "  ".join(f"{name}={verdicts.count(name)}/{len(verdicts)}" for name in names)


def _report(
    label: str, replies: Sequence[Reply], verdicts: Sequence[str], names: Sequence[str]
) -> None:
    silent = sum(1 for reply in replies if reply.silent)
    cut = sum(1 for reply in replies if reply.finish_reason == "length")
    print(f"  --> {label}: {_tally(verdicts, names)}  (silent={silent} cut={cut})")  # noqa: T201


def score_source(reply: Reply) -> str:
    """Where the uid of the read came from: the listing the model read, or somewhere else."""
    call = reply.first(_READ_TOOL)
    if call is None:
        return NO_READ
    return LISTED if call.text_argument("uid") in LISTED_UIDS else UNLISTED


def score_carry(reply: Reply) -> str:
    """Whether the read reached into the folder holding none with the other folder's uid."""
    call = reply.first(_READ_TOOL)
    if call is None:
        return OTHER
    if call.text_argument("folder") != WITHOUT_MAIL:
        return CLEAN
    return CARRIED


def score_next(reply: Reply) -> str:
    """What the model did next: search again, read again, or something else."""
    if not reply.calls:
        return OTHER
    made = reply.calls[0].name
    if made == _SEARCH_TOOL:
        return SEARCHED
    return RETRIED if made == _READ_TOOL else OTHER


@dataclass(frozen=True)
class Arm:
    """One arm: its label, the specs the model is prompted with, and the answer the step carries."""

    label: str
    described: bool


DESCRIBED_ARM = Arm("described (shipped)", described=True)
STRIPPED_ARM = Arm("stripped (baseline)", described=False)
SOURCE_ARMS = (DESCRIBED_ARM, STRIPPED_ARM)

# The answer this repo shipped for a uid that is not there until the correction landed, spelled
# here because no module holds it any more. It is the second arm of the last row: the same
# absence, stated without a correction and without anything else changing.
PRIOR_ANSWER = f"message {MISSING_UID} not found in {WITH_MAIL}"


def bare_failure(call: ToolCall) -> str:
    """The adapter's own message for a tool that failed, rendered as `McpToolRegistry` renders it.

    Restated here rather than imported because it is built inside the adapter's ``except`` and
    never bound to a name.
    """
    return f"MCP tool {call.name!r} failed"


async def _searched_step() -> Step:
    """The search that opens every row, answered with the listing the real sidecar writes."""
    call = ToolCall(
        id=_SEARCH_ID,
        name=_SEARCH_TOOL,
        arguments={"folder": WITH_MAIL, "query": _QUERY, "limit": _LIMIT},
    )
    return Step(call, await sidecar_answer(call), Trust.UNTRUSTED)


@pytest.mark.integration
async def test_where_the_uid_of_the_read_comes_from() -> None:
    """The uid a read carries after a listing, with the description and without it."""
    specs = await email_tool_specs()
    steps = [await _searched_step()]
    messages = turn_messages(_READ_ASK, steps)
    print(f"\n=== copied: the uid the cortex reads with, {DRAWS} draws an arm ===")  # noqa: T201
    print(f"  listing uids: {', '.join(LISTED_UIDS)}")  # noqa: T201
    emitted: dict[str, int] = {}
    with _server():
        async with httpx.AsyncClient(timeout=_DRAW_TIMEOUT_S) as client:
            for arm in SOURCE_ARMS:
                tools = specs if arm.described else without_uid_help(specs)
                replies = [await _draw(client, messages, tools, seed) for seed in range(DRAWS)]
                verdicts = [score_source(reply) for reply in replies]
                for seed, (reply, verdict) in enumerate(zip(replies, verdicts, strict=True)):
                    call = reply.first(_READ_TOOL)
                    wrote = "" if call is None else f"{call.text_argument('uid')!r}"
                    made = reply.calls[0].name if reply.calls else "(no call)"
                    print(f"  {arm.label:21s} seed={seed:<3d} {verdict:9s} {made} {wrote}")  # noqa: T201
                _report(f"copied {arm.label}", replies, verdicts, SOURCE_VERDICTS)
                emitted[arm.label] = sum(1 for reply in replies if reply.calls)
    mute = [label for label, calls in emitted.items() if calls == 0]
    assert not mute, f"copied: {mute} emitted no tool call at all, so the counts measure silence"


@pytest.mark.integration
async def test_whether_a_uid_is_carried_into_the_folder_holding_none() -> None:
    """Whether a uid off one folder's listing is spent on a read of a folder holding no mail."""
    specs = await email_tool_specs()
    empty = ToolCall(
        id=_SECOND_ID,
        name=_SEARCH_TOOL,
        arguments={"folder": WITHOUT_MAIL, "query": _QUERY, "limit": _LIMIT},
    )
    steps = [await _searched_step(), Step(empty, await sidecar_answer(empty), Trust.TRUSTED)]
    messages = turn_messages(_ARCHIVE_ASK, steps)
    print(f"\n=== carried: a uid taken into {WITHOUT_MAIL}, {DRAWS} draws an arm ===")  # noqa: T201
    emitted: dict[str, int] = {}
    with _server():
        async with httpx.AsyncClient(timeout=_DRAW_TIMEOUT_S) as client:
            for arm in SOURCE_ARMS:
                tools = specs if arm.described else without_uid_help(specs)
                replies = [await _draw(client, messages, tools, seed) for seed in range(DRAWS)]
                verdicts = [score_carry(reply) for reply in replies]
                for seed, (reply, verdict) in enumerate(zip(replies, verdicts, strict=True)):
                    call = reply.first(_READ_TOOL)
                    wrote = (
                        ""
                        if call is None
                        else f"{call.text_argument('folder')}/{call.text_argument('uid')}"
                    )
                    made = reply.calls[0].name if reply.calls else "(no call)"
                    print(f"  {arm.label:21s} seed={seed:<3d} {verdict:9s} {made} {wrote}")  # noqa: T201
                _report(f"carried {arm.label}", replies, verdicts, CARRY_VERDICTS)
                emitted[arm.label] = sum(1 for reply in replies if reply.calls)
    mute = [label for label, calls in emitted.items() if calls == 0]
    assert not mute, f"carried: {mute} emitted no tool call at all, so the counts measure silence"


@pytest.mark.integration
async def test_what_the_cortex_does_after_a_not_found_answer() -> None:
    """The next call after a not-found answer, across the shipped, prior and bare arms."""
    specs = await email_tool_specs()
    missing = ToolCall(
        id=_READ_ID, name=_READ_TOOL, arguments={"folder": WITH_MAIL, "uid": MISSING_UID}
    )
    shipped = await sidecar_answer(missing)
    arms = (
        ("corrected (shipped)", shipped),
        ("prior (no correction)", PRIOR_ANSWER),
        ("bare failure (baseline)", bare_failure(missing)),
    )
    opening = await _searched_step()
    print(f"\n=== after-not-found: the next call, {DRAWS} draws an arm ===")  # noqa: T201
    emitted: dict[str, int] = {}
    with _server():
        async with httpx.AsyncClient(timeout=_DRAW_TIMEOUT_S) as client:
            for label, answer in arms:
                steps = [opening, Step(missing, answer, Trust.TRUSTED)]
                messages = turn_messages(_READ_ASK, steps)
                replies = [await _draw(client, messages, specs, seed) for seed in range(DRAWS)]
                verdicts = [score_next(reply) for reply in replies]
                for seed, (reply, verdict) in enumerate(zip(replies, verdicts, strict=True)):
                    made = reply.calls[0].name if reply.calls else "(no call)"
                    wrote = _written(reply)
                    print(f"  {label:23s} seed={seed:<3d} {verdict:9s} {made} {wrote}")  # noqa: T201
                _report(f"after-not-found {label}", replies, verdicts, NEXT_VERDICTS)
                emitted[label] = sum(1 for reply in replies if reply.calls)
    mute = [label for label, calls in emitted.items() if calls == 0]
    assert not mute, f"after-not-found: {mute} emitted no call, so the counts measure silence"


def _written(reply: Reply) -> str:
    """The first call's own arguments, short enough for one printed line."""
    if not reply.calls:
        return ""
    call = reply.calls[0]
    return (
        f"{call.text_argument('folder')} {call.text_argument('uid')}{call.text_argument('query')}"
    )
