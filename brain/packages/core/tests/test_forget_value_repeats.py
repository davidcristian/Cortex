from datetime import UTC, datetime, timedelta

from cortex_core import (
    FORGET_CHOSEN_LIMIT,
    FORGET_CHOSEN_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    ForgetChosenTool,
    InMemoryMemoryStore,
    MemoryRecord,
    ToolCall,
)
from cortex_core.memory_values import whole_values

_AT = datetime(2026, 11, 7, 4, 0, 0, tzinfo=UTC)
_PHONE = "User: Remember that my phone number is 0176 5550 1234.\nAssistant: Noted."


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


async def test_a_number_sharing_only_a_prefix_is_not_listed() -> None:
    anna = "User: Remember that Anna's number is 0176 9988 7766.\nAssistant: Noted, Anna's number."
    lines, said, left = await _forget(
        "my phone number", _record("mine", _PHONE), _record("anna", anna, 1)
    )
    assert len(lines) == 2
    assert said.startswith("forgot 1 remembered exchanges;")
    assert left == ["anna"]


async def test_a_year_shared_with_another_fact_is_not_listed() -> None:
    passport = "User: Remember that my passport expires in March 2026.\nAssistant: Noted that."
    dentist = "User: Remember that my dentist is on 14.11.2026.\nAssistant: Noted that, 2026."
    lines, _, left = await _forget(
        "that my passport expires", _record("passport", passport), _record("dentist", dentist, 1)
    )
    assert len(lines) == 2
    assert left == ["dentist"]


async def test_a_year_in_the_reply_does_not_list_a_code_beside_it() -> None:
    car = "User: Remember that my car is a blue Fiat.\nAssistant: Noted on 7 November 2026."
    bike = "User: Remember my bike lock code.\nAssistant: Noted, your code for 2026 is 4512."
    _, _, left = await _forget(
        "remember that my car", _record("car", car), _record("bike", bike, 1)
    )
    assert left == ["bike"]


async def test_a_time_or_an_amount_shared_with_a_word_is_not_listed() -> None:
    yoga = "User: Remember that my yoga class starts at 18h30 and costs 1250 euros.\nAssistant: Ok."
    pottery = "User: My pottery class starts at 18h30.\nAssistant: Your class is at 18h30."
    loan = "User: The class loan is 1250 euros.\nAssistant: Noted, €1250 for the class."
    _, _, left = await _forget(
        "my yoga class",
        _record("yoga", yoga),
        _record("pottery", pottery, 1),
        _record("loan", loan, 2),
    )
    assert left == ["loan", "pottery"]


async def test_the_whole_number_restated_is_listed_under_a_line_naming_it() -> None:
    recall = "User: How do I reach me?\nAssistant: Your phone is 0176 5550 1234."
    lines, said, left = await _forget(
        "my phone number", _record("mine", _PHONE), _record("recall", recall, 1)
    )
    assert lines == [
        "Deletes for good, with no undo, these 2 remembered exchanges:",
        "- User: Remember that my phone number is 0176 5550 1234. Assistant: Noted.",
        "Listed because they also hold 0176 5550 1234:",
        "- User: How do I reach me? Assistant: Your phone is 0176 5550 1234.",
    ]
    assert said.startswith("forgot 2 remembered exchanges;")
    assert left == []


async def test_twenty_numbers_sharing_a_prefix_leave_the_forget_of_the_match() -> None:
    friends = [
        _record(f"f{i:02}", f"User: Remember friend {i}'s number 0176 {1000 + i} 0000.", i + 1)
        for i in range(FORGET_CHOSEN_LIMIT)
    ]
    lines, said, left = await _forget("my phone number", _record("mine", _PHONE), *friends)
    assert len(lines) == 2
    assert said.startswith("forgot 1 remembered exchanges;")
    assert len(left) == FORGET_CHOSEN_LIMIT


async def test_repeats_past_the_limit_leave_the_text_matches_listed_and_deleted() -> None:
    recalls = [
        _record(f"r{i:02}", "User: Phone?\nAssistant: Your phone is 0176 5550 1234.", i + 1)
        for i in range(FORGET_CHOSEN_LIMIT)
    ]
    lines, said, left = await _forget("my phone number", _record("mine", _PHONE), *recalls)
    assert lines == [
        "Deletes for good, with no undo, these 1 remembered exchanges:",
        "- User: Remember that my phone number is 0176 5550 1234. Assistant: Noted.",
        f"More than {FORGET_CHOSEN_LIMIT} exchanges also hold a value of these, so they stay.",
    ]
    assert said == (
        "forgot 1 remembered exchanges that contain that text, but more exchanges also hold its "
        f"value and were not listed, since a card lists at most {FORGET_CHOSEN_LIMIT}, so the "
        "value is not forgotten."
    )
    assert len(left) == FORGET_CHOSEN_LIMIT


async def test_the_limit_of_text_matches_is_still_listed_when_repeats_exist() -> None:
    mine = [
        _record(f"m{i:02}", f"User: my phone number, note {i}: 0176 5550 1234.", i)
        for i in range(FORGET_CHOSEN_LIMIT)
    ]
    recall = _record("recall", "User: Phone?\nAssistant: Your phone is 0176 5550 1234.", 30)
    lines, _, left = await _forget("my phone number", *mine, recall)
    assert len(lines) == FORGET_CHOSEN_LIMIT + 2
    assert left == ["recall"]


def test_a_whole_value_is_read_with_its_separators_and_letters() -> None:
    assert whole_values("Call 0176-5550-1234, code AB12CD34 or 7731-B, at 17:30.") == {
        "017655501234": "0176-5550-1234",
        "ab12cd34": "AB12CD34",
        "7731": "7731",
    }


def test_a_year_date_time_or_amount_is_not_a_value() -> None:
    text = "In 2026, on 2026-11-14 or 11/2026, at 18h30 or 1730 Uhr, pay $4400 or 1250 EUR."
    assert whole_values(text) == {}


def test_a_number_holding_a_year_among_long_groups_is_a_value() -> None:
    assert whole_values("Phone 030 2026 5555 or 2026 4512.") == {
        "03020265555": "030 2026 5555",
        "20264512": "2026 4512",
    }
