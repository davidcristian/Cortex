"""Drop the oldest history turns from a prompt the engine refused as longer than its context."""

from collections.abc import Sequence

from cortex_core.conversation import Message, Role

# The most characters one token holds on the cortex's tokenizer, measured on plain English. Dropping
# this many characters for each token over removes the excess of any text in one retry.
SHED_CHARS_PER_TOKEN = 4.7


def shed_oldest_turns(working: Sequence[Message], excess: int | None) -> list[Message] | None:
    """``working`` without enough of its oldest turns to cover ``excess`` tokens, at least one.

    System messages and the newest turn always stay; ``None`` when no other turn is left to drop.
    """
    turns: list[list[int]] = []
    for index, message in enumerate(working):
        if message.role is Role.SYSTEM:
            continue
        if turns and working[turns[-1][-1]].turn_id == message.turn_id:
            turns[-1].append(index)
        else:
            turns.append([index])
    needed = 0.0 if excess is None else excess * SHED_CHARS_PER_TOKEN
    dropped: set[int] = set()
    shed_chars = 0
    for turn in turns[:-1]:
        dropped.update(turn)
        shed_chars += sum(len(working[index].text) for index in turn)
        if shed_chars >= needed:
            break
    if not dropped:
        return None
    return [message for index, message in enumerate(working) if index not in dropped]
