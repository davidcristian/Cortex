"""The ``Embedder`` contract checks, run over every implementation of the port."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from cortex_core import EMBED_INPUT_CHARS, EMBEDDER_CONTEXT_TOKENS, Embedder, EmbedderError

_TEXT = "the sky is blue"
_OTHER = "a fact worth remembering"

# One token per character in the deployed model's tokenizer, the most any text measured.
_DENSEST = "東"


@dataclass(frozen=True, slots=True)
class EmbedderUnderTest:
    """One implementation plus the one way a test may take its backend away."""

    embedder: Embedder
    break_backend: Callable[[], None]


type Check = Callable[[EmbedderUnderTest], Awaitable[None]]


async def text_embeds_to_a_vector_of_real_numbers(under_test: EmbedderUnderTest) -> None:
    """The answer is a non-empty sequence of floats, because ranking multiplies and sums it."""
    vector = await under_test.embedder.embed(_TEXT)
    assert len(vector) > 0
    assert all(type(value) is float for value in vector)


async def every_text_embeds_at_one_width(under_test: EmbedderUnderTest) -> None:
    """The width belongs to the deployment's model, never to the text that was embedded."""
    widths = {
        len(await under_test.embedder.embed(_TEXT)),
        len(await under_test.embedder.embed(_OTHER)),
        len(await under_test.embedder.embed("")),
    }
    assert len(widths) == 1


async def the_same_text_embeds_the_same_way(under_test: EmbedderUnderTest) -> None:
    """One text always embeds to one vector, and an embedding between them changes nothing."""
    first = list(await under_test.embedder.embed(_TEXT))
    await under_test.embedder.embed(_OTHER)
    assert list(await under_test.embedder.embed(_TEXT)) == first


async def a_backend_that_cannot_answer_raises_embedder_error(
    under_test: EmbedderUnderTest,
) -> None:
    """A backend that cannot answer raises `EmbedderError`, from every implementation."""
    under_test.break_backend()
    try:
        await under_test.embedder.embed(_TEXT)
    except EmbedderError:
        return
    msg = "a broken backend embedded anyway"
    raise AssertionError(msg)


async def a_text_at_the_input_bound_embeds(under_test: EmbedderUnderTest) -> None:
    """The core sends at most `EMBED_INPUT_CHARS` characters, and every embedder takes them."""
    assert len(await under_test.embedder.embed(_DENSEST * EMBED_INPUT_CHARS)) > 0


async def a_text_longer_than_the_context_raises_embedder_error(
    under_test: EmbedderUnderTest,
) -> None:
    """A text the model cannot hold raises `EmbedderError`, the one error the core catches."""
    try:
        await under_test.embedder.embed(_DENSEST * EMBEDDER_CONTEXT_TOKENS)
    except EmbedderError:
        return
    msg = "a text longer than the context embedded anyway"
    raise AssertionError(msg)


BOUND_CHECKS: Sequence[Check] = (
    a_text_at_the_input_bound_embeds,
    a_text_longer_than_the_context_raises_embedder_error,
)

ALL_CHECKS: Sequence[Check] = (
    text_embeds_to_a_vector_of_real_numbers,
    every_text_embeds_at_one_width,
    the_same_text_embeds_the_same_way,
    a_backend_that_cannot_answer_raises_embedder_error,
    *BOUND_CHECKS,
)
