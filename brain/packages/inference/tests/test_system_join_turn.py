import re
from typing import cast

import httpx
import pytest
from system_led import (
    CONTEXT,
    INSTRUCTION,
    RECAP,
    TAINTED_MEMORY,
    TRUSTED_MEMORY,
    RecordingBackend,
    plain_context_task,
    read_dispatcher,
    recalling_turn,
)
from template_servers import TemplateServer

from cortex_core import (
    SECURITY_PREAMBLE,
    Role,
    SingleResidentModelManager,
    SubagentTask,
    SystemClock,
    TurnCompleted,
)
from cortex_core.subagent_attempt import PlacedAttempt
from cortex_inference import LlamaCppBackend

_ENDPOINT = "http://llama-cortex:8080"
_REPLY = b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n'


def _entries(chat: dict[str, object]) -> list[dict[str, str]]:
    return cast("list[dict[str, str]]", chat["messages"])


def _adapter(server: TemplateServer) -> RecordingBackend:
    client = httpx.AsyncClient(transport=httpx.MockTransport(server))
    manager = SingleResidentModelManager("cortex", _ENDPOINT)
    return RecordingBackend(LlamaCppBackend(manager, client))


async def test_a_recalling_turn_with_a_recap_is_answered_where_the_template_takes_one() -> None:
    server = TemplateServer(takes_several=False, reply=_REPLY)
    backend = _adapter(server)
    events = await recalling_turn(backend)
    assert events[-1] == TurnCompleted(turn_id="t-now", full_text="ok")
    ((preamble, memory, recap, *kept),) = backend.sent
    assert preamble.text == SECURITY_PREAMBLE
    assert TRUSTED_MEMORY in memory.text
    assert TAINTED_MEMORY in memory.text
    assert RECAP in recap.text
    assert len(server.probes) == 1
    (wire,) = [_entries(chat) for chat in server.chats]
    assert wire[0] == {"role": "system", "content": f"{preamble.text}\n{memory.text}\n{recap.text}"}
    assert [entry["role"] for entry in wire[1:]] == [m.role.value for m in kept]
    assert [m.role for m in kept] == [Role.USER, Role.ASSISTANT, Role.USER]


async def test_a_template_that_takes_every_system_message_gets_the_three_apart() -> None:
    server = TemplateServer(takes_several=True, reply=_REPLY)
    backend = _adapter(server)
    events = await recalling_turn(backend)
    assert events[-1] == TurnCompleted(turn_id="t-now", full_text="ok")
    ((preamble, memory, recap, *_),) = backend.sent
    (wire,) = [_entries(chat) for chat in server.chats]
    assert wire[:3] == [
        {"role": "system", "content": preamble.text},
        {"role": "system", "content": memory.text},
        {"role": "system", "content": recap.text},
    ]


async def _attempt(server: TemplateServer, task: SubagentTask) -> str:
    attempt = PlacedAttempt(SystemClock(), read_dispatcher(), constrain_output=False)
    outcome = await attempt.run(task, "cortex", _adapter(server), budget=None, progress=None)
    assert outcome.ok, outcome.detail
    return outcome.text


async def test_a_tool_task_with_a_plain_context_is_answered_where_the_template_takes_one() -> None:
    server = TemplateServer(takes_several=False, reply=_REPLY)
    assert await _attempt(server, plain_context_task()) == "ok"
    assert [_entries(chat) for chat in server.chats] == [
        [
            {"role": "system", "content": f"{SECURITY_PREAMBLE}\n{CONTEXT}"},
            {"role": "user", "content": INSTRUCTION},
        ]
    ]


@pytest.mark.parametrize("takes_several", [True, False])
async def test_a_tainted_task_sends_its_one_system_message_without_asking(
    *, takes_several: bool
) -> None:
    server = TemplateServer(takes_several=takes_several, reply=_REPLY)
    assert await _attempt(server, plain_context_task(tainted=True)) == "ok"
    assert server.probes == []
    ((system, user),) = [_entries(chat) for chat in server.chats]
    assert system == {"role": "system", "content": SECURITY_PREAMBLE}
    assert user["role"] == "user"
    fence = r"<untrusted-tool-output id=([0-9a-f]+)>\n(.*)\n</untrusted-tool-output id=\1>\n\n(.*)"
    found = re.fullmatch(fence, user["content"], re.DOTALL)
    assert found is not None
    assert (found.group(2), found.group(3)) == (CONTEXT, INSTRUCTION)
