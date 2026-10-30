import pytest

from cortex_core import (
    HashEmbedder,
    InMemoryMemoryStore,
    MemoryRecaller,
    SystemClock,
    ToolRun,
    TurnCapabilities,
)
from cortex_core.file_request import asks_files
from cortex_core.memory_claim import memory_withheld
from cortex_core.untrusted import TaintLedger

ASKS = [
    "What is the capital of Portugal? Also, list the directories you are allowed to access.",
    "Answer in one sentence first: what is 17 times 23? Then tell me which folders you can read.",
    "What's the capital of Australia? And also tell me which folders you can read.",
    "Read notes.txt in my files and tell me what it says.",
    "What does meeting-notes.txt say?",
    "Which folders can you read",
    "Do you have access to my files?",
    "Show me the directory tree.",
]
NOT_ASKS = [
    "What is the capital of Portugal?",
    "I keep my tax files in a blue folder.",
    "Please remember this: my locker code is 7319. Also, which folders can you read?",
    "Remember that my report is in report.pdf.",
    "Tell me a joke.",
    "",
]


@pytest.mark.parametrize("query", ASKS)
def test_a_message_asking_about_files_or_folders_is_read_as_such(query: str) -> None:
    assert asks_files(query)


@pytest.mark.parametrize("query", NOT_ASKS)
def test_a_statement_a_request_to_remember_or_another_question_is_not(query: str) -> None:
    assert not asks_files(query)


def _caps(*, record_tainted: bool) -> TurnCapabilities:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    return TurnCapabilities(memory=recaller, record_tainted_memory=record_tainted)


@pytest.mark.parametrize(
    ("taint", "runs", "query", "record_tainted", "withheld"),
    [
        (TaintLedger(), (), ASKS[0], False, True),
        (TaintLedger(), (ToolRun("set_volume", ok=True),), ASKS[2], True, True),
        (
            TaintLedger(tainted=True),
            (ToolRun("list_allowed_directories", ok=True),),
            ASKS[0],
            True,
            False,
        ),
        (TaintLedger(tainted=True), (ToolRun("read_text_file", ok=True),), ASKS[3], False, True),
        (TaintLedger(), (), NOT_ASKS[0], False, False),
        (TaintLedger(), (), NOT_ASKS[2], False, False),
    ],
)
def test_a_file_question_is_withheld_only_when_the_turn_read_no_tool_output(
    *,
    taint: TaintLedger,
    runs: tuple[ToolRun, ...],
    query: str,
    record_tainted: bool,
    withheld: bool,
) -> None:
    caps = _caps(record_tainted=record_tainted)
    assert memory_withheld(caps, taint, runs, query=query) is withheld
