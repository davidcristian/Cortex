from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    ForgetChosenTool,
    InMemoryMemoryStore,
    MemoryRecord,
    ToolCall,
)
from cortex_core.memory_values import value_searches

_AT = datetime(2026, 11, 8, 4, 0, 0, tzinfo=UTC)
_SPACED = "User: Remember that my phone number is 0151 2345 6789.\nAssistant: Noted."
_JOINED = "User: Call my phone at 015123456789 later.\nAssistant: Ok."
_HELD = "remembered exchanges that contain that text, but 1 other remembered exchanges still hold"


def _record(record_id: str, text: str, minutes: int = 0) -> MemoryRecord:
    return MemoryRecord(
        id=record_id,
        text=text,
        embedding=(1.0, 0.0),
        at=_AT + timedelta(minutes=minutes),
        scope="global",
    )


def _call(text: str) -> ToolCall:
    return ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text})


async def _forget(text: str, *records: MemoryRecord) -> tuple[list[str], str, list[str]]:
    store = InMemoryMemoryStore()
    for record in records:
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    card = await tool.card(_call(text))
    assert card is not None
    result = await tool.invoke(_call(text))
    left = sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=100))
    return card.splitlines(), result.content, left


async def test_a_number_restated_with_no_separators_is_listed_and_deleted() -> None:
    lines, said, left = await _forget(
        "phone number", _record("asked", _SPACED), _record("joined", _JOINED, 1)
    )
    assert lines == [
        "Deletes for good, with no undo, these 2 remembered exchanges:",
        "- User: Remember that my phone number is 0151 2345 6789. Assistant: Noted.",
        "Listed because they also hold 0151 2345 6789:",
        "- User: Call my phone at 015123456789 later. Assistant: Ok.",
    ]
    assert said.startswith("forgot 2 remembered exchanges;")
    assert left == []


async def test_a_number_restated_with_spaces_after_a_joined_one_is_listed() -> None:
    asked = "User: Remember that my phone number is 015123456789.\nAssistant: Noted."
    recall = "User: My phone?\nAssistant: Your phone is 0151 2345 6789."
    lines, _, left = await _forget(
        "phone number", _record("asked", asked), _record("recall", recall, 1)
    )
    assert lines[2:] == [
        "Listed because they also hold 015123456789:",
        "- User: My phone? Assistant: Your phone is 0151 2345 6789.",
    ]
    assert left == []


@pytest.mark.parametrize(
    "form",
    ["0151-2345-6789", "0151.2345.6789", "01512 345 6789", "01 51 2345 6789", "0151/2345/6789"],
)
async def test_a_number_restated_with_other_separators_is_listed(form: str) -> None:
    recall = f"User: My phone?\nAssistant: Your phone is {form}."
    lines, _, left = await _forget(
        "phone number", _record("asked", _SPACED), _record("recall", recall, 1)
    )
    assert len(lines) == 4
    assert left == []


async def test_the_value_itself_lists_a_row_writing_it_with_other_separators() -> None:
    other = "User: Remember my code 4512.\nAssistant: Noted."
    lines, said, left = await _forget(
        "0151 2345 6789",
        _record("asked", _SPACED),
        _record("joined", _JOINED, 1),
        _record("o", other, 2),
    )
    assert lines[2:] == [
        "Listed because they also hold 0151 2345 6789:",
        "- User: Call my phone at 015123456789 later. Assistant: Ok.",
    ]
    assert said.startswith("forgot 2 remembered exchanges;")
    assert left == ["o"]


@pytest.mark.parametrize(
    "near",
    [
        "User: Remember Anna's phone, 0151 2345 9999.\nAssistant: Noted, Anna's phone.",
        "User: My phone account is 0151234567890.\nAssistant: Noted.",
        "User: My work phone is +49 151 2345 6789.\nAssistant: Noted.",
        "User: My phone is 0151 2345, extension 6789.\nAssistant: Noted.",
        "User: Phone codes 0151 2345 and 6789.\nAssistant: Noted.",
    ],
)
@pytest.mark.parametrize("text", ["phone number", "0151 2345 6789"])
async def test_a_near_miss_of_the_number_stays(near: str, text: str) -> None:
    lines, said, left = await _forget(text, _record("asked", _SPACED), _record("near", near, 1))
    assert len(lines) == 2
    assert left == ["near"]
    assert said.startswith("forgot 1 remembered exchanges")


async def test_a_year_or_date_inside_the_number_is_not_listed() -> None:
    asked = "User: Remember that my phone number is 030 2026 5555.\nAssistant: Noted."
    year = "User: I got my phone in 2026.\nAssistant: Noted."
    date = "User: My phone contract renews on 2026-05-05.\nAssistant: Noted."
    lines, _, left = await _forget(
        "phone number", _record("asked", asked), _record("year", year, 1), _record("date", date, 2)
    )
    assert len(lines) == 2
    assert left == ["date", "year"]


async def test_a_restatement_with_no_word_of_the_text_stays_and_is_counted() -> None:
    bare = "User: And the other one?\nAssistant: 01 51 2345 6789."
    lines, said, left = await _forget(
        "phone number", _record("asked", _SPACED), _record("bare", bare, 1)
    )
    assert len(lines) == 2
    assert _HELD in said
    assert left == ["bare"]


def test_the_searches_reach_every_group_of_four_characters() -> None:
    assert value_searches("a12b34", "A12B-34") == ("A12B-34", "a12b34", "a12b", "12b3", "2b34")
    assert value_searches("7731", "7731") == ("7731",)


async def test_a_long_restatement_is_cut_around_its_own_form() -> None:
    recall = (
        f"User: {'Tell me everything you hold about me, please. ' * 3}\nAssistant: 015123456789."
    )
    lines, _, _ = await _forget(
        "0151 2345 6789", _record("asked", _SPACED), _record("r", recall, 1)
    )
    assert (
        lines[3] == "- ...e. Tell me everything you hold about me, please. Assistant: 015123456789."
    )
