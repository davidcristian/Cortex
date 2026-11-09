from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    ForgetChosenTool,
    InMemoryMemoryStore,
    MemoryRecord,
    MemoryStoreError,
    ToolCall,
)
from cortex_core.memory_values import code_runs, digit_runs

_AT = datetime(2026, 11, 7, 8, 0, 0, tzinfo=UTC)
_CLEAN = "forgot 1 remembered exchanges; no remembered exchange contains that text now."


def _held(removed: int, holding: int) -> str:
    return (
        f"forgot {removed} remembered exchanges that contain that text, but {holding} other "
        "remembered exchanges still hold a number a deleted one held, so that number is still "
        "remembered; a forget of the number itself would remove them."
    )


def _record(record_id: str, text: str, minutes: int = 0) -> MemoryRecord:
    return MemoryRecord(
        id=record_id,
        text=text,
        embedding=(1.0, 0.0),
        at=_AT + timedelta(minutes=minutes),
        scope="global",
    )


async def _forget(
    text: str, *records: MemoryRecord, store: InMemoryMemoryStore | None = None
) -> tuple[int, str, bool, list[str]]:
    held = store or InMemoryMemoryStore()
    for record in records:
        await held.add(record)
    tool = ForgetChosenTool(held, GLOBAL_MEMORY_SCOPE)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text})
    card = await tool.card(call)
    assert card is not None
    result = await tool.invoke(call)
    left = sorted(hit.record.id for hit in await held.search((1.0, 0.0), k=100))
    return len(card.splitlines()) - 1, result.content, result.is_error, left


async def test_a_french_forget_says_an_english_recall_still_holds_the_code() -> None:
    asked = "User: Souviens-toi que le code de mon casier à la piscine est 7731.\nAssistant: Noté."
    recall = "User: What is my swimming pool locker code?\nAssistant: Your locker code is 7731."
    listed, said, error, left = await _forget(
        "casier à la piscine", _record("asked", asked), _record("recall", recall, 1)
    )
    assert (listed, said, error, left) == (1, _held(1, 1), False, ["recall"])


async def test_a_recall_naming_only_the_value_is_counted_without_the_value() -> None:
    asked = "User: Remember that my gym locker code is 5819.\nAssistant: Noted."
    recall = (
        "User: Reply with only the number: which number did I ask you to keep?\nAssistant: 5819"
    )
    _, said, _, left = await _forget(
        "gym locker code", _record("asked", asked), _record("recall", recall, 1)
    )
    assert said == _held(1, 1)
    assert "5819" not in said
    assert left == ["recall"]


async def test_a_restated_code_that_reads_as_a_year_is_counted() -> None:
    asked = "User: my door code is 1987\nAssistant: Noted."
    restated = "User: The code for the door is still 1987, right?\nAssistant: Yes."
    listed, said, _, left = await _forget(
        "door code", _record("asked", asked), _record("restated", restated, 1)
    )
    assert (listed, said, left) == (1, _held(1, 1), ["restated"])


async def test_a_restated_code_before_german_am_is_counted() -> None:
    asked = "User: der Türcode ist 4512\nAssistant: Notiert."
    restated = "User: Der Code 4512 am Hintereingang, oder?\nAssistant: Ja, der Türcode."
    listed, said, _, left = await _forget(
        "Türcode ist", _record("asked", asked), _record("restated", restated, 1)
    )
    assert (listed, said, left) == (1, _held(1, 1), ["restated"])


async def test_a_number_restated_with_other_separators_is_counted_both_ways() -> None:
    spaced = "User: Remember my phone number is 0151 2345 6789.\nAssistant: Noted."
    bare = "User: Call me at 015123456789 later.\nAssistant: Will do."
    _, said, _, _ = await _forget("phone number", _record("a", spaced), _record("b", bare, 1))
    assert said == _held(1, 1)
    spaced_left = "User: Call me at 0151-2345-6789 later.\nAssistant: Will do."
    bare_asked = "User: Remember my phone number is 015123456789.\nAssistant: Noted."
    _, said, _, _ = await _forget(
        "phone number", _record("a", bare_asked), _record("b", spaced_left, 1)
    )
    assert said == _held(1, 1)


async def test_rows_sharing_only_part_of_a_number_are_not_counted() -> None:
    asked = "User: Remember my locker code is 7731.\nAssistant: Noted."
    others = (
        "User: My room is 77310.\nAssistant: Room 77310.",
        "User: Call 0177 3100 2222.\nAssistant: Noted.",
        "User: The meeting was on 12.03.7731.\nAssistant: Ok.",
        "User: My pin is 731.\nAssistant: Ok.",
    )
    records = [_record(f"o{index}", text, index + 1) for index, text in enumerate(others)]
    _, said, _, left = await _forget("locker code", _record("asked", asked), *records)
    assert said == _CLEAN
    assert left == ["o0", "o1", "o2", "o3"]


async def test_every_row_holding_a_number_is_counted_once() -> None:
    asked = "User: My bike code is 4512 and my door code is 1987.\nAssistant: Noted, 4512."
    both = "User: 4512 or 1987?\nAssistant: Both."
    door = "User: door 1987\nAssistant: Ok."
    _, said, _, left = await _forget(
        "bike code", _record("asked", asked), _record("both", both, 1), _record("door", door, 2)
    )
    assert said == _held(1, 2)
    assert left == ["both", "door"]


async def test_a_deleted_row_with_no_number_reports_nothing_left() -> None:
    asked = "User: Remember my car is a blue Fiat.\nAssistant: Noted."
    other = "User: My code is 4512.\nAssistant: Noted."
    _, said, _, left = await _forget("blue Fiat", _record("asked", asked), _record("o", other, 1))
    assert said == _CLEAN
    assert left == ["o"]


class _FailingAfterDelete(InMemoryMemoryStore):
    def __init__(self) -> None:
        super().__init__()
        self.deleted = False

    async def delete_ids(self, ids: Sequence[str]) -> int:
        self.deleted = True
        return await super().delete_ids(ids)

    async def find_text(
        self, text: str, *, limit: int, scopes: Sequence[str] | None = None
    ) -> Sequence[MemoryRecord]:
        if self.deleted and text == "7731":
            msg = "pgvector is down"
            raise MemoryStoreError(msg)
        return await super().find_text(text, limit=limit, scopes=scopes)


async def test_a_store_failure_while_counting_the_numbers_left_is_reported() -> None:
    asked = "User: Remember my locker code is 7731.\nAssistant: Noted."
    _, said, error, _ = await _forget(
        "locker code", _record("asked", asked), store=_FailingAfterDelete()
    )
    assert said == (
        "forgot 1 remembered exchanges, but the memory store then failed, so it is not known "
        "whether other remembered exchanges still contain that text or its value: pgvector is down."
    )
    assert error is True


def test_a_digit_run_is_read_with_its_separators_years_and_units_alike() -> None:
    text = "Code 4512 am Tor, born 1987, call 0151 2345-6789, pin 731, on 14.11.2026, B7731X."
    assert digit_runs(text) == {
        "4512": "4512",
        "1987": "1987",
        "015123456789": "0151 2345-6789",
        "14112026": "14.11.2026",
        "7731": "7731",
    }


@pytest.mark.parametrize(
    ("asked", "other", "text"),
    [
        (
            "User: Remember that I got married in 2015.\nAssistant: Noted, married in 2015.",
            "User: Remember that I moved to Berlin in 2015.\nAssistant: Noted.",
            "married",
        ),
        (
            "User: Remind me about the dentist.\nAssistant: It is set for 2026-11-10 at 09:00.",
            "User: Remind me about the gym.\nAssistant: It is set for 2026-11-10 at 18:00.",
            "dentist",
        ),
        (
            "User: Je me suis marié en 2015.\nAssistant: C'est noté.",
            "User: Ich bin 2015 nach Berlin gezogen.\nAssistant: Notiert.",
            "marié",
        ),
        (
            "User: The meeting is on 14.11.2026.\nAssistant: Noted.",
            "User: My flight leaves on 14.11.2026.\nAssistant: Noted.",
            "meeting",
        ),
    ],
    ids=["shared-year", "shared-date-in-replies", "year-in-another-language", "shared-dotted-date"],
)
async def test_a_year_or_date_an_unrelated_row_shares_is_not_counted(
    asked: str, other: str, text: str
) -> None:
    _, said, _, left = await _forget(text, _record("asked", asked), _record("other", other, 1))
    assert (said, left) == (_CLEAN, ["other"])


@pytest.mark.parametrize(
    ("asked", "text"),
    [
        ("User: Le code de ma porte est 1987.\nAssistant: C'est noté.", "porte"),
        ("User: Mein Türcode ist 1987.\nAssistant: Notiert.", "Türcode"),
        ("User: El código de la puerta es 1987.\nAssistant: Anotado.", "puerta"),
        ("User: Codul ușii este 1987.\nAssistant: Notat.", "ușii"),
        ("User: My PIN is 1987.\nAssistant: Noted.", "PIN"),
        ("User: Remember the number 1987 for the door.\nAssistant: Noted.", "door"),
        ("User: My bike code is 4512 and I was born in 1987.\nAssistant: Noted.", "bike"),
        ("User: Mon mot de passe wifi est 1987.\nAssistant: C'est noté.", "wifi"),
        ("User: La combinación de la caja fuerte es 1987.\nAssistant: Anotado.", "caja"),
        ("User: Combinația seifului este 1987.\nAssistant: Notat.", "seifului"),
        ("User: Die Schlosskombination ist 1987.\nAssistant: Notiert.", "Schloss"),
        ("User: Mein Tresorpasswort ist 1987.\nAssistant: Notiert.", "Tresor"),
        ("User: My locker combo is 1987.\nAssistant: Noted.", "locker"),
    ],
    ids=[
        "french",
        "german",
        "spanish",
        "romanian",
        "pin",
        "number",
        "code-elsewhere-in-row",
        "french-password",
        "spanish-combination",
        "romanian-combination",
        "german-compound-combination",
        "german-compound-password",
        "combo",
    ],
)
async def test_a_year_shaped_number_a_row_names_as_a_code_is_counted(asked: str, text: str) -> None:
    other = "User: Which one was it?\nAssistant: 1987"
    _, said, _, left = await _forget(text, _record("asked", asked), _record("o", other, 1))
    assert (said, left) == (_held(1, 1), ["o"])


def test_a_code_run_keeps_a_year_or_date_only_in_a_text_naming_a_code() -> None:
    assert code_runs("I got married in 2015 on 14.11.2026, call 0151 2345.") == {
        "01512345": "0151 2345"
    }
    assert code_runs("Code 1987, on 14.11.2026.") == {"1987": "1987", "14112026": "14.11.2026"}
