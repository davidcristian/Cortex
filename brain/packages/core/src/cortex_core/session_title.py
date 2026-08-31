"""Brain-generated session titles: build the prompt, run the model, clean the reply (ADR-0021).

A session's switcher title derives from its first user message by default (``sessions.py``).
When title generation is enabled, a turn engine instead asks the resident model for a short
title from the opening exchange and persists it via ``SessionStore.set_title``, so the switcher
shows what a chat is about rather than its opening words. Generating a title is inference, so it
runs where inference already runs: inside a turn, sequentially, after the reply's own stream has
released the GPU lease (no re-entrant acquire) and never on the read/list path (which would make
listing block on the model). The generated title lives in the store like every other piece of
conversation state, so it survives a model swap (the one hard rule). These are the pure pieces
(the prompt and the cleanup) plus the thin accumulation over the ``InferenceBackend`` port; the
engine owns the decision of when to call them (``TurnCapabilities.generate_titles``).
"""

from collections.abc import Sequence
from datetime import datetime

from cortex_core.conversation import Message, Role
from cortex_core.drain import drain_text
from cortex_core.inference import GenerationBounds
from cortex_core.ports import InferenceBackend
from cortex_core.sessions import TITLE_MAX

# How far a title's request may go (ADR-0038 bounded-side-calls addendum). Thinking is off because
# this pass's deliberation is discarded by construction: ``drain_text`` keeps ``TextChunk`` and
# drops ``ReasoningChunk`` before the caller sees a character of it, and the reasoning-only reply
# this feature already ships a fallback for (13,882 characters of thinking and no title, ADR-0021
# titles addendum) is that discard at its worst. Measured on the shipped cortex over one title
# prompt three times each way: thinking on decoded 277, 235 and 303 tokens in 9.7 s, 7.9 s and
# 10.4 s; off, it decoded 4 tokens in 0.2 s to 0.3 s, for the same titles run for run. The cap is
# here because nothing else bounds the request: ``clean_title`` cuts the stored text only after the
# model has replied.
#
# 32 is ``TITLE_MAX`` expressed in the request's own unit with room to spare: 48 characters is 12
# tokens at the ~4 chars/token this repo's character budgets assume, and eight times the four
# tokens a title actually costs. A tighter cap would save nothing measurable, a title already
# costing four tokens.
#
# Hitting the cap cannot change the stored title, which is what makes the pairing safe here in a
# way the recap's is not: a reply that reaches 32 tokens has already written past the 48 characters
# ``clean_title`` keeps, so the cut lands beyond the text that is stored. A cap with thinking left
# on deletes the answer entirely, and here that is certain rather than merely likely: the identical
# prompt capped at 16, 32 and 64 with thinking on came back ``finish_reason: "length"`` with an
# empty reply three times in three, because a title is four tokens and the deliberation before it
# is hundreds. An empty reply is the fallback this feature was built with (the engine persists
# nothing and the first-message derivation stands), so even that failure is the safe one; it is
# simply not a title.
#
# The trace budget sits beside the switch because it is the half that holds (ADR-0005
# request-lever addendum). The switch is a request to a template and was measured to do nothing on
# some picks under some request shapes; a budget of zero is a sampler that ends the thought
# wherever it starts. It is spelled here rather than derived from ``thinking`` anywhere, because
# what makes it right here is the discard above and nothing about the switch: nothing reads the
# trace this pass would spend.
TITLE_MAX_TOKENS = 32
TITLE_BOUNDS = GenerationBounds(max_tokens=TITLE_MAX_TOKENS, thinking=False, trace_tokens=0)

# The opening exchange follows this instruction as the model's only context. Kept short and
# deterministic; the reply is cleaned to one bounded line regardless of how the model answers.
_INSTRUCTION = (
    "Give this conversation a short title of a few words. Reply with only the title, "
    "with no quotation marks and no closing punctuation."
)


def build_title_messages(
    user_text: str, assistant_text: str, *, at: datetime, turn_id: str
) -> list[Message]:
    """The one-message prompt for a title: the instruction, then the session's opening exchange."""
    body = f"{_INSTRUCTION}\n\nUser: {user_text}\nAssistant: {assistant_text}"
    return [Message(role=Role.USER, text=body, at=at, turn_id=turn_id)]


def clean_title(raw: str) -> str:
    """Collapse the model's reply to one line, strip wrapping quotes, and bound it to ``TITLE_MAX``.

    A model may wrap a title in quotes or spread it over lines; this normalizes both. The result
    is bounded here and re-bounded by ``summarize_ends`` at read time, so a stored title can never
    exceed the switcher's width however the model replied. An empty result (the model said nothing
    usable) comes back as ``""`` for the caller to reject rather than persist.
    """
    collapsed = " ".join(raw.split())
    return collapsed.strip("\"'")[:TITLE_MAX]


async def generate_title(backend: InferenceBackend, model: str, messages: Sequence[Message]) -> str:
    """Run one tool-less completion and return its cleaned title.

    Only assistant text contributes; a reasoning model's ``ReasoningChunk`` and any ``ToolCall``
    are ignored, so the title is the reply and never the private thinking. ``InferenceError``
    propagates for the caller to absorb: a failed title falls back to the first-message derivation
    and is not worth failing a turn over.

    The call goes through ``drain_text`` (ADR-0038 decision 8) rather than a bare comprehension:
    a stream abandoned by a mid-drain failure would leave the GPU lease held until asynchronous-
    generator finalization, and the title runs inside a turn whose next acquire would then wait
    on nothing. It carries ``TITLE_BOUNDS``, so the request asks for a title rather than for the
    page of deliberation this function then throws away.
    """
    return clean_title(await drain_text(backend, model, messages, bounds=TITLE_BOUNDS))
