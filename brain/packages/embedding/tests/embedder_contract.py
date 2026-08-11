"""The `Embedder` contract, run over every implementation (AGENTS.md: ports before adapters)."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from cortex_core import Embedder, EmbedderError

# One text embedded twice, and a second one embedded between them: enough to tell an
# implementation that answers from the text apart from one that answers from a counter.
_TEXT = "the sky is blue"
_OTHER = "a fact worth remembering"


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
    """The port has one failure channel and every implementation owes it."""
    under_test.break_backend()
    try:
        await under_test.embedder.embed(_TEXT)
    except EmbedderError:
        return
    msg = "a broken backend embedded anyway"
    raise AssertionError(msg)


ALL_CHECKS: Sequence[Check] = (
    text_embeds_to_a_vector_of_real_numbers,
    every_text_embeds_at_one_width,
    the_same_text_embeds_the_same_way,
    a_backend_that_cannot_answer_raises_embedder_error,
)
