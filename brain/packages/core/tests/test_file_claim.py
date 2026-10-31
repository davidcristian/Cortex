from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    REPLY_CAPPED_NOTE,
    DecodeStop,
    GenerationBounds,
    InferenceEvent,
    InMemorySessionStore,
    InMemoryToolRegistry,
    JsonSchema,
    Message,
    RecordingAuditSink,
    StopReason,
    TaintLedger,
    TextChunk,
    TextDelta,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
)
from cortex_core.file_claim import UNREAD_FOLDERS_NOTE, claims_folders, unread_folders_claim

_START = datetime(2026, 10, 31, 6, 0, tzinfo=UTC)
_ASKS = "What's the capital of Australia? And also tell me which folders you can read."
_LISTED = "I can read the following folders:\n- /home/user/Documents\n- /home/user/Downloads"

RECORDED = [
    "Here are the directories I am allowed to access:\n- /home/user/data\n- /home/user/documents",
    "The capital of Portugal is Lisbon.\n\nHere are the directories I am allowed to access:\n"
    "- `home`\n- `workspace`\n- `user_data`",
    "Regarding the directories I can access, here is the list:\n- /home/user/work",
    "As for the directories I am allowed to access, here they are:\n- `home`\n- `tmp`",
    "Here are the directories I am allowed to access:\n*   /home/user/documents",
    "17 times 23 is 391.\n\nI can access the following directories:\n- /home/user/Documents",
    "I can read any directory within the following paths:\n- `/home/user/Documents`",
    "I can read the following directories:\n- /home/user/\n- /home/user/documents/",
    "As for the folders I can access, here is the list of allowed directories:\n- `_memory`",
    "As for the folders I can access, I can read any directory within the following paths:\n"
    "- `/home/user/Documents`",
    "I can access any directory listed in the following locations:\n- `/home/user/`",
    "Regarding the folders I can access, here is the list of allowed directories:\n"
    "*   `Documents`\n\nI can also access any subdirectories within these folders.",
    "I am allowed to access the following directories:\n- /home/user/data",
    "The directories I am allowed to access are:\n- /projects",
    "The directory I am allowed to access is:\n/projects",
    "The directory you are allowed to access is:\n/projects",
    "I have access to the following directory:\n* `/projects`",
    "As for the folders I can access, I am permitted to read files and directories within the "
    "`/projects` directory.",
    "As for the folders I can access, I have permission to read the `/projects` directory.",
]

KIN = [
    "I can read C:\\Users\\me\\Documents.",
    "I can read ~/Documents and ~/Downloads.",
    "I\u2019m allowed to read /srv/data.",
    "I can also see /srv/data.",
    "I can read these folders: Documents and Downloads.",
    "1. I can read the following files:\n2. a.txt",
    "I can read the following files:\n1. a.txt\n2. b.txt",
    "I can read the following:\n- /srv/data",
]

NEAR_MISSES = [
    "",
    "I don't have access to your files.",
    "I do not have access to /home/user/Documents.",
    "I can't read /home/user/Documents.",
    "I cannot access your folders. Please give me a path such as /home/user/Documents.",
    "I am not allowed to read /home/user/Documents.",
    "I have no access to folders on this machine.",
    "Which folder do you mean?",
    "I can read a folder. Which one should I read?",
    "Can I read /home/user/Documents for you?",
    "Should I list /home/user/Documents?",
    "I can read /srv/data, is that the one you mean?",
    "I can read a file if you give me its path, such as /home/user/notes.txt.",
    "I can read a folder once you name it, for example /srv/data.",
    "To list a folder, run:\n```\nls /home/user/Documents\n```",
    "I can list a folder with this command:\n```bash\nls /home/user/Documents\n```",
    "I can list the following folders with this:\n```\n- /home/user/Documents\n```",
    "I can read a folder with `ls /home/user`.",
    "Use this:\n```\ncat /etc/hosts",
    "It prints this:\n```\nI can read /srv/data\n```",
    "It prints this:\n```\nI can read /srv/data",
    "Linux keeps its log files in /var/log.",
    "Your config files are usually under /etc.",
    "You can access /etc/hosts with sudo.",
    "- /var/log\n- /var/log/syslog",
    "I can access the page at https://example.com/docs/files.",
    "I can read and/or write files.",
    "I can see 3/4 of it.",
    "I can read files and folders in your project.",
    "I can read text files and PDFs.",
    "I can read the following file types:\n- Text\n- PDF",
    "I can read the following file formats:\n- txt\n- md",
    "I can read the following:\n- Text\n- PDF",
    "I can help with the following:\n- reading files\n- listing folders",
    "I can read the following folders:",
    "I can read the following folders:\n\nThe capital of Australia is Canberra.",
    "I can read the following folders:\nThe capital is Canberra.\n- /srv/data",
    "The capital of Australia is Canberra.",
    "I found these folders:\n- /home/user/Documents",
]

TYPED = [
    ("Which files are in /home/david/notes?", "I can read /home/david/notes."),
    ("Show me /home/david/notes.txt", "I can see /home/david/notes.txt, which holds no text."),
    ("What is in /srv/data?", "I can read the following folder:\n- `/srv/data`"),
    ("What is in my documents folder?", "I can read the following folder:\n- Documents"),
    ("What is in notes.txt?", "I can read the file you named: notes.txt"),
]


@pytest.mark.parametrize("reply", [*RECORDED, *KIN])
def test_a_reply_saying_it_reaches_a_path_or_a_listed_folder_is_a_claim(reply: str) -> None:
    assert claims_folders(reply, query=_ASKS)


@pytest.mark.parametrize("reply", NEAR_MISSES)
def test_a_reply_that_names_no_folder_it_says_it_reaches_is_not_a_claim(reply: str) -> None:
    assert not claims_folders(reply, query=_ASKS)


@pytest.mark.parametrize(("query", "reply"), TYPED)
def test_a_path_or_folder_the_person_typed_is_not_a_claim(*, query: str, reply: str) -> None:
    assert not claims_folders(reply, query=query)


def test_one_entry_the_person_did_not_type_is_a_claim() -> None:
    reply = "I can read the following folders:\n- /srv/data\n- /srv/other"
    assert claims_folders(reply, query="What is in /srv/data?")


@pytest.mark.parametrize(
    ("taint", "query", "reply", "claim"),
    [
        (TaintLedger(), _ASKS, _LISTED, True),
        (TaintLedger(tainted=True), _ASKS, _LISTED, False),
        (TaintLedger(), "What is the capital of Australia?", _LISTED, False),
        (
            TaintLedger(),
            "Remember my code 7319, and list the folders you can read.",
            _LISTED,
            False,
        ),
        (TaintLedger(), _ASKS, "The capital of Australia is Canberra.", False),
    ],
    ids=["no-call", "read", "other-question", "asks-to-remember", "no-folders"],
)
def test_the_claim_needs_a_file_question_and_a_turn_that_read_no_tool_output(
    *, taint: TaintLedger, query: str, reply: str, claim: bool
) -> None:
    assert unread_folders_claim(taint, query, reply) is claim


class _Clock:
    def __init__(self) -> None:
        self._ticks = 0

    def now(self) -> datetime:
        self._ticks += 1
        return _START + timedelta(seconds=self._ticks)


class _Scripted:
    def __init__(self, steps: Sequence[Sequence[InferenceEvent]]) -> None:
        self._steps = list(steps)

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema, bounds
        for event in self._steps.pop(0):
            yield event


async def _folders(arguments: Mapping[str, object]) -> str:
    del arguments
    return "/projects"


async def _turn(steps: Sequence[Sequence[InferenceEvent]]) -> tuple[str, InMemorySessionStore]:
    spec = ToolSpec(name="list_allowed_directories", description="list", parameters={})
    registry = InMemoryToolRegistry({spec.name: (spec, _folders)})
    sessions = InMemorySessionStore()
    caps = TurnCapabilities(tools=ToolDispatcher(registry, RecordingAuditSink(), _Clock()))
    engine = TurnEngine(sessions, _Scripted(steps), _Clock(), capabilities=caps)
    events = [event async for event in engine.handle_turn("s", _ASKS, turn_id="t-1")]
    return "".join(e.text for e in events if isinstance(e, TextDelta)), sessions


async def test_a_listed_folder_with_no_call_ends_with_the_note_in_what_is_saved() -> None:
    shown, sessions = await _turn([[TextChunk(_LISTED)]])
    assert shown == _LISTED + UNREAD_FOLDERS_NOTE
    assert (await sessions.history("s"))[-1].text == shown


async def test_a_listed_folder_after_a_call_shows_no_note() -> None:
    call = ToolCall(id="c1", name="list_allowed_directories", arguments={})
    shown, _sessions = await _turn([[call], [TextChunk(_LISTED)]])
    assert shown == _LISTED


async def test_the_note_comes_after_the_length_note() -> None:
    capped = [TextChunk(_LISTED), DecodeStop(StopReason.CAPPED)]
    shown, _sessions = await _turn([capped])
    assert shown == _LISTED + REPLY_CAPPED_NOTE + UNREAD_FOLDERS_NOTE
