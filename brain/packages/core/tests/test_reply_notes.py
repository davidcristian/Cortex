import importlib
import pkgutil
from collections import defaultdict
from typing import cast

import pytest

import cortex_core
from cortex_core.forget_claim import (
    HANDED_CLAIM_NOTE,
    UNFORGOTTEN_CLAIM_NOTE,
    UNFORGOTTEN_CLAIM_NOTES,
)
from cortex_core.forget_uncalled import UNCALLED_FORGET_NOTE
from cortex_core.forget_unnamed import kept_note
from cortex_core.reply_notes import REPLY_NOTES, claim_corrected, model_text
from cortex_core.turn_output import place_note

# Notes the brain writes into a tool result, a prompt or a summary, never after a reply.
_NOT_IN_A_REPLY = frozenset(
    {
        "DAILY_NOTE",
        "FORGET_NOT_KEPT_NOTE",
        "NO_ROOM_NOTE",
        "RECALLED_RUNS_NOTE",
        "RESULT_CUT_NOTE",
        "TAIL_CUT_NOTE",
        "UNFOLDED_NOTE",
    }
)


def _as_appended(note: str) -> str:
    filled = note.format_map(defaultdict[str, str](lambda: "Tuesday 9:00"))
    return filled if filled.endswith(")") else f"{filled}\n- User: my code is 7731.)"


def _reply(text: str, *notes: str) -> str:
    parts = [text]
    for note in notes:
        parts.append(place_note(parts, note))
    return "".join(parts)


@pytest.mark.parametrize("note", REPLY_NOTES)
def test_each_note_as_the_brain_appends_it_is_left_out(note: str) -> None:
    text = "I deleted the old code and kept 7731."
    reply = _reply(text, _as_appended(note), UNFORGOTTEN_CLAIM_NOTE)
    assert model_text(reply).rstrip() == text


@pytest.mark.parametrize("note", REPLY_NOTES)
def test_a_note_alone_leaves_nothing(note: str) -> None:
    assert model_text(_reply("", _as_appended(note))) == ""


@pytest.mark.parametrize(
    "reply",
    [
        "I deleted your code.",
        "(Nothing was forgotten in this turn.)",
        UNFORGOTTEN_CLAIM_NOTE + "\n\nI deleted your code.",
        "Done." + UNFORGOTTEN_CLAIM_NOTE.rstrip(")"),
        "Done. " + UNFORGOTTEN_CLAIM_NOTE.lstrip("\n"),
    ],
)
def test_text_the_model_wrote_stays(reply: str) -> None:
    assert model_text(reply) == reply


@pytest.mark.parametrize("claim", [UNFORGOTTEN_CLAIM_NOTE, *UNFORGOTTEN_CLAIM_NOTES.values()])
@pytest.mark.parametrize("after", [(), (UNCALLED_FORGET_NOTE,), (_as_appended(REPLY_NOTES[0]),)])
def test_a_reply_closed_by_the_claim_note_is_corrected(claim: str, after: tuple[str, ...]) -> None:
    assert claim_corrected(_reply("I deleted your code.", claim, *after))


@pytest.mark.parametrize(
    "reply",
    [
        "I deleted your code.",
        _reply("I deleted your code.", UNCALLED_FORGET_NOTE),
        _reply("I deleted your code.", HANDED_CLAIM_NOTE),
        UNFORGOTTEN_CLAIM_NOTE + "\n\nI deleted your code.",
        "Done." + UNFORGOTTEN_CLAIM_NOTE.rstrip(")"),
        "Done. " + UNFORGOTTEN_CLAIM_NOTE.lstrip("\n"),
    ],
)
def test_a_reply_with_no_claim_note_at_its_end_is_not_corrected(reply: str) -> None:
    assert not claim_corrected(reply)


def test_a_list_note_with_a_line_break_inside_an_item_stays() -> None:
    reply = _reply("Done.", kept_note(["User: my code\nis 7731."]))
    assert model_text(reply) == reply


def _named_notes() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for info in pkgutil.walk_packages(cortex_core.__path__, "cortex_core."):
        module = importlib.import_module(info.name)
        for name, value in vars(module).items():
            if name.startswith("_") or name in _NOT_IN_A_REPLY:
                continue
            if name.endswith("_NOTE") and isinstance(value, str):
                found[name] = [value]
            elif name.endswith("_NOTES") and isinstance(value, dict):
                texts = cast("dict[str, object]", value).values()
                found[name] = [text for text in texts if isinstance(text, str)]
    return found


def test_every_note_a_module_names_is_listed() -> None:
    missing = {
        name
        for name, texts in _named_notes().items()
        if any(text not in REPLY_NOTES for text in texts)
    }
    assert missing == set()
